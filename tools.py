# tools.py
# 每个工具 = 一段真实能跑的 Python 函数 + 一份"给大模型看的说明书"(JSON Schema)
# Agent 干活靠的就是这两样：函数负责执行，说明书负责让模型"看懂"什么时候该用、怎么传参。

import json
import ast
import math
import datetime
import os
import sys
import subprocess
import tempfile
import httpx
from urllib.parse import quote
from memory import add_memory, search_memory
from tutor import (
    get_profile as _get_profile,
    update_profile as _update_profile,
    analyze_exam_paper as _analyze_exam_paper,
    make_study_plan as _make_study_plan,
)

from storage import DATA_DIR

# 笔记持久化到统一数据目录（挂 Render Disk 后不丢）
NOTES_FILE = os.path.join(DATA_DIR, "notes.json")


_ALLOWED_MATH = {
    "abs": abs, "round": round, "min": min, "max": max, "pow": pow,
    "sqrt": math.sqrt, "log": math.log, "log10": math.log10,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "floor": math.floor, "ceil": math.ceil,
    "pi": math.pi, "e": math.e,
}


def _safe_eval(node):
    """只允许数字、四则运算、括号、一元正负、白名单数学函数——彻底杜绝 eval 任意代码执行。"""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("只允许数字常量")
    if isinstance(node, ast.BinOp):
        left, right = _safe_eval(node.left), _safe_eval(node.right)
        op = node.op
        if isinstance(op, ast.Add):
            return left + right
        if isinstance(op, ast.Sub):
            return left - right
        if isinstance(op, ast.Mult):
            return left * right
        if isinstance(op, ast.Div):
            return left / right
        if isinstance(op, ast.FloorDiv):
            return left // right
        if isinstance(op, ast.Mod):
            return left % right
        if isinstance(op, ast.Pow):
            if right > 1000:
                raise ValueError("指数过大，已拒绝")
            return left ** right
        raise ValueError("不支持的运算符")
    if isinstance(node, ast.UnaryOp):
        val = _safe_eval(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +val
        if isinstance(node.op, ast.USub):
            return -val
        raise ValueError("不支持的一元运算")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_MATH:
            raise ValueError("不允许调用该函数/变量")
        args = [_safe_eval(a) for a in node.args]
        return _ALLOWED_MATH[node.func.id](*args)
    if isinstance(node, ast.Name):
        if node.id in _ALLOWED_MATH:
            return _ALLOWED_MATH[node.id]
        raise ValueError(f"不允许的变量: {node.id}")
    raise ValueError("不支持的表达式")


def calculator(expression: str) -> str:
    """计算四则运算与常见数学函数，例如 '23 * 4 + 1' 或 'sqrt(2) + pi'。"""
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree)
        return f"计算结果: {result}"
    except Exception as e:
        return f"计算失败: {e}"


def get_current_time() -> str:
    """返回当前的日期和时间（北京时间，Asia/Shanghai）。"""
    from zoneinfo import ZoneInfo
    now = datetime.datetime.now(ZoneInfo("Asia/Shanghai"))
    return now.strftime("现在是 %Y-%m-%d %H:%M:%S（北京时间）")


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


# ===== 代码执行沙箱（让 Agent 能算数据、画图、生成文件，对标 Manus 的"会干活"） =====
# 在受限子进程里跑 Python，带超时；stdout/stderr 回传。仅用于可信输入——这是学习项目，
# 没有做完整的容器隔离，生产环境请换成 Docker/gVisor 等真沙箱。
# 安全的子进程环境变量：只透传无害系统变量，剔除一切密钥（API Key / 数据库 URL / Token / 密码）。
# 避免把 OPENAI_API_KEY、DATABASE_URL 等机密泄露给被执行的用户代码（旧实现会全量透传）。
_SAFE_ENV_KEYS = (
    "PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LANGUAGE",
    "TMPDIR", "TEMP", "TMP", "SYSTEMROOT", "SYSTEMDRIVE", "PATHEXT",
    "COMSPEC", "SHELL", "PWD", "TERM",
)
_SECRET_HINTS = ("KEY", "SECRET", "TOKEN", "PASSWORD", "PASSWD", "DATABASE", "CREDENTIAL", "PRIVATE")


