# chat_history.py
# ============================================================
# 对话历史记录存储（支持 PostgreSQL / SQLite 自动切换）。
#
# 把每轮对话的「可见消息」（用户 / 助手 + 工具调用步骤）持久化到数据库，
# 支持列出历史会话、回看某次会话、新建、删除。
#
# 它独立于 LangGraph 的 MemorySaver：
#   - MemorySaver 只管「多轮上下文记忆」，便于 Agent 续聊；
#   - 这里存的是「看得见的历史对话记录」，刷新 / 重开页面都能回看。
#
# 持久化层见 db.py：线上用 Render PostgreSQL（重启不丢），本地回退 SQLite。
# ============================================================

import os
import json
import time
import uuid
import threading
from datetime import datetime

from db import (connect, q, exec, fetchall, fetchone,
                create_table_if_not_exists, USE_PG)

_lock = threading.Lock()


def _now() -> int:
    return int(time.time())


def _fmt(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


_SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT,
    created_at INTEGER,
    updated_at INTEGER,
    owner TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conv_id TEXT,
    role TEXT,
    text TEXT,
    steps TEXT,
    created_at INTEGER);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conv_id);
"""

_PG_DDL = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT,
    created_at INTEGER,
    updated_at INTEGER,
    owner TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conv_id TEXT,
    role TEXT,
    text TEXT,
    steps TEXT,
    created_at INTEGER);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conv_id);
"""


def _init_db() -> None:
    with _lock:
        conn = connect()
        create_table_if_not_exists(conn, "conversations", _SQLITE_DDL, _PG_DDL)
        conn.close()
    _migrate_owner()
    _migrate_json()


def _migrate_owner() -> None:
    """兼容旧库：若 conversations 表还没有 owner 列，则补加（默认空串）。"""
    with _lock:
        conn = connect()
        try:
            cur = conn.cursor()
            if USE_PG:
                cur.execute(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name='conversations' AND column_name='owner'"
                )
                exists = cur.fetchone() is not None
            else:
                cur.execute("PRAGMA table_info(conversations)")
                exists = any(r[1] == "owner" for r in cur.fetchall())
            if not exists:
                cur.execute(q(
                    "ALTER TABLE conversations ADD COLUMN owner TEXT NOT NULL DEFAULT ''"
                ))
                conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            conn.close()


