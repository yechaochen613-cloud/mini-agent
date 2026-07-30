# exercises.py —— 诊断闭环：出题 + 本地判分 + 薄弱点画像
#
# 复用 tutor.ask_llm（一次性大模型问答）生成选择题；
# 离线/MOCK 或解析失败时用 curriculum 内置 quiz 兜底，保证闭环始终可用。
# 判分纯本地（答案比对），不依赖模型；薄弱点画像写回 tutor 学情档案。

import os
import random
from collections import defaultdict

from curriculum import get_curriculum, get_all_points, sample_points, SUPPORTED, list_supported
from tutor import ask_llm, _extract_json, update_profile, _mock


_GEN_SYSTEM = (
    "你是一位严谨的 K12 数学出题专家。给定学科、年级与若干『知识点』，请为每个知识点出 1 道【选择题】。\n"
    "【只输出一个 JSON 数组】，不要任何解释文字。数组每个元素结构：\n"
    "{\n"
    "  \"topic_id\": \"对应知识点 id（必须原样返回）\",\n"
    "  \"topic\": \"知识点名称（必须原样返回）\",\n"
    "  \"stem\": \"题干（简洁、纯文字可表述、无图）\",\n"
    "  \"options\": [\"A选项\",\"B选项\",\"C选项\",\"D选项\"],   // 恰好 4 个，且只有一个正确\n"
    "  \"answer\": 0,   // 正确选项下标，必须是 0/1/2/3 之一，且对应选项确为唯一正确答案\n"
    "  \"explanation\": \"1-2 句话的解析\"\n"
    "}\n"
    "要求：难度符合年级水平；题干明确无歧义；干扰项有合理迷惑性；answer 必须是 0-3 且唯一正确。"
)


def generate_diagnosis(subject: str, grade: str, count: int = 12, seed=None) -> dict:
    """生成诊断卷。返回 {subject, grade, count, questions:[...]}；不支持的学科年级返回 None。"""
    if (subject, grade) not in SUPPORTED:
        return None
    try:
        count = max(4, min(20, int(count)))
    except Exception:
        count = 12
    points = get_all_points(subject, grade)
    chosen = sample_points(points, count, seed=seed)

    questions = _try_llm(subject, grade, chosen)
    if not questions:
        questions = _fallback(chosen)

    return {
        "subject": subject,
        "grade": grade,
        "count": len(questions),
        "questions": questions,
    }


