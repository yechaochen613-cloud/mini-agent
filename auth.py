# auth.py
# ============================================================
# 用户账户 + 会话（登录态）存储。
#
# 设计目标：
#   - 与 chat_history / connectors 一样，复用 db.py 的 connect()，
#     本地用 SQLite、线上（Render）自动用 PostgreSQL，零额外依赖。
#   - 密码用标准库 pbkdf2_hmac 加盐哈希（不引入 bcrypt 等第三方包）。
#   - 登录态用「服务端会话 token + HttpOnly Cookie」实现，安全且前端无感知。
# ============================================================

import os
import time
import uuid
import secrets
import hashlib
import threading
import logging

logger = logging.getLogger(__name__)

from db import (connect, q, exec, fetchone, fetchall,
                create_table_if_not_exists, USE_PG)

# 会话有效期：30 天
SESSION_TTL = 60 * 60 * 24 * 30

_lock = threading.Lock()

_SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE,
    pw_hash TEXT,
    created_at INTEGER);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT,
    created_at INTEGER,
    expires_at INTEGER);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE TABLE IF NOT EXISTS oauth_states (
    token TEXT PRIMARY KEY,
    created_at INTEGER);
"""

_PG_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE,
    pw_hash TEXT,
    created_at INTEGER);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT,
    created_at INTEGER,
    expires_at INTEGER);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE TABLE IF NOT EXISTS oauth_states (
    token TEXT PRIMARY KEY,
    created_at INTEGER);
"""


def _init_db() -> None:
    with _lock:
        conn = connect()
        create_table_if_not_exists(conn, "users", _SQLITE_DDL, _PG_DDL)
        conn.close()


# ===== 密码哈希 =====
# 迭代次数：从最初 10 万提升到 20 万（SHA-256 下约增加几十毫秒/次，仍在可接受范围）。
# 哈希格式带版本前缀，便于以后再次升级；旧格式（无前缀）按 _LEGACY_ITER 兼容，
# 登录成功时自动用新参数重算并写回（透明升级，存量用户无感）。
PBKDF2_ITER = 200_000
_LEGACY_ITER = 100_000


def _hash_password(password: str) -> str:
    """返回 'v2|<iter>|<salt_hex>|<hash_hex>'，salt 随机。"""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITER)
    return f"v2|{PBKDF2_ITER}|{salt.hex()}|{dk.hex()}"


def _verify_password(password: str, stored: str):
    """返回 (ok: bool, needs_upgrade: bool)。needs_upgrade 为 True 表示旧格式命中，应重写。"""
    try:
        if stored.startswith("v2|"):
            _, it_s, salt_hex, hash_hex = stored.split("|", 3)
            it = int(it_s)
            salt = bytes.fromhex(salt_hex)
        else:
            # 旧格式：salt:hash，固定 10 万次
            salt_hex, hash_hex = stored.split(":", 1)
            it = _LEGACY_ITER
            salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, it)
        ok = secrets.compare_digest(dk.hex(), hash_hex)
        return ok, (not stored.startswith("v2|"))
    except Exception:
        return False, False


# ===== 用户注册 / 校验 =====
def register_user(username: str, password: str) -> dict:
    """注册新用户；重复用户名 / 非法输入抛 ValueError（由路由转 400）。"""
    username = (username or "").strip()
    if len(username) < 2 or len(username) > 32:
        raise ValueError("用户名长度需为 2-32 个字符")
    if " " in username or "\n" in username:
        raise ValueError("用户名不能包含空格")
    if not password or len(password) < 6:
        raise ValueError("密码至少 6 位")

    pw_hash = _hash_password(password)
    uid = str(uuid.uuid4())
    now = int(time.time())
    with _lock:
        conn = connect()
        row = fetchone(conn, "SELECT id FROM users WHERE username=?", (username,))
        if row:
            conn.close()
            raise ValueError("该用户名已被注册")
        exec(conn,
             "INSERT INTO users(id, username, pw_hash, created_at) VALUES(?,?,?,?)",
             (uid, username, pw_hash, now))
        conn.close()
    return {"id": uid, "username": username}


