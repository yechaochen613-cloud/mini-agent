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
"""


def _init_db() -> None:
    with _lock:
        conn = connect()
        create_table_if_not_exists(conn, "users", _SQLITE_DDL, _PG_DDL)
        conn.close()


# ===== 密码哈希 =====
def _hash_password(password: str) -> str:
    """返回 'salt_hex:hash_hex'，salt 随机。"""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return salt.hex() + ":" + dk.hex()


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, hash_hex = stored.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
        return secrets.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


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
    """校验用户名 + 密码；成功返回用户 dict，失败返回 None。"""
    username = (username or "").strip()
    with _lock:
        conn = connect()
        row = fetchone(conn, "SELECT id, pw_hash FROM users WHERE username=?", (username,))
        conn.close()
    if not row:
        return None
    uid, pw_hash = row
    if not _verify_password(password, pw_hash):
        return None
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


# 模块加载即建表
_init_db()
