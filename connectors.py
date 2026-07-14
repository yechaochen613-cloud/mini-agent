"""
连接器（Connectors）—— 管理可接入的应用与 API，参考 Manus 的连接器面板。

每个连接器有：id / name / description / icon / category / status(connected/disconnected)。
状态持久化到 SQLite（与 chat_history 共用同一个 DB，表 connectors）。
"""

import os
import json
import time
import hashlib

from db import connect, q, exec, fetchall, fetchone, create_table_if_not_exists

# ── 连接器注册表（参考 Manus 截图中的全部 8 个）─────────────────────
CONNECTORS = [
    {
        "id": "browser",
        "name": "My Browser",
        "desc": "在你自己的浏览器上访问网页",
        "icon": "browser",       # 对应前端 SVG icon name
        "category": "built-in",
        "color": "#4285F4",      # 品牌色
    },
    {
        "id": "gmail",
        "name": "Gmail",
        "desc": "撰写邮件，搜索会话并快速生成摘要",
        "icon": "gmail",
        "category": "google",
        "color": "#EA4335",
        "url": "https://mail.google.com",
    },
    {
        "id": "github",
        "name": "GitHub",
        "desc": "管理代码仓库，协作开发与代码审查",
        "icon": "github",
        "category": "dev",
        "color": "#171515",
    },
    {
        "id": "instagram",
        "name": "Instagram",
        "desc": "生成并发布 Instagram 帖子、限时动态或 Reels",
        "icon": "instagram",
        "category": "social",
        "color": "#E1306C",
    },
    {
        "id": "workspace",
        "name": "Google Workspace",
        "desc": "快速访问文件、智能搜索内容，并让 Mini Agent 协助你更高效地管理文档",
        "icon": "workspace",
        "category": "google",
        "color": "#34A853",
    },
    {
        "id": "meta_ads",
        "name": "Meta Ads Manager",
        "desc": "自动化生成广告洞察与优化方案，以节省时间并最大化利润",
        "icon": "metaads",
        "category": "marketing",
        "color": "#0080FF",
    },
    {
        "id": "calendar",
        "name": "Google Calendar",
        "desc": "查看日程安排，优化时间与活动管理",
        "icon": "calendar",
        "category": "google",
        "color": "#4285F4",
    },
    {
        "id": "notion",
        "name": "Notion",
        "desc": "搜索和更新内容，实现自动化流程",
        "icon": "notion",
        "category": "productivity",
        "color": "#000000",
    },
]

# id → connector dict 快查
_BY_ID = {c["id"]: c for c in CONNECTORS}


def _init_connectors_table():
    """确保 connectors 表存在（pg / sqlite 自动适配）。"""
    _SQLITE_DDL = """
    CREATE TABLE IF NOT EXISTS connectors (
        id      TEXT PRIMARY KEY,
        connected INTEGER NOT NULL DEFAULT 0,
        config  TEXT DEFAULT '{}',
        connected_at TEXT,
        updated_at TEXT
    )
    """
    _PG_DDL = """
    CREATE TABLE IF NOT EXISTS connectors (
        id      TEXT PRIMARY KEY,
        connected INTEGER NOT NULL DEFAULT 0,
        config  TEXT DEFAULT '{}',
        connected_at TEXT,
        updated_at TEXT
    )
    """
    conn = connect()
    create_table_if_not_exists(conn, "connectors", _SQLITE_DDL, _PG_DDL)
    conn.close()


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


# ── 公开 API ───────────────────────────────────────────────────────

def list_connectors():
    """返回全部连接器列表，每个带 connected 状态。"""
    conn = connect()
    rows = exec(conn,
        "SELECT id, connected, config, connected_at FROM connectors"
    ).fetchall()
    conn.close()
    status = {r[0]: {"connected": bool(r[1]), "config": json.loads(r[2] or "{}"), "connected_at": r[3]} for r in rows}

    result = []
    for c in CONNECTORS:
        s = status.get(c["id"], {"connected": False, "config": {}, "connected_at": None})
        entry = {**c, **s}
        result.append(entry)
    return result


def get_connector(conn_id):
    """获取单个连接器详情。"""
    if conn_id not in _BY_ID:
        return None
    all_c = list_connectors()
    for c in all_c:
        if c["id"] == conn_id:
            return c
    return None