def _safe_subprocess_env() -> dict:
    env: dict = {}
    for k, v in os.environ.items():
        if k in _SAFE_ENV_KEYS:
            env[k] = v
            continue
        # 其余只允许明显无害的普通变量，任何疑似密钥的一律剔除
        if k.isupper() and not any(h in k for h in _SECRET_HINTS):
            env[k] = v
    env["PYTHONPATH"] = ""
    return env


def run_code(code: str, timeout: int = 15) -> str:
    """在限时子进程里执行 Python 代码，返回 stdout/stderr。适合数据计算、画图、生成文件等。"""
    code = (code or "").strip()
    if not code:
        return "（没有提供代码）"
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            path = f.name
        try:
            proc = subprocess.run(
                [sys.executable, path],
                capture_output=True, text=True,
                timeout=timeout, cwd=DATA_DIR,
                env=_safe_subprocess_env(),
            )
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        out = (proc.stdout or "")
        err = (proc.stderr or "")
        if proc.returncode != 0:
            return f"⚠ 执行出错（退出码 {proc.returncode}）：\n{(err or out)[:2000]}"
        combined = (out + err).strip()
        return combined[:4000] or "（代码执行成功，无输出）"
    except subprocess.TimeoutExpired:
        return f"⚠ 执行超时（超过 {timeout} 秒），已终止。"
    except Exception as e:
        return f"⚠ 执行失败：{e}"


# ===== 长期记忆工具（让 Agent 跨对话记得用户说过的话） =====

def save_memory(text: str) -> str:
    """把用户透露的重要信息（姓名、偏好、计划、事实等）存入长期记忆，方便以后跨对话回忆。"""
    return add_memory(text)


def search_memory_tool(query: str) -> str:
    """从长期记忆里检索与查询相关的信息，用于主动"回忆"某件事。"""
    return search_memory(query)


# ===== 文档理解工具（多格式解析 + 跨文档检索/比对） =====
# 重逻辑都在 documents.py，这里只做"给模型看的函数签名 + 字符串返回"的薄封装。
from documents import (
    list_documents as _list_documents,
    search_documents as _search_documents,
    read_document as _read_document,
    extract_tables as _extract_tables,
    extract_clauses as _extract_clauses,
    compare_documents as _compare_documents,
)


def list_uploaded_documents() -> str:
    """列出当前已上传的文档（名称、类型、字数、表格数、分块数、条款数）。上传文档后用它查看每篇的 id。"""
    return _list_documents()


def search_uploaded_documents(query: str, top_k: int = 5) -> str:
    """跨所有已上传文档做语义/关键词检索，返回最相关片段、来源文档与相关度。适合『在文档里找…』『某条款在哪』。"""
    return _search_documents(query, top_k=top_k)


def read_document(doc_id: str, max_chars: int = 4000) -> str:
    """读取某篇文档的正文（默认前 4000 字，长文档会提示用检索定位）。doc_id 来自 list_uploaded_documents。"""
    return _read_document(doc_id, max_chars=max_chars)


def extract_document_tables(doc_id: str) -> str:
    """提取某篇文档里的所有表格（表头 + 数据），以可读格式返回。doc_id 来自 list_uploaded_documents。"""
    return _extract_tables(doc_id)


def extract_document_clauses(doc_id: str, keyword: str = "") -> str:
    """提取某篇文档里的条款（第X条 / Article X / 多级编号等）。可传 keyword 过滤，例如只关心『保密』『赔偿』。"""
    return _extract_clauses(doc_id, keyword=keyword or None)


