# tutor.py —— 私人家教核心模块（学情档案 + 试卷分析 + 针对性提升计划）
#
# 设计目标（对应 Phase 2）：
#   1) 结构化学情档案：记录学生姓名/年级、各科掌握度(0-100)、薄弱点、目标。
#      存于 PostgreSQL（线上持久化，重启/redeploy 不丢），本地回退 SQLite。
#   2) 上传试卷分析：复用 documents.py 解析 PDF/Word/图片 → 提取文字 →
#      用大模型产出结构化分析（学科、得分估算、知识点掌握度、薄弱点、建议），
#      并自动写入学情档案 + 存入 exam_papers 表（持久化）。
#   3) 针对性提升计划：综合档案薄弱点 + 历史试卷，生成可执行的周/日计划。
#
# 复用：
#   - db.py 的统一数据库层（PostgreSQL / SQLite 自动切换 + 方言转换）
#   - documents.py 的 get_document / read_document（已解析的试卷文本）
#   - 视觉分析复用 /vision 的 ChatOpenAI 调用方式（glm-4v-flash 处理扫描件图片）

import os
import re
import json
import base64
import datetime
import uuid

from db import connect, q, exec, fetchall, fetchone, create_table_if_not_exists
from documents import get_document


# ===== 学情档案默认结构 =====
DEFAULT_PROFILE = {
    "name": "",          # 学生姓名
    "grade": "",         # 年级，如 "初二"
    "subjects": {},      # {学科: 掌握度0-100}，如 {"数学": 72, "英语": 85}
    "weak_points": [],   # 薄弱点标签列表，如 ["二次函数", "阅读理解"]
    "strengths": [],     # 优势标签
    "goals": [],         # 学习目标
    "papers_count": 0,   # 已分析试卷数
    "updated_at": "",
}


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


# ============================================================
# 建表（模块加载即执行一次）
# ============================================================

_PROFILE_SQLITE = """
CREATE TABLE IF NOT EXISTS student_profile (
    id         TEXT PRIMARY KEY,
    data       TEXT NOT NULL,
    updated_at TEXT
)
"""

_PROFILE_PG = """
CREATE TABLE IF NOT EXISTS student_profile (
    id         TEXT PRIMARY KEY,
    data       TEXT NOT NULL,
    updated_at TEXT
)
"""

_PAPER_SQLITE = """
CREATE TABLE IF NOT EXISTS exam_papers (
    id             TEXT PRIMARY KEY,
    filename       TEXT,
    subject        TEXT,
    grade          TEXT,
    extracted_text TEXT,
    analysis       TEXT,
    score_summary  TEXT,
    weak_points    TEXT,
    created_at     TEXT
)
"""

_PAPER_PG = """
CREATE TABLE IF NOT EXISTS exam_papers (
    id             TEXT PRIMARY KEY,
    filename       TEXT,
    subject        TEXT,
    grade          TEXT,
    extracted_text TEXT,
    analysis       TEXT,
    score_summary  TEXT,
    weak_points    TEXT,
    created_at     TEXT
)
"""


def _init_tutor_tables():
    conn = connect()
    create_table_if_not_exists(conn, "student_profile", _PROFILE_SQLITE, _PROFILE_PG)
    create_table_if_not_exists(conn, "exam_papers", _PAPER_SQLITE, _PAPER_PG)
    conn.close()


_init_tutor_tables()


# ============================================================
# 学情档案读写
# ============================================================

def get_profile() -> dict:
    """读取学情档案（无则返回默认结构）。"""
    conn = connect()
    try:
        row = fetchone(conn, "SELECT data FROM student_profile WHERE id=?", ("default",))
    finally:
        conn.close()
    if row and row[0]:
        try:
            data = json.loads(row[0])
            # 补齐缺失字段，向前兼容
            for k, v in DEFAULT_PROFILE.items():
                data.setdefault(k, v)
            return data
        except Exception:
            pass
    return dict(DEFAULT_PROFILE)


def save_profile(data: dict) -> dict:
    """整体保存档案。"""
    data["updated_at"] = _now()
    conn = connect()
    try:
        exec(conn,
             "INSERT OR REPLACE INTO student_profile (id, data, updated_at) VALUES (?,?,?)",
             ("default", json.dumps(data, ensure_ascii=False), data["updated_at"]))
    finally:
        conn.close()
    return data


