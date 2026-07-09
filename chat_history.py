# chat_history.py
# 对话历史记录存储：把每轮对话的「可见消息」（用户 / 助手 + 工具调用步骤）
# 持久化到 conversations.json，支持列出历史会话、回看某次会话、新建、删除。
#
# 设计上它独立于 LangGraph 的 MemorySaver：
#   - MemorySaver 只管「多轮上下文记忆」，便于 Agent 续聊；
#   - 这里存的是「看得见的历史对话记录」，刷新/重开页面都能回看。
# 二者解耦，任意一方丢失都不影响另一方（比如服务重启后 MemorySaver 清空，
# 但历史记录仍在，用户照样能点开看之前的聊天）。

import os
import json
import time
import uuid
import threading
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HIST_FILE = os.path.join(BASE_DIR, "conversations.json")
_lock = threading.Lock()


# ===== 底层读写（加锁，保证并发安全） =====
def _load() -> dict:
    if not os.path.exists(HIST_FILE):
        return {}
    try:
        with open(HIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict) -> None:
    # 写临时文件再原子替换，避免半截写入导致文件损坏
    tmp = HIST_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, HIST_FILE)


def _now() -> int:
    return int(time.time())


def _fmt(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


# ===== 对外接口 =====
def list_conversations() -> list:
    """返回历史会话列表（按最近更新时间倒序），每项含 id/title/时间/消息数。"""
    data = _load()
    out = []
    for sid, c in data.items():
        updated = c.get("updated_at", c.get("created_at", 0))
        out.append({
            "id": sid,
            "title": c.get("title", "新对话"),
            "created_at": c.get("created_at", 0),
            "updated_at": updated,
            "updated_fmt": _fmt(updated),
            "msg_count": len(c.get("messages", [])),
        })
    out.sort(key=lambda x: x["updated_at"], reverse=True)
    return out


def get_conversation(sid: str) -> dict | None:
    """返回单次会话的完整内容（含 messages），不存在返回 None。"""
    return _load().get(sid)


def create_conversation(sid: str | None = None, title: str = "新对话") -> dict:
    """新建一个空会话；sid 不传则自动生成。已存在则直接返回。"""
    sid = sid or str(uuid.uuid4())
    now = _now()
    with _lock:
        data = _load()
        if sid not in data:
            data[sid] = {
                "id": sid,
                "title": title,
                "created_at": now,
                "updated_at": now,
                "messages": [],
            }
            _save(data)
    return {"id": sid, "title": title}


def append_message(sid: str, role: str, text: str,
                   steps: list | None = None, title: str | None = None) -> dict:
    """往某会话追加一条消息。会话不存在会自动创建。
    role: 'user' | 'bot'；steps 是工具调用步骤（仅 bot 有）。
    title 用于给会话起名（通常是首条用户消息的前若干字）。"""
    now = _now()
    with _lock:
        data = _load()
        c = data.get(sid)
        if not c:
            c = {"id": sid, "title": title or "新对话",
                 "created_at": now, "updated_at": now, "messages": []}
            data[sid] = c
        # 首条消息时，用首句给会话命名（避免一直叫「新对话」）
        if title and (not c.get("title") or c.get("title") == "新对话"):
            c["title"] = title
        c["updated_at"] = now
        c["messages"].append({
            "role": role,
            "text": text,
            "steps": steps or [],
        })
        _save(data)
    return c


def delete_conversation(sid: str) -> dict:
    """删除一条历史会话。"""
    with _lock:
        data = _load()
        if sid in data:
            del data[sid]
            _save(data)
    return {"status": "ok", "id": sid}