def compare_two_documents(a: str, b: str, topic: str = "") -> str:
    """跨文档关联比对与交叉验证：找出两篇文档最相似的片段（重叠/一致候选），并扫描数值差异。a、b 为文档 id；topic 可选，用于聚焦主题。"""
    return _compare_documents(a, b, topic=topic or None)


def delegate_subagent(sub_agent_id: str, task: str) -> str:
    """把当前任务委派给一个已创建的子智能体（Sub-Agent）处理。sub_agent_id 为子智能体 id（在「子智能体」面板可看到）；task 为交给它做的具体任务描述。返回子智能体的处理结果文本。适合把专业子任务（如写作、代码、研究）交给对应子智能体完成。"""
    from sub_agents import run_sub_agent
    mock = os.getenv("MOCK", "false").lower() == "true"
    return run_sub_agent(sub_agent_id, task, session_id=None, mock=mock)


# ===== 教辅工具（私人家教：学情档案 + 试卷分析 + 提升计划） =====

def get_learning_profile() -> str:
    """读取当前学生的学情档案（姓名、年级、各科掌握度、薄弱点、优势、目标）。家教对话中用它了解学生底数。"""
    return json.dumps(_get_profile(), ensure_ascii=False)


def update_learning_profile(profile_json: str) -> str:
    """更新学情档案。传入 JSON 字符串，可包含：name(姓名)、grade(年级)、subjects(学科:掌握度0-100的字典)、weak_points(薄弱点列表)、strengths(优势列表)、goals(目标列表)。会自动合并去重。"""
    try:
        data = json.loads(profile_json)
    except Exception as e:
        return f"参数不是合法 JSON：{e}"
    _update_profile(data)
    return "已更新学情档案 ✅"


def analyze_exam_paper(doc_id: str) -> str:
    """分析一篇已上传的试卷/作业（doc_id 来自 list_uploaded_documents）。自动提取文字、评估各科掌握度与薄弱点、给出针对性建议，并写入学情档案。返回人类可读的分析摘要。"""
    return _analyze_exam_paper(doc_id)


def make_study_plan(goal: str = "", days: int = 14) -> str:
    """基于学情档案与历史试卷，生成针对性提升计划。goal 为目标描述（可空），days 为周期天数（默认14）。返回 JSON 计划（含每日主题与任务、给家长的陪伴建议）。"""
    return _make_study_plan(goal=goal, days=days)


