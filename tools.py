# tools.py
# 每个工具 = 一段真实能跑的 Python 函数 + 一份"给大模型看的说明书"(JSON Schema)
# Agent 干活靠的就是这两样：函数负责执行，说明书负责让模型"看懂"什么时候该用、怎么传参。

import json
import datetime
import os
import httpx
from urllib.parse import quote
from memory import add_memory, search_memory

# 笔记存到项目目录下的 notes.json
NOTES_FILE = os.path.join(os.path.dirname(__file__), "notes.json")


def calculator(expression: str) -> str:
    """计算一个四则运算表达式，例如 '23 * 4 + 1'。"""
    try:
        # 注意：真实生产环境要用更安全的解析器（比如 ast 限制语法）。
        # 这里本地学习用，已关掉危险内建函数，足够演示。
        result = eval(expression, {"__builtins__": {}}, {})
        return f"计算结果: {result}"
    except Exception as e:
        return f"计算失败: {e}"


def get_current_time() -> str:
    """返回当前的日期和时间。"""
    now = datetime.datetime.now()
    return now.strftime("现在是 %Y-%m-%d %H:%M:%S")


def save_note(title: str, content: str) -> str:
    """把一条笔记保存到本地文件。"""
    notes = []
    if os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            notes = json.load(f)
    notes.append({
        "title": title,
        "content": content,
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
    })
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)
    return f"已保存笔记: {title}"


def read_notes() -> str:
    """读取之前保存的所有笔记。"""
    if not os.path.exists(NOTES_FILE):
        return "还没有保存任何笔记。"
    with open(NOTES_FILE, "r", encoding="utf-8") as f:
        notes = json.load(f)
    if not notes:
        return "笔记本是空的。"
    lines = [f"- {n['title']}: {n['content']}" for n in notes]
    return "已保存的笔记:\n" + "\n".join(lines)


# ===== 联网工具（真实外部 API） =====

def _http_get(url, params=None, headers=None, timeout=15):
    """统一的 GET 请求封装：带超时、跟随重定向、失败抛异常由调用方兜底。"""
    try:
        r = httpx.get(url, params=params, headers=headers,
                      timeout=timeout, follow_redirects=True)
        r.raise_for_status()
        return r
    except Exception as e:
        raise RuntimeError(f"网络请求失败: {e}")


# WMO 天气代码 -> 中文描述（Open-Meteo 返回的是 WMO code）
WMO_CODES = {
    0: "晴", 1: "大致晴朗", 2: "局部多云", 3: "阴",
    45: "有雾", 48: "雾凇",
    51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
    56: "冻毛毛雨", 57: "强冻毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨", 67: "强冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
    80: "小阵雨", 81: "阵雨", 82: "强阵雨",
    85: "小阵雪", 86: "大阵雪",
    95: "雷雨", 96: "雷雨伴冰雹", 99: "强雷雨伴冰雹",
}


def get_weather(city: str) -> str:
    """查询某个城市的当前天气（温度、天气状况、湿度、风速）。城市名支持中文，例如 '北京' 或 'Shanghai'。"""
    try:
        # 1) 城市名 -> 经纬度（Open-Meteo 地理编码，免费无需 Key）
        geo = _http_get("https://geocoding-api.open-meteo.com/v1/search",
                        params={"name": city, "count": 1, "language": "zh", "format": "json"})
        geo_data = geo.json()
        if not geo_data.get("results"):
            return f"没找到城市：{city}，请换个写法试试。"
        loc = geo_data["results"][0]
        lat, lon = loc["latitude"], loc["longitude"]

        # 2) 经纬度 -> 实时天气预报
        fc = _http_get("https://api.open-meteo.com/v1/forecast",
                       params={
                           "latitude": lat, "longitude": lon,
                           "current": "temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m",
                           "timezone": "auto",
                       })
        cur = fc.json()["current"]
        desc = WMO_CODES.get(cur.get("weather_code"), "未知天气")
        name = loc.get("name", city)
        country = loc.get("country", "")
        return (f"{name}（{country}）当前天气：{desc}，"
                f"气温 {cur['temperature_2m']}°C，"
                f"湿度 {cur.get('relative_humidity_2m', '?')}%，"
                f"风速 {cur.get('wind_speed_10m', '?')} km/h")
    except Exception as e:
        return f"查询天气失败: {e}"


