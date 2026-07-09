# chat_history.py
# ============================================================
# 对话历史记录存储（SQLite 版）。
#
# 把每轮对话的「可见消息」（用户 / 助手 + 工具调用步骤）持久化到 SQLite，
# 支持列出历史会话、回看某次会话、新建、删除。
#
# 相比旧版 conversations.json：
#   - 真正的数据库，并发安全（WAL + 锁），不会因半截写入损坏；
#   - 数据落在 storage.DATA_DIR，挂载 Render Disk 后 redeploy/重启都不丢；
#   - 首次启动会自动把项目根目录下的旧 conversations.json 平滑迁移进库。
#
# 它独立于 LangGraph 的 MemorySaver：
#   - MemorySaver 只管「多轮上下文记忆」，便于 Agent 续聊；
#   - 这里存的是「看得见的历史对话记录」，刷新 / 重开页面都能回看。
# ============================================================

import os
import json
import time
import uuid
import sqlite3
import threading
from datetime import datetime

from storage import DATA_DIR

DB_FILE = os.path.join(DATA_DIR, "conversations.db")
_lock = threading.Lock()


# ===== 底层连接（每次操作独立连接，线程安全；WAL 模式提升并发读） =====
def _conn() -> sqlite3.Connection:
    # 显式强制 DELETE（rollback）journal 模式：PRAGMA 会改写数据库文件头里持久化的
    # journal 标志，避免沿用历史 WAL 残留（旧 .db 文件可能是 WAL 模式）导致读取视图不一致，
    # 或进程被 SIGKILL / redeploy 时未 checkpoint 而丢数据。每次 commit 直接落主库，最稳。
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=DELETE")
    return conn


def _now() -> int:
    return int(time.time())


def _fmt(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def _init_db() -> None:
    with _lock:
        conn = _conn()
        conn.execute(
            """CREATE TABLE IF NOT EXISTS conversations (
                   id TEXT PRIMARY KEY,
                   title TEXT,
                   created_at INTEGER,
                   updated_at INTEGER)"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS messages (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   conv_id TEXT,
                   role TEXT,
                   text TEXT,
                   steps TEXT,
                   created_at INTEGER)"""
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conv_id)"
        )
        conn.commit()
        conn.close()
    _migrate_json()


def _migrate_json() -> None:
    """首次启动时，把项目根目录 / DATA_DIR 下遗留的 conversations.json 导入 SQLite。"""
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
        conn = _conn()
        for sid, c in data.items():
            conn.execute(
                "INSERT OR IGNORE INTO conversations(id, title, created_at, updated_at) "
                "VALUES(?,?,?,?)",
                (sid, c.get("title", "新对话"), c.get("created_at", 0), c.get("updated_at", 0)),
            )
            for m in c.get("messages", []):
                conn.execute(
                    "INSERT INTO messages(conv_id, role, text, steps, created_at) "
                    "VALUES(?,?,?,?,?)",
                    (sid, m.get("role"), m.get("text", ""),
                     json.dumps(m.get("steps", []), ensure_ascii=False), c.get("updated_at", 0)),
                )
        conn.commit()
        conn.close()
    try:
        os.remove(src)
    except OSError:
        pass


# ===== 对外接口（签名与旧版 JSON 版保持一致，api.py 无需改动调用方式） =====
def list_conversations() -> list:
    """返回历史会话列表（按最近更新时间倒序），每项含 id/title/时间/消息数。"""
    conn = _conn()
    rows = conn.execute(
        "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC"
    ).fetchall()
    out = []
    for sid, title, created, updated in rows:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE conv_id=?", (sid,)
        ).fetchone()[0]
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


def get_conversation(sid: str) -> dict | None:
    """返回单次会话的完整内容（含 messages），不存在返回 None。"""
    conn = _conn()
    row = conn.execute(
        "SELECT id, title, created_at, updated_at FROM conversations WHERE id=?",
        (sid,),
    ).fetchone()
    if not row:
        conn.close()
        return None
    msgs = conn.execute(
        "SELECT role, text, steps FROM messages WHERE conv_id=? ORDER BY id ASC", (sid,)
    ).fetchall()
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


def create_conversation(sid: str | None = None, title: str = "新对话") -> dict:
    """新建一个空会话；sid 不传则自动生成。已存在则直接返回。"""
    sid = sid or str(uuid.uuid4())
    now = _now()
    with _lock:
        conn = _conn()
        conn.execute(
            "INSERT OR IGNORE INTO conversations(id, title, created_at, updated_at) "
            "VALUES(?,?,?,?)", (sid, title, now, now)
        )
        conn.commit()
        conn.close()
    return {"id": sid, "title": title}


def append_message(sid: str, role: str, text: str,
                   steps: list | None = None, title: str | None = None) -> dict:
    """往某会话追加一条消息。会话不存在会自动创建。
    role: 'user' | 'bot'；steps 是工具调用步骤（仅 bot 有）。
    title 用于给会话起名（通常是首条用户消息的前若干字）。"""
    now = _now()
    with _lock:
        conn = _conn()
        cur = conn.execute("SELECT id, title FROM conversations WHERE id=?", (sid,)).fetchone()
        if not cur:
            conn.execute(
                "INSERT INTO conversations(id, title, created_at, updated_at) "
                "VALUES(?,?,?,?)", (sid, title or "新对话", now, now)
            )
        elif title and (not cur[1] or cur[1] == "新对话"):
            # 首条消息时，用首句给会话命名（避免一直叫「新对话」）
            conn.execute(
                "UPDATE conversations SET title=?, updated_at=? WHERE id=?",
                (title, now, sid)
            )
        else:
            conn.execute(
                "UPDATE conversations SET updated_at=? WHERE id=?", (now, sid)
            )
        conn.execute(
            "INSERT INTO messages(conv_id, role, text, steps, created_at) "
            "VALUES(?,?,?,?,?)",
            (sid, role, text, json.dumps(steps or [], ensure_ascii=False), now)
        )
        conn.commit()
        conn.close()
    return get_conversation(sid)


def delete_conversation(sid: str) -> dict:
    """删除一条历史会话（会话 + 其全部消息）。"""
    with _lock:
        conn = _conn()
        conn.execute("DELETE FROM conversations WHERE id=?", (sid,))
        conn.execute("DELETE FROM messages WHERE conv_id=?", (sid,))
        conn.commit()
        conn.close()
    return {"status": "ok", "id": sid}


# 模块加载即建表 + 迁移
_init_db()