def _try_llm(subject: str, grade: str, chosen: list) -> list:
    """用大模型按抽样知识点出题；任何异常/解析失败返回空（交由兜底）。

    与 api.py 的 Agent 一致：只要配置了真实密钥就走真模型，忽略 MOCK 开关，
    保证线上（即便 MOCK=true）也能用 LLM 生成有变化的题目；无密钥/失败则回退兜底。
    """
    _real_cfg = bool(os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_BASE_URL"))
    if _mock() and not _real_cfg:
        return []
    try:
        topics = "\n".join(f"- id:{p['id']} 知识点:{p['name']}" for p in chosen)
        user = (
            f"学科：{subject}\n年级：{grade}\n"
            f"请为以下每个知识点各出 1 道选择题（共 {len(chosen)} 道）：\n{topics}"
        )
        raw = ask_llm(_GEN_SYSTEM, user, temperature=0.4, max_tokens=2800)
        arr = _extract_json(raw)
        if isinstance(arr, dict):
            arr = arr.get("questions") or []
        if not isinstance(arr, list) or not arr:
            return []
        by_id = {p["id"]: p for p in chosen}
        out = []
        for item in arr:
            if not isinstance(item, dict):
                continue
            p = by_id.get(item.get("topic_id"))
            if not p and item.get("topic"):
                p = next((x for x in chosen if x["name"] == item.get("topic")), None)
            if not p:
                continue
            opts = item.get("options")
            if not isinstance(opts, list) or len(opts) != 4:
                continue
            ans = item.get("answer")
            if not isinstance(ans, int) or not (0 <= ans < len(opts)):
                continue
            out.append({
                "id": f"{p['id']}-{random.randint(1000, 9999)}",
                "topic_id": p["id"],
                "topic": p["name"],
                "stem": item.get("stem", ""),
                "options": opts,
                "answer": ans,
                "explanation": item.get("explanation", ""),
            })
        return out
    except Exception:
        return []


def _fallback(chosen: list) -> list:
    """离线兜底：直接用 curriculum 内置的正确选择题。"""
    out = []
    for p in chosen:
        q = p.get("quiz")
        if not q:
            continue
        out.append({
            "id": f"{p['id']}-fb",
            "topic_id": p["id"],
            "topic": p["name"],
            "stem": q["q"],
            "options": list(q["options"]),
            "answer": int(q["a"]),
            "explanation": q.get("exp", ""),
        })
    return out


def grade_diagnosis(subject: str, grade: str, questions: list, answers: list, write_profile: bool = True) -> dict:
    """本地判分并聚合薄弱点画像。

    questions: 生成时的题目数组（含 answer）
    answers:   [{id, choice}] 用户作答
    返回 {subject, grade, score, correct, total, mastery:[...], weak_points, strengths, suggestions, profile}
    """
    ans_map = {}
    for a in (answers or []):
        if isinstance(a, dict) and a.get("id") is not None:
            ans_map[a.get("id")] = a.get("choice")

    total = len(questions) if questions else 0
    correct = 0
    per_topic = {}
    for q in (questions or []):
        qid = q.get("id")
        correct_idx = q.get("answer")
        chosen = ans_map.get(qid)
        is_right = isinstance(chosen, int) and chosen == correct_idx
        if is_right:
            correct += 1
        tid = q.get("topic_id") or q.get("topic")
        d = per_topic.setdefault(tid, {"topic": q.get("topic"), "right": 0, "total": 0})
        d["total"] += 1
        if is_right:
            d["right"] += 1

    score = round(100 * correct / total) if total else 0

    mastery = []
    for tid, d in per_topic.items():
        pct = round(100 * d["right"] / d["total"]) if d["total"] else 0
        mastery.append({
            "topic_id": tid,
            "topic": d["topic"],
            "pct": pct,
            "right": d["right"],
            "total": d["total"],
        })
    # 掌握度从低到高排列，最弱的排前面，便于优先攻克
    mastery.sort(key=lambda x: x["pct"])

    weak = [m["topic"] for m in mastery if m["pct"] < 60]
    strong = [m["topic"] for m in mastery if m["pct"] >= 85]
    suggestions = _suggestions(weak, strong, subject)

    profile = None
    if write_profile:
        try:
            update_profile({
                "grade": grade,
                "subjects": {subject: score},
                "weak_points": weak,
                "strengths": strong,
            })
            from tutor import get_profile
            profile = get_profile()
        except Exception:
            pass

    return {
        "subject": subject,
        "grade": grade,
        "score": score,
        "correct": correct,
        "total": total,
        "mastery": mastery,
        "weak_points": weak,
        "strengths": strong,
        "suggestions": suggestions,
        "profile": profile,
    }


def _suggestions(weak: list, strong: list, subject: str) -> list:
    s = []
    if weak:
        s.append(f"优先攻克薄弱点：{ '、'.join(weak[:4]) }，建议每个知识点配套 3-5 道同类题巩固。")
        s.append("把诊断中出错的题加入『错题本』，按艾宾浩斯曲线复习，避免遗忘。")
    if strong:
        s.append(f"保持优势：{ '、'.join(strong[:3]) } 掌握较好，可尝试拔高题进一步拓展。")
    if not s:
        s.append("各知识点掌握较均衡，保持日常练习节奏即可。")
    return s


# ============================================================
# 期 2：薄弱点 → 针对性练习 + 名师讲解
# ============================================================

_PRACTICE_SYSTEM = (
    "你是一位耐心细致的 K12 数学名师，擅长「边讲边练」。给定学科、年级与若干【薄弱知识点】，"
    "请为每个知识点出 1-2 道【选择题】用于巩固。\n"
    "【只输出一个 JSON 数组】，不要任何解释文字。数组每个元素结构：\n"
    "{\n"
    "  \"topic_id\": \"对应知识点 id（必须原样返回）\",\n"
    "  \"topic\": \"知识点名称（必须原样返回）\",\n"
    "  \"stem\": \"题干（简洁、纯文字可表述、无图）\",\n"
    "  \"options\": [\"A选项\",\"B选项\",\"C选项\",\"D选项\"],   // 恰好 4 个，只有一个正确\n"
    "  \"answer\": 0,   // 正确选项下标，必须是 0/1/2/3 之一\n"
    "  \"explanation\": \"名师讲解：①点明考查的知识点；②分步推导（写出关键算式/推理）；③指出常见易错点。3-5 句，像老师在黑板边写边讲。\"\n"
    "}\n"
    "要求：题目紧扣该薄弱点、难度贴合年级；explanation 必须体现『分步推导 + 易错提醒』的名师风格；"
    "answer 必须是 0-3 且对应选项确为唯一正确答案。"
)


def generate_practice(subject: str, grade: str, focus_points: list = None, count: int = 6, seed=None) -> dict:
    """生成针对性练习（薄弱点巩固 + 名师讲解）。

    返回 {subject, grade, focus_points, count, questions:[...]}；不支持的学科年级返回 None。
    focus_points：薄弱点列表（知识点 id 或名称）；为空则自动从学情档案 weak_points 取，仍为空则抽样兜底。
    """
    if (subject, grade) not in SUPPORTED:
        return None
    try:
        count = max(3, min(12, int(count)))
    except Exception:
        count = 6
    all_pts = get_all_points(subject, grade)
    by_id = {p["id"]: p for p in all_pts}
    by_name = {p["name"]: p for p in all_pts}

    def resolve(fp):
        fp = str(fp or "").strip()
        if not fp:
            return None
        if fp in by_id:
            return by_id[fp]
        if fp in by_name:
            return by_name[fp]
        for p in all_pts:
            if fp in p["name"] or p["name"] in fp:
                return p
        return None

    # 1) 显式给定的聚焦薄弱点
    target, seen = [], set()
    for fp in (focus_points or []):
        p = resolve(fp)
        if p and p["id"] not in seen:
            seen.add(p["id"])
            target.append(p)
    # 2) 未给定 → 从学情档案薄弱点自动取（诊断写回的 weak_points 即知识点名称）
    if not target:
        try:
            from tutor import get_profile
            prof = get_profile()
            for wp in (prof.get("weak_points") or []):
                p = resolve(wp)
                if p and p["id"] not in seen:
                    seen.add(p["id"])
                    target.append(p)
        except Exception:
            pass
    # 3) 仍为空 → 抽样兜底，保证闭环始终可用
    if not target:
        target = sample_points(all_pts, count, seed=seed)

    # 展开成 count 个 slot（轮转），使薄弱点均匀分布
    slots = []
    if target:
        while len(slots) < count:
            slots.extend(target)
        slots = slots[:count]
    else:
        slots = sample_points(all_pts, count, seed=seed)

    questions = _try_llm_practice(subject, grade, slots)
    if not questions:
        questions = _fallback_practice(slots)
    else:
        # 按 slot 顺序补齐 LLM 未覆盖的题（用内置题库兜底该 slot），确保恰好 count 题
        q_by_topic = defaultdict(list)
        for q in questions:
            q_by_topic[q["topic_id"]].append(q)
        final = []
        for slot in slots:
            if q_by_topic.get(slot["id"]):
                final.append(q_by_topic[slot["id"]].pop(0))
            else:
                final.append(_fb_one(slot))
        questions = final

    return {
        "subject": subject,
        "grade": grade,
        "focus_points": [t["name"] for t in target],
        "count": len(questions),
        "questions": questions,
    }


def _try_llm_practice(subject: str, grade: str, slots: list) -> list:
    """用大模型针对薄弱点出练习（含名师讲解）。异常/解析失败返回空（交由兜底）。"""
    _real_cfg = bool(os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_BASE_URL"))
    if _mock() and not _real_cfg:
        return []
    try:
        topics = "\n".join(f"- id:{p['id']} 知识点:{p['name']}" for p in slots)
        user = (
            f"学科：{subject}\n年级：{grade}\n"
            f"以下是学生的薄弱知识点，请针对它们各出 1 道选择题（共 {len(slots)} 道，可一个知识点多道）：\n{topics}"
        )
        raw = ask_llm(_PRACTICE_SYSTEM, user, temperature=0.5, max_tokens=3500)
        arr = _extract_json(raw)
        if isinstance(arr, dict):
            arr = arr.get("questions") or []
        if not isinstance(arr, list) or not arr:
            return []
        by_id = {p["id"]: p for p in slots}
        out = []
        for item in arr:
            if not isinstance(item, dict):
                continue
            p = by_id.get(item.get("topic_id"))
            if not p and item.get("topic"):
                p = next((x for x in slots if x["name"] == item.get("topic")), None)
            if not p:
                continue
            opts = item.get("options")
            if not isinstance(opts, list) or len(opts) != 4:
                continue
            ans = item.get("answer")
            if not isinstance(ans, int) or not (0 <= ans < len(opts)):
                continue
            exp = item.get("explanation") or (p.get("quiz", {}) or {}).get("exp", "")
            if not exp:
                exp = f"本题考查『{p['name']}』。正确选项是 {chr(65 + ans)}：{opts[ans] if opts else ''}。"
            out.append({
                "id": f"{p['id']}-{random.randint(1000, 9999)}",
                "topic_id": p["id"],
                "topic": p["name"],
                "stem": item.get("stem", ""),
                "options": opts,
                "answer": ans,
                "explanation": exp,
            })
        return out
    except Exception:
        return []


def _fb_one(p: dict) -> dict:
    """单题离线兜底：用内置 quiz。"""
    q = p.get("quiz") or {}
    opts = list(q.get("options", []))
    ans = int(q.get("a", 0)) if opts else 0
    exp = q.get("exp", "")
    if not exp and opts:
        exp = f"本题考查『{p['name']}』。正确选项是 {chr(65 + ans)}：{opts[ans]}。"
    return {
        "id": f"{p['id']}-{random.randint(1000, 9999)}",
        "topic_id": p["id"],
        "topic": p["name"],
        "stem": q.get("q", ""),
        "options": opts,
        "answer": ans,
        "explanation": exp,
    }


def _fallback_practice(slots: list) -> list:
    """离线兜底：去重后逐点出题（保证题目不重复）。"""
    seen, out = set(), []
    for p in slots:
        if p["id"] in seen:
            continue
        seen.add(p["id"])
        out.append(_fb_one(p))
    return out
