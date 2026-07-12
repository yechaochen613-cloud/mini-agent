"""
定时任务（Schedules）—— 让智能体按节奏自动干活。

存储：DATA_DIR/schedules.json（与对话/连接器同目录，Render 挂 Disk 后可持久）。
执行：免费版没有常驻 cron，所以由前端在页面打开时按 setInterval 轮询，
      发现 next_run <= now 就自动把 prompt 发给对话（send()），并回写 last_run / 重算 next_run。
      后端只负责「存 + 算下次运行时间 + 提供 CRUD」。
"""

import os
import json
import time
import uuid

from storage import DATA_DIR

SCHEDULES_FILE = os.path.join(DATA_DIR, "schedules.json")

# recurrence.type 取值：
#   "interval" -> 每 minutes 分钟跑一次
#   "daily"    -> 每天 time(HH:MM) 跑一次
#   "weekly"   -> 每周 weekday(0=周一..6=周日) + time(HH:MM) 跑一次


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _load():
    if not os.path.exists(SCHEDULES_FILE):
        return []
    try:
        with open(SCHEDULES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save(items):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SCHEDULES_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def compute_next_run(rec, from_ts=None):
    """根据 recurrence 算出下一次运行的时间戳（秒）。from_ts 不传则用当前时间。"""
    from_ts = from_ts or time.time()
    rec = rec or {}
    rtype = rec.get("type", "interval")
    try:
        if rtype == "interval":
            minutes = max(1, int(rec.get("minutes", 60)))
            return from_ts + minutes * 60
        elif rtype == "daily":
            return _next_daily(rec.get("time", "09:00"), from_ts)
        elif rtype == "weekly":
            return _next_weekly(int(rec.get("weekday", 0)), rec.get("time", "09:00"), from_ts)
    except Exception:
        pass
    return from_ts + 3600


def _next_daily(hhmm, from_ts):
    h, m = _parse_hhmm(hhmm)
    now = time.localtime(from_ts)
    cand = time.mktime((now.tm_year, now.tm_mon, now.tm_mday, h, m, 0, 0, 0, -1))
    if cand <= from_ts:
        cand = time.mktime((now.tm_year, now.tm_mon, now.tm_mday + 1, h, m, 0, 0, 0, -1))
    return cand


def _next_weekly(weekday, hhmm, from_ts):
    h, m = _parse_hhmm(hhmm)
    # time.struct_time.tm_wday: 0=周一..6=周日，与我们的 weekday 定义一致
    now = time.localtime(from_ts)
    days_ahead = (weekday - now.tm_wday) % 7
    if days_ahead == 0:
        cand = time.mktime((now.tm_year, now.tm_mon, now.tm_mday, h, m, 0, 0, 0, -1))
        if cand <= from_ts:
            days_ahead = 7
    target_day = now.tm_mday + days_ahead
    cand = time.mktime((now.tm_year, now.tm_mon, target_day, h, m, 0, 0, 0, -1))
    return cand


def _parse_hhmm(hhmm):
    try:
        h, m = str(hhmm).split(":")
        return int(h), int(m)
    except Exception:
        return 9, 0


def list_schedules():
    return _load()


def get_schedule(sid):
    for s in _load():
        if s["id"] == sid:
            return s
    return None


def create_schedule(data):
    items = _load()
    rec = data.get("recurrence", {}) or {}
    rec.setdefault("type", "interval")
    if rec["type"] == "interval":
        rec["minutes"] = max(1, int(rec.get("minutes", 60)))
    sid = uuid.uuid4().hex[:12]
    now = _now()
    item = {
        "id": sid,
        "title": (data.get("title") or "定时任务").strip() or "定时任务",
        "prompt": (data.get("prompt") or "").strip(),
        "recurrence": rec,
        "enabled": True,
        "created_at": now,
        "last_run": None,
        "next_run": compute_next_run(rec),
    }
    items.append(item)
    _save(items)
    return item


def update_schedule(sid, data):
    items = _load()
    for s in items:
        if s["id"] == sid:
            if "title" in data:
                s["title"] = data["title"].strip() or s["title"]
            if "prompt" in data:
                s["prompt"] = data["prompt"]
            if "recurrence" in data and data["recurrence"]:
                rec = data["recurrence"]
                if rec.get("type") == "interval":
                    rec["minutes"] = max(1, int(rec.get("minutes", 60)))
                s["recurrence"] = rec
                s["next_run"] = compute_next_run(rec, s.get("last_run_ts"))
            if "enabled" in data:
                s["enabled"] = bool(data["enabled"])
            _save(items)
            return s
    return None


def delete_schedule(sid):
    items = _load()
    new = [s for s in items if s["id"] != sid]
    if len(new) != len(items):
        _save(new)
        return True
    return False


def mark_run(sid, ts=None):
    """任务执行后回写 last_run，并按 recurrence 重算 next_run。"""
    ts = ts or time.time()
    items = _load()
    for s in items:
        if s["id"] == sid:
            s["last_run"] = _now()
            s["last_run_ts"] = ts
            if s.get("enabled", True):
                s["next_run"] = compute_next_run(s["recurrence"], ts)
            _save(items)
            return s
    return None
