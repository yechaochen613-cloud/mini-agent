"""
学习库（Library）—— 错题本 + 收藏，集中放在 DATA_DIR/library.json。

设计要点：
  - 与 schedules / notes 同思路：用 JSON 文件存储（DATA_DIR 在 Render 挂 Disk 后持久化，
    本地则在项目 data/ 目录），无需改数据库表结构，SQLite / Postgres 下表现一致。
  - 错题本（wrong_questions）：学生答错的题归集，按学科/章节归类，保留 AI 讲解。
  - 收藏（favorites）：把 AI 讲得好的答案一键存为收藏，支持标注。
  - 所有函数都是纯数据层，api.py 只负责调它们 + 校验。
"""

import os
import json
import time
import uuid

from storage import DATA_DIR

LIB_FILE = os.path.join(DATA_DIR, "library.json")


def _load():
    if not os.path.exists(LIB_FILE):
        return {"wrong_questions": [], "favorites": []}
    try:
        with open(LIB_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        d.setdefault("wrong_questions", [])
        d.setdefault("favorites", [])
        return d
    except Exception:
        return {"wrong_questions": [], "favorites": []}


def _save(d):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LIB_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _now_ts():
    return int(time.time())


# 艾宾浩斯复习间隔（天），索引 = 掌握度 0(生疏)~5(熟练)
REVIEW_INTERVALS = [1, 2, 4, 7, 15, 30]
MASTERY_LABELS = ["生疏", "薄弱", "一般", "良好", "扎实", "熟练"]


# ===== 错题本 =====
def list_wrong_questions(subject=None):
    items = _load()["wrong_questions"]
    if subject:
        items = [i for i in items if i.get("subject") == subject]
    return sorted(items, key=lambda x: x.get("created_at", ""), reverse=True)


def add_wrong_question(data):
    d = _load()
    now_ts = _now_ts()
    item = {
        "id": uuid.uuid4().hex[:12],
        "subject": (data.get("subject") or "").strip(),
        "question": (data.get("question") or "").strip(),
        "my_answer": (data.get("my_answer") or "").strip(),
        "correct_answer": (data.get("correct_answer") or "").strip(),
        "explanation": (data.get("explanation") or "").strip(),
        "created_at": _now(),
        # 复习闭环字段
        "mastery": 0,                              # 0 生疏 ~ 5 熟练
        "review_count": 0,                        # 已复习次数
        "next_review_at": now_ts + 86400,         # 首次复习：明天
        "last_review_at": None,                   # 上次复习时间戳
    }
    d["wrong_questions"].append(item)
    _save(d)
    return item


def delete_wrong_question(wid):
    d = _load()
    new = [i for i in d["wrong_questions"] if i["id"] != wid]
    if len(new) != len(d["wrong_questions"]):
        d["wrong_questions"] = new
        _save(d)
        return True
    return False


def update_wrong_question(wid, data):
    d = _load()
    for i in d["wrong_questions"]:
        if i["id"] == wid:
            for k, v in data.items():
                if v is None:
                    continue
                if k in ("subject", "my_answer", "correct_answer", "explanation"):
                    i[k] = str(v).strip()
                elif k == "mastery":
                    try:
                        i["mastery"] = max(0, min(5, int(v)))
                    except (TypeError, ValueError):
                        pass
            _save(d)
            return i
    return None


def review_wrong_question(wid, mastery):
    """标记一次复习：更新掌握度，按艾宾浩斯推算下次复习时间。返回更新后的错题，找不到返回 None。"""
    d = _load()
    for i in d["wrong_questions"]:
        if i["id"] == wid:
            m = max(0, min(5, int(mastery) if mastery is not None else (i.get("mastery", 0) or 0)))
            i["mastery"] = m
            i["review_count"] = (i.get("review_count", 0) or 0) + 1
            now_ts = _now_ts()
            i["last_review_at"] = now_ts
            i["next_review_at"] = now_ts + REVIEW_INTERVALS[m] * 86400
            _save(d)
            return i
    return None


def due_wrong_questions():
    """返回当前应当复习的错题（下次复习时间 <= 现在，或从未排期）。按紧急度（时间升序）排列。"""
    now_ts = _now_ts()
    items = _load()["wrong_questions"]
    due = []
    for i in items:
        nxt = i.get("next_review_at")
        if nxt is None or nxt <= now_ts:
            due.append(i)
    due.sort(key=lambda x: x.get("next_review_at") or 0)
    return due


def subjects_of_wrong_questions():
    return sorted({i.get("subject") for i in _load()["wrong_questions"] if i.get("subject")})


# ===== 收藏 =====
def list_favorites():
    items = _load()["favorites"]
    return sorted(items, key=lambda x: x.get("created_at", ""), reverse=True)


def add_favorite(data):
    d = _load()
    item = {
        "id": uuid.uuid4().hex[:12],
        "title": (data.get("title") or "收藏").strip() or "收藏",
        "content": (data.get("content") or "").strip(),
        "created_at": _now(),
    }
    d["favorites"].append(item)
    _save(d)
    return item


def delete_favorite(fid):
    d = _load()
    new = [i for i in d["favorites"] if i["id"] != fid]
    if len(new) != len(d["favorites"]):
        d["favorites"] = new
        _save(d)
        return True
    return False