def web_search(query: str) -> str:
    """联网搜索资料（基于维基百科公开数据，无需 Key），返回最相关的摘要与来源链接。"""
    headers = {"User-Agent": "mini-agent/1.0 (learning project)"}
    try:
        # 1) 用 opensearch 做真正的"搜索"：自然语言也能匹配相关词条，并直接带摘要与链接
        osr = _http_get("https://zh.wikipedia.org/w/api.php",
                        params={"action": "opensearch", "search": query,
                                "limit": 3, "format": "json"},
                        headers=headers)
        res = osr.json()
        # 返回格式: [query, [标题...], [摘要...], [链接...]]
        if len(res) >= 4 and res[1]:
            lines = [f"· {t}：{d}\n  {l}" for t, d, l in zip(res[1], res[2], res[3])]
            return "搜索结果：\n" + "\n".join(lines)

        # 2) opensearch 没结果，再试 REST 摘要接口（query 恰好是词条名时）
        url = f"https://zh.wikipedia.org/api/rest_v1/page/summary/{quote(query)}"
        r = _http_get(url, headers=headers)
        data = r.json()
        if data.get("extract"):
            page = data.get("content_urls", {}).get("desktop", {}).get("page", "")
            return f"{data.get('title', query)}\n{data['extract']}\n来源: {page}"

        return "未找到相关资料。"
    except Exception as e:
        return (f"搜索失败：{e}。"
                f"（提示：部分网络环境会限制访问维基百科；部署到开放网络后即可正常使用。）")


# ===== 长期记忆工具（让 Agent 跨对话记得用户说过的话） =====

def save_memory(text: str) -> str:
    """把用户透露的重要信息（姓名、偏好、计划、事实等）存入长期记忆，方便以后跨对话回忆。"""
    return add_memory(text)


def search_memory_tool(query: str) -> str:
    """从长期记忆里检索与查询相关的信息，用于主动"回忆"某件事。"""
    return search_memory(query)


# 用名字查函数，Agent Loop 调工具时就靠这个字典
TOOL_FUNCTIONS = {
    "calculator": calculator,
    "get_current_time": get_current_time,
    "save_note": save_note,
    "read_notes": read_notes,
    "get_weather": get_weather,
    "web_search": web_search,
    "save_memory": save_memory,
    "search_memory": search_memory_tool,
}

# 给大模型看的"工具清单"（OpenAI 兼容格式）
# 模型不会真的执行函数，它只根据 description 决定"调不调、传什么参数"
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "计算四则运算表达式，例如 '23 * 4 + 1'。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式"}
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "获取当前的日期和时间。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_note",
            "description": "保存一条笔记，需要提供标题和内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "笔记标题"},
                    "content": {"type": "string", "description": "笔记内容"},
                },
                "required": ["title", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_notes",
            "description": "读取所有已保存的笔记。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询某个城市的当前天气（温度、天气状况、湿度、风速）。支持中文城市名，例如 '北京'、'上海'、'Tokyo'。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称，可用中文或英文"}
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "联网搜索资料（基于维基百科公开数据），返回最相关的摘要和来源链接。适合查概念、人物、地点等百科知识。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "把用户透露的重要长期信息记住，例如姓名、喜好、计划、关键事实。之后即使开新对话，Agent 也能回忆起来。",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "要记住的信息，用完整一句话描述，例如『用户叫小明，喜欢喝咖啡』"}
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "从长期记忆中检索与查询相关的信息，用于主动回忆用户之前说过的话。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "要回忆的内容关键词，例如『我叫什么』『我的偏好』"}
                },
                "required": ["query"],
            },
        },
    },
]