# 用名字查函数，Agent Loop 调工具时就靠这个字典
TOOL_FUNCTIONS = {
    "calculator": calculator,
    "run_code": run_code,
    "get_current_time": get_current_time,
    "save_note": save_note,
    "read_notes": read_notes,
    "get_weather": get_weather,
    "web_search": web_search,
    "save_memory": save_memory,
    "search_memory": search_memory_tool,
    "list_uploaded_documents": list_uploaded_documents,
    "search_uploaded_documents": search_uploaded_documents,
    "read_document": read_document,
    "extract_document_tables": extract_document_tables,
    "extract_document_clauses": extract_document_clauses,
    "compare_two_documents": compare_two_documents,
    "delegate_subagent": delegate_subagent,
    "get_learning_profile": get_learning_profile,
    "update_learning_profile": update_learning_profile,
    "analyze_exam_paper": analyze_exam_paper,
    "make_study_plan": make_study_plan,
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
                "name": "run_code",
                "description": "在 Python 沙箱里执行代码并返回输出，用于数据计算、画图、生成文件等复杂任务。支持 numpy/pandas/matplotlib 等已安装库。传入要执行的完整代码（可放在 ```python 代码块``` 里）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "要执行的 Python 代码"},
                        "timeout": {"type": "integer", "description": "超时秒数，默认 15"}
                    },
                    "required": ["code"],
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
    {
        "type": "function",
        "function": {
            "name": "list_uploaded_documents",
            "description": "列出当前已上传的文档（名称、类型、字数、表格数、分块数、条款数）。上传文档后先用它拿到每篇的 id，再调用其它文档工具。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_uploaded_documents",
            "description": "跨所有已上传文档做语义/关键词检索，返回最相关片段、来源文档与相关度。适合『在文档里找某内容』『某条款在哪篇』。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索内容，例如『违约责任』『交付时间』"},
                    "top_k": {"type": "integer", "description": "返回最相关片段数，默认 5"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_document",
            "description": "读取某篇文档的正文（默认前 4000 字，长文档会提示用检索定位）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "文档 id（来自 list_uploaded_documents）"},
                    "max_chars": {"type": "integer", "description": "最多读取字数，默认 4000"}
                },
                "required": ["doc_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_document_tables",
            "description": "提取某篇文档里的所有表格（表头 + 数据），以可读格式返回。",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "文档 id（来自 list_uploaded_documents）"}
                },
                "required": ["doc_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_document_clauses",
            "description": "提取某篇文档里的条款（第X条 / Article X / 多级编号等）。可传 keyword 过滤，例如只关心『保密』『赔偿』。",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "文档 id（来自 list_uploaded_documents）"},
                    "keyword": {"type": "string", "description": "可选关键词过滤，例如『保密』『赔偿』"}
                },
                "required": ["doc_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_two_documents",
            "description": "跨文档关联比对与交叉验证：找出两篇文档最相似的片段（重叠/一致候选），并扫描数值差异。a、b 为文档 id；topic 可选，用于聚焦主题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "string", "description": "文档 A 的 id"},
                    "b": {"type": "string", "description": "文档 B 的 id"},
                    "topic": {"type": "string", "description": "可选，聚焦主题，例如『交付时间』"}
                },
                "required": ["a", "b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delegate_subagent",
            "description": "把当前任务委派给一个已创建的子智能体（Sub-Agent）处理。适合把专业子任务（如写作、代码、研究）交给对应子智能体完成。sub_agent_id 为子智能体 id（在「子智能体」面板可看到）；task 为交给它做的具体任务描述。返回子智能体的处理结果。",
            "parameters": {
                "type": "object",
                "properties": {
                    "sub_agent_id": {"type": "string", "description": "子智能体 id（来自「子智能体」面板列表）"},
                    "task": {"type": "string", "description": "要交给子智能体做的具体任务描述"}
                },
                "required": ["sub_agent_id", "task"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_learning_profile",
            "description": "读取当前学生的学情档案，返回姓名/年级/各科掌握度/薄弱点/优势/目标。开始辅导或想了解学生底数时调用。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_learning_profile",
            "description": "更新学情档案。传 JSON，可含 name(姓名)、grade(年级)、subjects(学科:掌握度0-100字典)、weak_points(薄弱点列表)、strengths(优势列表)、goals(目标列表)。自动合并去重。",
            "parameters": {
                "type": "object",
                "properties": {
                    "profile_json": {"type": "string", "description": "学情档案 JSON 字符串，例如 '{\"grade\":\"初二\",\"weak_points\":[\"二次函数\"],\"subjects\":{\"数学\":65}}'"}
                },
                "required": ["profile_json"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_exam_paper",
            "description": "分析一篇已上传的试卷/作业（doc_id 来自 list_uploaded_documents）。自动提取文字、评估掌握度与薄弱点、给建议，并写入学情档案。返回人类可读的分析摘要。学生上传试卷后调用它。",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "试卷文档 id（来自 list_uploaded_documents）"}
                },
                "required": ["doc_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "make_study_plan",
            "description": "基于学情档案与历史试卷生成针对性提升计划。goal 为目标(可空)，days 为周期天数(默认14)。返回 JSON 计划（每日主题/任务、家长陪伴建议）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "学习目标，例如『期末数学提高到85分』（可空）"},
                    "days": {"type": "integer", "description": "计划周期天数，默认 14"}
                },
            },
        },
    },
]