def verify_user(username: str, password: str) -> dict | None:
    """校验用户名 + 密码；成功返回用户 dict，失败返回 None。
    若命中旧哈希格式，登录成功后透明用新参数重算写回（兼容升级）。"""
    username = (username or "").strip()
    with _lock:
        conn = connect()
        row = fetchone(conn, "SELECT id, pw_hash FROM users WHERE username=?", (username,))
        if not row:
            conn.close()
            return None
        uid, pw_hash = row
        ok, upgrade = _verify_password(password, pw_hash)
        if not ok:
            conn.close()
            return None
        if upgrade:
            try:
                new_hash = _hash_password(password)
                exec(conn, "UPDATE users SET pw_hash=? WHERE id=?", (new_hash, uid))
            except Exception:
                pass  # 重哈希失败不影响本次登录
        conn.close()
    return {"id": uid, "username": username}


# ===== 会话（登录态） =====
def create_session(user_id: str) -> str:
    """生成一个会话 token 并落库，返回 token 字符串。"""
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    exp = now + SESSION_TTL
    with _lock:
        conn = connect()
        exec(conn,
             "INSERT INTO sessions(token, user_id, created_at, expires_at) VALUES(?,?,?,?)",
             (token, user_id, now, exp))
        conn.close()
    return token


def get_session_user(token: str) -> dict | None:
    """按 token 取当前登录用户；token 无效或过期返回 None。"""
    if not token:
        return None
    with _lock:
        conn = connect()
        row = fetchone(conn, "SELECT user_id, expires_at FROM sessions WHERE token=?", (token,))
        if not row:
            conn.close()
            return None
        uid, exp = row
        if exp and int(time.time()) > exp:
            exec(conn, "DELETE FROM sessions WHERE token=?", (token,))
            conn.close()
            return None
        urow = fetchone(conn, "SELECT id, username FROM users WHERE id=?", (uid,))
        conn.close()
    if not urow:
        return None
    return {"id": urow[0], "username": urow[1]}


def delete_session(token: str) -> None:
    """注销指定会话 token。"""
    if not token:
        return
    with _lock:
        conn = connect()
        exec(conn, "DELETE FROM sessions WHERE token=?", (token,))
        conn.close()


# ===== OAuth state 持久化（替代内存 dict：重启 / 多实例也不丢，回调校验仍可靠） =====
def save_oauth_state(token: str) -> None:
    """保存一个 OAuth state（GitHub 等 OAuth 回调的 CSRF 校验凭证）。"""
    with _lock:
        conn = connect()
        exec(conn, "INSERT OR REPLACE INTO oauth_states(token, created_at) VALUES(?,?)",
             (token, int(time.time())))
        conn.close()


def consume_oauth_state(token: str) -> bool:
    """校验并消费一个 OAuth state：存在则删除并返回 True，否则 False（防重放/伪造）。"""
    if not token:
        return False
    with _lock:
        conn = connect()
        row = fetchone(conn, "SELECT 1 FROM oauth_states WHERE token=?", (token,))
        if not row:
            conn.close()
            return False
        exec(conn, "DELETE FROM oauth_states WHERE token=?", (token,))
        conn.close()
    return True


# ===== 过期会话 / state 清理（避免表无限膨胀） =====
def cleanup_expired_sessions() -> int:
    """删除过期会话及过期 OAuth state，返回清理掉的会话数。"""
    now = int(time.time())
    with _lock:
        conn = connect()
        row = fetchone(conn, "SELECT COUNT(*) FROM sessions WHERE expires_at < ?", (now,))
        removed = row[0] if row else 0
        exec(conn, "DELETE FROM sessions WHERE expires_at < ?", (now,))
        # 过期 OAuth state（>10 分钟）顺手清理
        exec(conn, "DELETE FROM oauth_states WHERE created_at < ?", (now - 600,))
        conn.close()
    return removed


def _start_cleanup_scheduler(interval_sec: int = 3600) -> None:
    """后台守护线程：每隔 interval_sec 清理一次过期会话 / state。"""
    def _loop():
        while True:
            time.sleep(interval_sec)
            try:
                n = cleanup_expired_sessions()
                if n:
                    logger.info("[auth] 已清理 %d 个过期会话", n)
            except Exception as e:
                logger.warning("[auth] 清理任务出错（已忽略）: %s", e)
    threading.Thread(target=_loop, daemon=True).start()


# 模块加载即建表 + 启动过期清理调度
_init_db()
_start_cleanup_scheduler()