def connect_connector(conn_id, config=None):
    """
    连接一个连接器。
    - browser: 无需配置，直接标记已连接（内置能力）
    - github: 需要 token
    - gmail: 需要 OAuth 或 API key
    - 其他: 暂时 mock 连接（记录状态）
    返回 {ok, message, connector}
    """
    if conn_id not in _BY_ID:
        return {"ok": False, "message": f"未知连接器: {conn_id}"}

    cfg = config or {}
    conn = connect()
    now = _now()

    # 特殊处理: browser 内置可用
    if conn_id == "browser":
        exec(conn,
            "INSERT OR REPLACE INTO connectors (id, connected, config, connected_at, updated_at) VALUES (?,?,?,?,?)",
            (conn_id, 1, json.dumps(cfg), now, now),
        )
        conn.close()
        return get_connector(conn_id)

    # GitHub: 校验 token 格式
    if conn_id == "github":
        token = cfg.get("token", "")
        if not token or len(token) < 10:
            conn.close()
            return {"ok": False, "message": "请提供有效的 GitHub Personal Access Token"}
        exec(conn,
            "INSERT OR REPLACE INTO connectors (id, connected, config, connected_at, updated_at) VALUES (?,?,?,?,?)",
            (conn_id, 1, json.dumps(cfg), now, now),
        )
        conn.close()
        return get_connector(conn_id)

    # Gmail: 需要 credentials
    if conn_id == "gmail":
        if not cfg.get("credentials") and not cfg.get("api_key"):
            conn.close()
            return {"ok": False, "message": "请提供 Gmail API 凭据或 OAuth 授权"}
        exec(conn,
            "INSERT OR REPLACE INTO connectors (id, connected, config, connected_at, updated_at) VALUES (?,?,?,?,?)",
            (conn_id, 1, json.dumps(cfg), now, now),
        )
        conn.close()
        return get_connector(conn_id)

    # 其余: 直接记录连接状态（mock）
    exec(conn,
        "INSERT OR REPLACE INTO connectors (id, connected, config, connected_at, updated_at) VALUES (?,?,?,?,?)",
        (conn_id, 1, json.dumps(cfg), now, now),
    )
    conn.close()
    return get_connector(conn_id)


def disconnect_connector(conn_id):
    """断开一个连接器。"""
    if conn_id not in _BY_ID:
        return {"ok": False, "message": f"未知连接器: {conn_id}"}
    conn = connect()
    exec(conn,
        "UPDATE connectors SET connected=0, config='{}', connected_at=NULL, updated_at=? WHERE id=?",
        (_now(), conn_id),
    )
    conn.close()
    return get_connector(conn_id)


# ── 连接器能力端点（被 api.py 路由调用）───────────────────────────

def github_action(action, params=None):
    """GitHub 能力：搜索仓库/问题等。需要先 connect 并提供 token。"""
    p = params or {}
    c = get_connector("github")
    if not c or not c.get("connected"):
        return {"error": "GitHub 未连接，请先在连接器面板中添加 Token"}
    token = c["config"].get("token", "")
    import urllib.request, urllib.error, json as _j
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Mini-Agent/1.0",
    }
    base = "https://api.github.com"

    try:
        if action == "search_repos":
            q = p.get("q", "")
            url = f"{base}/search/repositories?q={urllib.parse.quote(q)}&per_page=10"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = _j.loads(resp.read())
                return {"results": [
                    {"full_name": item["full_name"], "description": item.get("description",""), "stars": item["stargazers_count"],
                     "language": item.get("language"), "url": item["html_url"]}
                    for item in data.get("items", [])
                ]}
        elif action == "user_repos":
            url = f"{base}/user/repos?per_page=10&sort=updated"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = _j.loads(resp.read())
                return {"repos": [
                    {"full_name": item["full_name"], "description": item.get("description",""),
                     "updated_at": item.get("updated_at"), "url": item["html_url"]}
                    for item in data
                ]}
        elif action == "search_issues":
            q = p.get("q", "")
            url = f"{base}/search/issues?q={urllib.parse.quote(q)}&per_page=10"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = _j.loads(resp.read())
                return {"issues": [
                    {"title": item["title"], "number": item["number"], "state": item["state"],
                     "repo": item.get("repository_url","").replace("https://api.github.com/repos/", ""),
                     "url": item["html_url"]}
                    for item in data.get("items", [])
                ]}
        else:
            return {"error": f"未知 GitHub 操作: {action}"}
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        return {"error": f"GitHub API 错误 ({e.code}): {body}"}
    except Exception as e:
        return {"error": f"GitHub 请求失败: {e}"}


def calendar_action(action, params=None):
    """Calendar 能力（mock 或真实 Google Calendar API）。"""
    p = params or {}
    c = get_connector("calendar")
    if not c or not c.get("connected"):
        return {"error": "Calendar 未连接"}

    # Mock 模式返回演示数据
    import agent_langgraph
    # 检查全局 agent 是否在 mock 模式（间接判断）
    if os.getenv("MOCK", "").lower() == "true":
        if action == "list_events":
            return {"events": [
                {"title": "团队周会", "time": "今天 14:00-15:00", "location": "会议室 A"},
                {"title": "产品评审", "time": "明天 10:00-11:30", "location": "线上"},
                {"title": "代码重构计划", "time": "后天 16:00-17:00", "location": ""},
            ]}
        elif action == "add_event":
            title = p.get("title", "新事件")
            return {"ok": True, "message": f"(演示模式) 已创建日历事件「{title}」"}
        return {"error": f"未知操作: {action}"}

    # 真实模式需 google-auth + google-api-python-client
    return {"error": "Calendar 真实 API 需要安装 google-auth 和 google-api-python-client 并完成 OAuth 授权"}


def notion_action(action, params=None):
    """Notion 能力（复用已有 notes 工具）。"""
    p = params or {}
    c = get_connector("notion")
    if not c or not c.get("connected"):
        return {"error": "Notion 未连接"}
    # 复用已有的笔记功能
    from tools import list_notes, save_note, delete_note
    if action == "list":
        return {"notes": list_notes()}
    elif action == "save":
        content = p.get("content", "")
        return save_note(content)
    elif action == "delete":
        note_id = p.get("id")
        return delete_note(note_id)
    return {"error": f"未知 Notion 操作: {action}"}


import urllib.parse

# 模块加载时确保 connectors 表存在
_init_connectors_table()
