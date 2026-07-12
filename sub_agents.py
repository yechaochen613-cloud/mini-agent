"""
子智能体（Sub-Agents）—— 可管理的专用智能体。

每个子智能体有：id / name / role(角色提示词) / tools(允许使用的工具子集) /
color / icon / created_at。
存储：DATA_DIR/sub_agents.json。
运行：run_sub_agent() 用子智能体的角色提示词 + 受限工具集，起一个独立的 Agent 实例跑任务，
      主对话可通过 delegate_subagent 工具把子任务委派给它（见 tools.py）。
"""

import os
import json
import time
import uuid

from storage import DATA_DIR

SUB_AGENTS_FILE = os.path.join(DATA_DIR, "sub_agents.json")

# 默认种子子智能体（首次启动、文件为空时写入）
_SEED = [
    {
        "name": "写作助手",
        "role": "你擅长各类中文写作：润色、扩写、总结、写邮件与文案。输出清晰、有结构、符合中文表达习惯。",
        "tools": ["save_note", "read_notes", "web_search", "get_current_time"],
        "color": "#a855f7",
        "icon": "✍️",
    },
    {
        "name": "代码助手",
        "role": "你是一名资深工程师，擅长写与调试 Python/前端代码、解释技术概念、给出可运行示例。",
        "tools": ["run_code", "calculator", "web_search", "get_current_time"],
        "color": "#22d3ee",
        "icon": "💻",
    },
    {
        "name": "研究助手",
        "role": "你善于联网检索、交叉验证信息、整理要点并给出带出处的简报。",
        "tools": ["web_search", "get_current_time", "save_note", "search_uploaded_documents"],
        "color": "#34d399",
        "icon": "🔬",
    },
]


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _load():
    if not os.path.exists(SUB_AGENTS_FILE):
        return None
    try:
        with open(SUB_AGENTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save(items):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SUB_AGENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def _ensure_seed():
    items = _load()
    if items is None:
        seeded = []
        now = _now()
        for s in _SEED:
            seeded.append({
                "id": uuid.uuid4().hex[:12],
                "name": s["name"],
                "role": s["role"],
                "tools": s["tools"],
                "color": s["color"],
                "icon": s["icon"],
                "created_at": now,
                "enabled": True,
            })
        _save(seeded)
        return seeded
    return items


def list_sub_agents():
    return _ensure_seed()


def get_sub_agent(sid):
    for s in list_sub_agents():
        if s["id"] == sid:
            return s
    return None


def create_sub_agent(data):
    items = list_sub_agents()
    item = {
        "id": uuid.uuid4().hex[:12],
        "name": (data.get("name") or "新子智能体").strip() or "新子智能体",
        "role": (data.get("role") or "").strip(),
        "tools": list(data.get("tools") or []),
        "color": data.get("color") or "#a855f7",
        "icon": data.get("icon") or "🤖",
        "created_at": _now(),
        "enabled": True,
    }
    items.append(item)
    _save(items)
    return item


def update_sub_agent(sid, data):
    items = list_sub_agents()
    for s in items:
        if s["id"] == sid:
            if "name" in data:
                s["name"] = data["name"].strip() or s["name"]
            if "role" in data:
                s["role"] = data["role"]
            if "tools" in data:
                s["tools"] = list(data["tools"] or [])
            if "color" in data:
                s["color"] = data["color"]
            if "icon" in data:
                s["icon"] = data["icon"]
            if "enabled" in data:
                s["enabled"] = bool(data["enabled"])
            _save(items)
            return s
    return None


def delete_sub_agent(sid):
    items = list_sub_agents()
    new = [s for s in items if s["id"] != sid]
    if len(new) != len(items):
        _save(new)
        return True
    return False


def run_sub_agent(sub_id, task, session_id=None, mock=False):
    """运行一个子智能体处理 task，返回回复文本。

    - mock=True：返回基于角色模拟的回复（无需 API key，部署演示可用）。
    - mock=False：起独立 Agent，用子智能体的角色提示词 + 受限工具集跑 run_trace。
    """
    sub = get_sub_agent(sub_id)
    if not sub:
        return f"（未找到子智能体：{sub_id}）"
    name = sub["name"]

    if mock or os.getenv("MOCK", "false").lower() == "true":
        return (
            f"（子智能体「{name}」已处理）\n"
            f"任务：{task}\n"
            f"作为{name}，我的处理思路：{sub.get('role','')[:60]}……"
            f"此处为演示回复，接入真实模型后将给出完整结果。"
        )

    # 真实模式：起一个受限 Agent
    from agent_langgraph import Agent
    import os as _os
    agent = Agent(
        api_key=_os.getenv("OPENAI_API_KEY"),
        base_url=_os.getenv("OPENAI_BASE_URL"),
        model=_os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        mock=False,
    )
    allowed = set(sub.get("tools") or [])
    if allowed:
        agent._all_tools = [t for t in agent._all_tools if t.name in allowed]
        agent._tool_map = {t.name: t for t in agent._all_tools}
        agent.tool_schemas = [s for s in agent.tool_schemas if s["function"]["name"] in allowed]
        agent._llm_cache.clear()
        try:
            agent._llm_for(agent.model)
        except Exception:
            pass
    role_prompt = (
        f"你是一个名为「{name}」的专用子智能体。\n"
        f"你的专业定位：{sub.get('role','')}\n"
        f"请严格围绕你的定位完成任务，输出专业、可直接使用的结果。"
    )
    agent._system_override = role_prompt
    sid = session_id or ("sub_" + uuid.uuid4().hex[:10])
    try:
        res = agent.run_trace(sid, task, max_steps=4)
        return res.get("reply") or "（子智能体未返回内容）"
    except Exception as e:
        return f"（子智能体运行出错：{e}）"