def _migrate_json() -> None:
    """首次启动时，把项目根目录 / DATA_DIR 下遗留的 conversations.json 导入数据库。"""
    from storage import DATA_DIR
    legacy_paths = [
        os.path.join(DATA_DIR, "conversations.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "conversations.json"),
    ]
    src = next((p for p in legacy_paths if os.path.exists(p)), None)
    if not src:
        return
    try:
        with open(src, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return
    with _lock:
        conn = connect()
        for sid, c in data.items():
            exec(conn,
                 "INSERT OR IGNORE INTO conversations(id, title, created_at, updated_at) "
                 "VALUES(?,?,?,?)",
                 (sid, c.get("title", "新对话"), c.get("created_at", 0), c.get("updated_at", 0)))
            for m in c.get("messages", []):
                exec(conn,
                     "INSERT INTO messages(conv_id, role, text, steps, created_at) "
                     "VALUES(?,?,?,?,?)",
                     (sid, m.get("role"), m.get("text", ""),
                      json.dumps(m.get("steps", []), ensure_ascii=False), c.get("updated_at", 0)))
        conn.close()
    try:
        os.remove(src)
    except OSError:
        pass


# ===== 对外接口（签名与旧版保持一致，api.py 无需改动调用方式） =====
def list_conversations(owner: str | None = None) -> list:
    """返回历史会话列表（按最近更新时间倒序），每项含 id/title/时间/消息数。
    owner 不传则返回全部（兼容旧逻辑）；传了则只返回该用户的会话。"""
    conn = connect()
    if owner:
        rows = fetchall(conn,
                        "SELECT id, title, created_at, updated_at FROM conversations "
                        "WHERE owner=? ORDER BY updated_at DESC", (owner,))
    else:
        rows = fetchall(conn,
                        "SELECT id, title, created_at, updated_at FROM conversations "
                        "ORDER BY updated_at DESC")
    out = []
    for sid, title, created, updated in rows:
        cnt = fetchone(conn, "SELECT COUNT(*) FROM messages WHERE conv_id=?", (sid,))[0]
        out.append({
            "id": sid,
            "title": title,
            "created_at": created,
            "updated_at": updated,
            "updated_fmt": _fmt(updated),
            "msg_count": cnt,
        })
    conn.close()
    return out


def get_conversation(sid: str, owner: str | None = None) -> dict | None:
    """返回单次会话的完整内容（含 messages），不存在返回 None。
    owner 传入时做归属校验：会话不属于该用户则视为不存在。"""
    conn = connect()
    if owner:
        row = fetchone(conn,
                       "SELECT id, title, created_at, updated_at FROM conversations "
                       "WHERE id=? AND owner=?", (sid, owner))
    else:
        row = fetchone(conn,
                       "SELECT id, title, created_at, updated_at FROM conversations WHERE id=?",
                       (sid,))
    if not row:
        conn.close()
        return None
    msgs = fetchall(conn,
                    "SELECT role, text, steps FROM messages WHERE conv_id=? ORDER BY id ASC",
                    (sid,))
    conn.close()
    return {
        "id": row[0],
        "title": row[1],
        "created_at": row[2],
        "updated_at": row[3],
        "messages": [
            {"role": r, "text": t, "steps": json.loads(s or "[]")} for r, t, s in msgs
        ],
    }


def create_conversation(sid: str | None = None, title: str = "新对话",
                        owner: str = "") -> dict:
    """新建一个空会话；sid 不传则自动生成。已存在则直接返回。"""
    sid = sid or str(uuid.uuid4())
    now = _now()
    with _lock:
        conn = connect()
        exec(conn,
             "INSERT OR IGNORE INTO conversations(id, title, created_at, updated_at, owner) "
             "VALUES(?,?,?,?,?)", (sid, title, now, now, owner or ""))
        conn.close()
    return {"id": sid, "title": title}


def append_message(sid: str, role: str, text: str,
                   steps: list | None = None, title: str | None = None,
                   owner: str = "") -> dict:
    """往某会话追加一条消息。会话不存在会自动创建（并归属 owner）。
    role: 'user' | 'bot'；steps 是工具调用步骤（仅 bot 有）。
    title 用于给会话起名（通常是首条用户消息的前若干字）。"""
    now = _now()
    with _lock:
        conn = connect()
        cur = fetchone(conn, "SELECT id, title, owner FROM conversations WHERE id=?", (sid,))
        if not cur:
            exec(conn,
                 "INSERT INTO conversations(id, title, created_at, updated_at, owner) "
                 "VALUES(?,?,?,?,?)", (sid, title or "新对话", now, now, owner or ""))
        elif title and (not cur[1] or cur[1] == "新对话"):
            exec(conn,
                 "UPDATE conversations SET title=?, updated_at=? WHERE id=?",
                 (title, now, sid))
        else:
            exec(conn,
                 "UPDATE conversations SET updated_at=? WHERE id=?", (now, sid))
        exec(conn,
             "INSERT INTO messages(conv_id, role, text, steps, created_at) "
             "VALUES(?,?,?,?,?)",
             (sid, role, text, json.dumps(steps or [], ensure_ascii=False), now))
        conn.close()
    return get_conversation(sid)


def delete_conversation(sid: str, owner: str | None = None) -> dict:
    """删除一条历史会话（会话 + 其全部消息）。
    owner 传入时只删属于自己的会话。"""
    with _lock:
        conn = connect()
        if owner:
            exec(conn, "DELETE FROM conversations WHERE id=? AND owner=?", (sid, owner))
        else:
            exec(conn, "DELETE FROM conversations WHERE id=?", (sid,))
        exec(conn, "DELETE FROM messages WHERE conv_id=?", (sid,))
        conn.close()
    return {"status": "ok", "id": sid}


def get_recent_messages(sid: str, limit: int = 20) -> list:
    """取某会话最近 limit 条可见消息（role/text，正序），用于重启后回灌 LangGraph 上下文。
    不校验归属——调用方（api.py 的 /chat）已通过鉴权拿到属于该用户的 session_id。"""
    conn = connect()
    rows = fetchall(conn,
                    "SELECT role, text FROM messages WHERE conv_id=? "
                    "ORDER BY id DESC LIMIT ?", (sid, limit))
    conn.close()
    return [{"role": r, "text": t} for r, t in reversed(rows)]


# 模块加载即建表 + 迁移
_init_db()