def update_profile(partial: dict) -> dict:
    """局部合并更新档案（薄弱点去重追加，掌握度取较新值）。"""
    cur = get_profile()
    for k, v in (partial or {}).items():
        if k == "subjects" and isinstance(v, dict):
            for subj, lvl in v.items():
                try:
                    cur["subjects"][subj] = int(lvl)
                except Exception:
                    pass
        elif k == "weak_points" and isinstance(v, list):
            for w in v:
                ws = str(w).strip()
                if ws and ws not in cur["weak_points"]:
                    cur["weak_points"].append(ws)
        elif k == "strengths" and isinstance(v, list):
            for s in v:
                ss = str(s).strip()
                if ss and ss not in cur["strengths"]:
                    cur["strengths"].append(ss)
        elif k == "goals" and isinstance(v, list):
            cur["goals"] = [str(x).strip() for x in v if str(x).strip()]
        elif k in ("name", "grade"):
            cur[k] = str(v or "")
    # 同步试卷计数
    cur["papers_count"] = len(list_papers_raw())
    return save_profile(cur)


# ============================================================
# 按学科分诊（名师·技能联动学情档案用）
# ============================================================

def subject_triage(subject: str) -> dict:
    """按学科「分诊」：返回该学科在学情档案中的掌握度、相关薄弱点、优势、年级/姓名。

    供名师·技能召唤某科老师时注入 system 提示，让老师按学生真实水平因材施教。
    - 没有建档 / 该科无数据时 has_profile=False，调用方据此走通用辅导。
    - 学科名匹配做容错：如档案里写「道法」也能和「政治」对上。
    """
    p = get_profile()
    subs = p.get("subjects", {}) or {}
    # 精确匹配优先；否则在已有学科 key 里找包含/被包含关系
    mastery = subs.get(subject)
    if mastery is None:
        for k, v in subs.items():
            if subject in k or k in subject:
                mastery = v
                break
    weak = p.get("weak_points", []) or []
    # 优先取「学科名出现在薄弱点里」的条目；否则退化为最近几条薄弱点供参考
    relevant = [w for w in weak if subject in w]
    if not relevant:
        relevant = weak[:5]
    strong = p.get("strengths", []) or []
    has = bool(p.get("name") or p.get("grade") or mastery is not None or weak or strong)
    return {
        "has_profile": has,
        "name": p.get("name", ""),
        "grade": p.get("grade", ""),
        "subject": subject,
        "mastery": mastery,
        "weak_points": relevant,
        "strengths": strong[:3],
    }


# ============================================================
# 试卷记录读写
# ============================================================

def _row_to_paper(row):
    cols = ["id", "filename", "subject", "grade", "extracted_text",
            "analysis", "score_summary", "weak_points", "created_at"]
    d = dict(zip(cols, row))
    try:
        d["analysis"] = json.loads(d["analysis"]) if d["analysis"] else None
    except Exception:
        pass
    try:
        d["weak_points"] = json.loads(d["weak_points"]) if d["weak_points"] else []
    except Exception:
        d["weak_points"] = []
    d.pop("extracted_text", None)  # 列表接口不返回全文
    return d


def list_papers_raw() -> list:
    conn = connect()
    try:
        rows = fetchall(conn,
                         "SELECT id,filename,subject,grade,extracted_text,analysis,"
                         "score_summary,weak_points,created_at FROM exam_papers "
                         "ORDER BY created_at DESC")
    finally:
        conn.close()
    return rows


def list_papers() -> list:
    return [_row_to_paper(r) for r in list_papers_raw()]


def add_paper(rec: dict) -> dict:
    pid = rec.get("id") or uuid.uuid4().hex[:12]
    conn = connect()
    try:
        exec(conn,
             "INSERT OR REPLACE INTO exam_papers "
             "(id,filename,subject,grade,extracted_text,analysis,score_summary,weak_points,created_at) "
             "VALUES (?,?,?,?,?,?,?,?,?)",
             (pid,
              rec.get("filename", ""),
              rec.get("subject", ""),
              rec.get("grade", ""),
              rec.get("extracted_text", ""),
              json.dumps(rec.get("analysis"), ensure_ascii=False) if rec.get("analysis") else "",
              rec.get("score_summary", ""),
              json.dumps(rec.get("weak_points", []), ensure_ascii=False),
              rec.get("created_at", _now())))
    finally:
        conn.close()
    # 同步 papers_count
    p = get_profile()
    p["papers_count"] = len(list_papers_raw())
    save_profile(p)
    return rec


# ============================================================
# 大模型调用（复用 /vision 的方式：ChatOpenAI + 环境变量模型）
# ============================================================

def _mock() -> bool:
    return os.getenv("MOCK", "false").lower() == "true"


