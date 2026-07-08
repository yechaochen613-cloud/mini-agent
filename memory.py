# memory.py —— 真·RAG 记忆库（embeddings + 向量余弦检索）
#
# 这是路线图"阶段 3 RAG"的正经实现，和上一版"关键词重叠"的区别：
#   上一版：把文字拆成 token，用"重合词数"当相似度 → 只能字面匹配
#            ("咖啡" 匹配 "咖啡"，但 "爱喝的饮料" 匹配不到 "咖啡")
#   这一版：用嵌入模型把每段文字变成一串数字（向量），向量越接近 = 语义越像。
#           "我喜欢喝咖啡" 和 "他爱喝的饮料是咖啡" 在向量空间里距离很近 → 能"意会"。
#
# 向量库（Vector DB）本质就是"一堆向量 + 相似度检索"。这里把向量存进 memory.json
# （文件级向量索引），用纯 Python 算余弦相似度。规模小（几百条）时这完全够用；
# 要上生产，把 _load/_save + _cosine 换成 Chroma / Qdrant / pgvector 即可，接口不变。
#
# 嵌入后端（可插拔）：
#   - zhipu  （默认）：用智谱 embedding-3（OpenAI 兼容）。需 embeddings 资源包。
#   - openai ：任意 OpenAI 兼容嵌入端点（填 EMBEDDING_BASE_URL/KEY/MODEL）。
#   - keyword：本地关键词向量兜底，无需联网、零依赖（语义能力弱，仅作降级）。
#   任何嵌入调用失败（如余额不足 429 / 断网 / MOCK 模式）都会自动降级到 keyword，
#   保证功能永远不中断——这正是"优雅降级"的工程习惯。

import json
import os
import re
import math
import datetime
from dotenv import load_dotenv

load_dotenv()  # 确保能读到 EMBEDDING_* 配置

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "memory.json")
MAX_MEMORIES = 300  # 上限，防止无限增长

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "zhipu")  # zhipu | openai | keyword
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "embedding-3")
MOCK = os.getenv("MOCK", "false").lower() == "true"

# 懒加载的嵌入客户端（仅非 keyword / 非 MOCK 时使用）
_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        if EMBEDDING_PROVIDER == "zhipu":
            base = os.getenv("OPENAI_BASE_URL")
            key = os.getenv("OPENAI_API_KEY")
        else:  # openai 兼容
            base = os.getenv("EMBEDDING_BASE_URL")
            key = os.getenv("EMBEDDING_API_KEY")
        _client = OpenAI(api_key=key, base_url=base)
    return _client


# ---------------- 嵌入（文字 → 向量） ----------------

def _tokenize(text):
    """中文按单字、英文/数字按连续词，小写化。用于关键词兜底向量。"""
    text = (text or "").lower()
    return re.findall(r"[a-z0-9]+|[一-鿿]", text)


def _keyword_vector(text):
    """把文本变成词频字典（稀疏向量）。"""
    d = {}
    for tk in _tokenize(text):
        d[tk] = d.get(tk, 0) + 1
    return d


def embed(text):
    """返回 {"kw": bool, "vec": ...}。kw=True 表示用的是关键词兜底向量。"""
    # MOCK 或显式 keyword：直接用本地关键词向量，零依赖、离线可用
    if MOCK or EMBEDDING_PROVIDER == "keyword":
        return {"kw": True, "vec": _keyword_vector(text)}

    # 否则尝试真实嵌入模型（语义向量）
    try:
        client = _get_client()
        model = EMBEDDING_MODEL if EMBEDDING_PROVIDER == "zhipu" \
            else os.getenv("EMBEDDING_MODEL_OPENAI", "text-embedding-3-small")
        resp = client.embeddings.create(model=model, input=text)
        return {"kw": False, "vec": resp.data[0].embedding}
    except Exception:
        # 优雅降级：余额不足 / 断网 / 任何异常 → 退回关键词向量，功能不中断
        return {"kw": True, "vec": _keyword_vector(text)}


# ---------------- 余弦相似度 ----------------

def _cosine(a, b):
    """支持稠密向量(list)与稀疏向量(dict)两种表示。"""
    if isinstance(a, dict) or isinstance(b, dict):
        da = a if isinstance(a, dict) else {}
        db = b if isinstance(b, dict) else {}
        keys = set(da) | set(db)
        dot = sum(da.get(k, 0) * db.get(k, 0) for k in keys)
        na = math.sqrt(sum(v * v for v in da.values()))
        nb = math.sqrt(sum(v * v for v in db.values()))
        return dot / (na * nb) if na and nb else 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


# ---------------- 存取 ----------------

def _load():
    if not os.path.exists(MEMORY_FILE):
        return []
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save(memories):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memories, f, ensure_ascii=False, indent=2)


def add_memory(text):
    """保存一条记忆（顺便算好它的向量一起存盘）。返回给模型看的结果字符串。"""
    text = (text or "").strip()
    if not text:
        return "记忆内容为空，未保存。"
    memories = _load()
    if any(m["text"] == text for m in memories):
        return f"这条记忆已经存在了：{text}"

    emb = embed(text)
    memories.append({
        "text": text,
        "vec": emb["vec"],
        "kw": emb["kw"],
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
    })
    if len(memories) > MAX_MEMORIES:
        memories = memories[-MAX_MEMORIES:]
    _save(memories)
    mode = "语义向量" if not emb["kw"] else "关键词向量(兜底)"
    return f"已记住（{mode}）：{text}"


def _retrieve(query, top_k=5, threshold=None):
    """统一检索：返回 [(score, memory), ...] 按相似度降序。"""
    memories = _load()
    if not memories:
        return []
    q = embed(query)
    # 阈值：语义向量用 0.25，关键词兜底用 0.04（两者分布不同）
    if threshold is None:
        threshold = 0.25 if not q["kw"] else 0.04
    scored = []
    for m in memories:
        # 若本次查询与某条记忆的向量类型不一致（理论上同一次运行不会），跳过
        s = _cosine(q["vec"], m.get("vec", {}))
        if s >= threshold:
            scored.append((s, m))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]


def search_memory(query, top_k=5):
    """显式检索：模型/用户主动"回忆"某件事。"""
    scored = _retrieve(query, top_k=top_k, threshold=None)
    if not scored:
        return "没有找到相关的记忆。"
    lines = [f"- {m['text']}（相关度 {s:.2f}）" for s, m in scored]
    return "相关记忆：\n" + "\n".join(lines)


def relevant_context(query, top_k=5):
    """隐性检索：每轮对话前自动找出相关记忆，用于注入 system 提示。
    没有相关记忆时返回空字符串（不污染提示词）。"""
    scored = _retrieve(query, top_k=top_k)
    if not scored:
        return ""
    return "\n".join(f"- {m['text']}" for _, m in scored)


def clear_memory():
    """清空整个记忆库（调试用）。"""
    _save([])
    return "已清空所有记忆。"