def ask_llm(system: str, user: str, temperature: float = 0.2, max_tokens: int = 2000) -> str:
    """用配置的大模型做一次性问答（不进 Agent Loop）。MOCK 模式返回占位。"""
    if _mock():
        return "（演示模式）已生成分析结果。接入真实模型后这里会返回结构化学情分析。"
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage
        model = os.getenv("OPENAI_MODEL", "glm-4-flash")
        llm = ChatOpenAI(
            model=model,
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            temperature=temperature,
            max_tokens=max_tokens,
        )
        resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        return resp.content
    except Exception as e:
        return f"（分析失败：{e}）"


def _vision_describe(doc: dict) -> str:
    """对扫描件图片用视觉模型转写文字（best-effort，glm-4v-flash）。失败返回空串。"""
    if _mock():
        return ""
    path = doc.get("path", "")
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage
        model = os.getenv("OPENAI_MODEL_VISION", "glm-4v-flash")
        llm = ChatOpenAI(
            model=model,
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            temperature=0,
        )
        msg = HumanMessage(content=[
            {"type": "text",
             "text": "这是一份学生试卷/作业。请尽可能完整地把每一道题的题目、学生的作答、以及能看到的得分或批改痕迹，转写成文字，保留题号。"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ])
        return llm.invoke([msg]).content or ""
    except Exception:
        return ""


def _extract_json(text: str):
    """从模型输出里尽量解析出 JSON（兼容 ```json 围栏 / 前后多余文字）。"""
    if not text:
        return {}
    t = text.strip()
    # 去掉 ```json ... ``` 围栏
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", t, re.I)
    if m:
        t = m.group(1).strip()
    # 取第一个 { 到最后一个 } 之间的内容
    s, e = t.find("{"), t.rfind("}")
    if s != -1 and e != -1 and e > s:
        t = t[s:e + 1]
    try:
        return json.loads(t)
    except Exception:
        return {}


# ============================================================
# 试卷分析（核心）
# ============================================================

_ANALYSIS_SYSTEM = (
    "你是一位严谨的 K12 学情分析专家。用户会给你一份学生试卷/作业的内容（可能是题目+学生作答+得分）。\n"
    "请基于内容做结构化分析，并【只输出一个 JSON 对象】，不要任何解释性文字。JSON 结构如下：\n"
    "{\n"
    "  \"subject\": \"学科，如 数学/语文/英语/物理\",\n"
    "  \"grade\": \"推断的年级，如 初二/高一（不确定留空字符串）\",\n"
    "  \"score_summary\": \"一句话总结，含总分估算与失分集中点，例如『满分100估得72，失分集中在函数与几何证明』\",\n"
    "  \"mastery\": { \"知识点名称\": 掌握度0-100的数值 },   // 依据学生在这些知识点上的表现估算\n"
    "  \"weak_points\": [\"薄弱知识点/能力短板\"],            // 结合失分点，2-6 条\n"
    "  \"strengths\": [\"优势知识点\"],                       // 1-3 条\n"
    "  \"questions\": [ {\"no\":\"题号/内容\", \"topic\":\"知识点\", \"status\":\"correct|partial|wrong\", \"note\":\"简短点评\"} ],\n"
    "  \"suggestions\": [\"针对性提升建议，可操作\"]           // 2-5 条\n"
    "}\n"
    "注意：掌握度请基于『学生在该知识点上的作答正确率与难度』合理估算；若试卷无法判断正确与否，依据题目覆盖与作答完整度推断。"
)


def analyze_exam_paper(doc_id: str) -> str:
    """分析一篇已上传的试卷文档，更新学情档案，并返回人类可读的分析摘要。

    被 /analyze-paper 路由与 analyze_exam_paper 工具共用。
    """
    doc = get_document(doc_id)
    if not doc:
        return "找不到该文档（doc_id 无效或已被清理）。请重新上传试卷。"

    text = (doc.get("full_text") or "").strip()
    # 扫描件图片：尝试视觉转写
    if not text and doc.get("type") == "image":
        text = _vision_describe(doc)
    if not text:
        return ("⚠️ 无法从这份试卷中提取文字——它可能是纯图片且没有安装 OCR。" 
                "建议：①上传带文本层的 PDF / Word；②或把题目文字粘贴给我，我同样可以分析。")

    content = text[:6000]
    raw = ask_llm(_ANALYSIS_SYSTEM, "以下是一份学生试卷内容：\n\n" + content)
    analysis = _extract_json(raw)

    if not analysis:
        # 模型没吐出合规 JSON：退回把原始结论直接存为摘要
        analysis = {
            "subject": doc.get("type", "试卷"),
            "score_summary": raw[:200],
            "mastery": {},
            "weak_points": [],
            "strengths": [],
            "questions": [],
            "suggestions": [],
        }

    subject = analysis.get("subject", "") or doc.get("type", "试卷")
    grade = analysis.get("grade", "") or ""
    mastery = analysis.get("mastery", {}) or {}
    weak = analysis.get("weak_points", []) or []
    strong = analysis.get("strengths", []) or []

    # 写入学情档案（掌握度 + 薄弱点 + 优势 + 年级）
    update_profile({
        "grade": grade,
        "subjects": mastery,
        "weak_points": weak,
        "strengths": strong,
    })

    # 存试卷记录（持久化）
    add_paper({
        "filename": doc.get("name", ""),
        "subject": subject,
        "grade": grade,
        "extracted_text": text[:8000],
        "analysis": analysis,
        "score_summary": analysis.get("score_summary", ""),
        "weak_points": weak,
        "created_at": _now(),
    })

    # 组装人类可读摘要
    lines = []
    lines.append(f"📊 《{doc.get('name','试卷')}》学情分析")
    if grade:
        lines.append(f"年级：{grade}　学科：{subject}")
    if analysis.get("score_summary"):
        lines.append(f"📝 {analysis['score_summary']}")
    if mastery:
        lines.append("")
        lines.append("【各科/知识点掌握度】")
        for k, v in mastery.items():
            bar = "█" * (v // 10) + "░" * (10 - v // 10)
            lines.append(f"  {k}：{bar} {v}%")
    if weak:
        lines.append("")
        lines.append("【薄弱点】" + "、".join(weak))
    if strong:
        lines.append("【优势】" + "、".join(strong))
    if analysis.get("suggestions"):
        lines.append("")
        lines.append("【针对性提升建议】")
        for i, s in enumerate(analysis["suggestions"], 1):
            lines.append(f"  {i}. {s}")
    lines.append("")
    lines.append("✅ 已自动更新学情档案（掌握度与薄弱点）。可点『生成提升计划』获得可执行的复习安排。")
    return "\n".join(lines)


# ============================================================
# 针对性提升计划
# ============================================================

_PLAN_SYSTEM = (
    "你是一位私人家教，擅长根据学生学情制定可执行的学习计划。\n"
    "用户会给你学生的学情档案（年级、各科掌握度、薄弱点、优势、历史试卷结论）和一个目标/周期。\n"
    "请输出一个【只含 JSON 对象】的计划，结构如下：\n"
    "{\n"
    "  \"goal\": \"总目标（复述/提炼）\",\n"
    "  \"days\": 天数,\n"
    "  \"focus\": [\"本阶段重点薄弱点\"],\n"
    "  \"schedule\": [ {\"day\": 第几天(整数), \"theme\": \"当日主题\", \"tasks\": [\"具体任务1\",\"具体任务2\"]} ],\n"
    "  \"tips\": [\"给家长的陪伴建议/学习策略\"]\n"
    "}\n"
    "要求：任务具体、可操作、紧扣薄弱点；每天 2-4 个任务；难度循序渐进。"
)


def make_study_plan(goal: str = "", days: int = 14) -> str:
    """基于学情档案 + 历史试卷，生成针对性提升计划（JSON 字符串返回）。"""
    try:
        days = int(days)
    except Exception:
        days = 14
    days = max(3, min(60, days))

    profile = get_profile()
    papers = list_papers()
    paper_hints = []
    for p in papers[:8]:
        a = p.get("analysis") or {}
        paper_hints.append(f"- {p.get('filename','')}：{a.get('score_summary','') or p.get('score_summary','')}"
                           f"｜薄弱：{', '.join(a.get('weak_points', []) or p.get('weak_points', []) or [])}")

    profile_block = (
        f"学生：{profile.get('name') or '同学'}　年级：{profile.get('grade') or '未填'}\n"
        f"各科掌握度：{json.dumps(profile.get('subjects', {}), ensure_ascii=False)}\n"
        f"薄弱点：{', '.join(profile.get('weak_points', []) or []) or '暂无'}\n"
        f"优势：{', '.join(profile.get('strengths', []) or []) or '暂无'}\n"
        f"历史试卷（{len(papers)} 份）：\n" + ("\n".join(paper_hints) if paper_hints else "  （暂无）")
    )
    user = (f"【学情档案】\n{profile_block}\n\n"
            f"【目标】{goal or '全面提升，重点攻克薄弱点'}\n"
            f"【周期】{days} 天")

    raw = ask_llm(_PLAN_SYSTEM, user, temperature=0.4, max_tokens=2500)
    plan = _extract_json(raw)
    if not plan:
        plan = {
            "goal": goal or "全面提升",
            "days": days,
            "focus": profile.get("weak_points", [])[:3],
            "schedule": [],
            "tips": [raw[:300] or "（生成计划失败，请稍后重试）"],
        }
    return json.dumps(plan, ensure_ascii=False)
