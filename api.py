# api.py
# 用 FastAPI 把 Agent 包成 HTTP 接口，对应路线图阶段 5（工程化与部署）。
#
# 本地启动（在你自己机器上）：
#   uvicorn api:app --host 0.0.0.0 --port 8000 --reload
# 然后浏览器打开 http://localhost:8000/docs 能看到自动生成的接口文档。
#
# 调用示例：
#   curl -X POST http://localhost:8000/chat \
#        -H "Content-Type: application/json" \
#        -d '{"message": "帮我算 99*3，再记一条笔记：今天用 FastAPI 包了 Agent"}'

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi import File, UploadFile, Form
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import re
import time
import uuid
import shutil
from collections import deque
from documents import (
    ingest_file, ingest_url, list_documents, list_document_summaries,
    get_document, read_document, extract_tables, extract_clauses,
    search_documents, compare_documents,
)
import chat_history as history

# 阶段 4 引入：用 LangGraph 重写 Agent Loop（行为/接口与原手写版 agent.py 完全一致）
# 想回退到手写版，把这行改回 `from agent import Agent` 即可。
from agent_langgraph import Agent

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UI_FILE = os.path.join(BASE_DIR, "index.html")

app = FastAPI(title="Mini Tool-Calling Agent API", version="1.0")

# 允许跨域，方便以后接前端页面（生产环境请把 allow_origins 改成具体域名）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== 极简全局限流（防止公网暴露后被刷爆你的模型额度） =====
# 教学版：用滑动窗口限制"每分钟最多 N 次请求"。生产建议上 Redis + 按 IP 限流。
RATE_LIMIT = 60        # 每分钟最多请求数
RATE_WINDOW = 60       # 窗口秒数
_hits = deque()

def _rate_ok() -> bool:
    now = time.time()
    while _hits and now - _hits[0] > RATE_WINDOW:
        _hits.popleft()
    if len(_hits) >= RATE_LIMIT:
        return False
    _hits.append(now)
    return True


# 启动时构建一个全局 Agent 实例（复用连接，避免每次请求都重建）
agent = Agent(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    mock=os.getenv("MOCK", "false").lower() == "true",
)


class ChatRequest(BaseModel):
    message: str | None = None          # 正常对话内容；处理待审批操作时留空
    max_steps: int = 5
    session_id: str | None = None       # 不传则由服务端生成新会话
    # 人工审核的答复：{decision:"approve_all"|"reject_all"|"custom", approved:[ids], rejected:[ids], edits:{id:args}}
    # 带上它就表示"人类已答复"，服务端会用它唤醒被中断的图。
    review_decision: dict | None = None


class ChatResponse(BaseModel):
    reply: str
    steps: list
    session_id: str
    needs_review: bool = False          # True = 图被暂停，等待人类审批
    review: dict | None = None          # 待审批的操作清单（needs_review 时才有）


class ResetRequest(BaseModel):
    session_id: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tools")
def tools():
    """列出当前已加载的工具（本地 + 通过 MCP 接入的），方便排查 MCP 是否生效。"""
    return {"tools": [s["function"]["name"] for s in agent.tool_schemas]}


@app.get("/")
def root():
    # 直接把用户带到网页界面，/docs 仍是接口文档
    return RedirectResponse(url="/ui")


@app.get("/ui", response_class=FileResponse)
def ui():
    # 托管网页聊天界面，同源访问 /chat，无需处理跨域
    return FileResponse(UI_FILE)


# ===== PWA 所需静态资源 =====
@app.get("/manifest.webmanifest", response_class=FileResponse)
def manifest():
    return FileResponse(os.path.join(BASE_DIR, "manifest.webmanifest"),
                        media_type="application/manifest+json")


@app.get("/sw.js", response_class=FileResponse)
def sw():
    return FileResponse(os.path.join(BASE_DIR, "sw.js"),
                        media_type="text/javascript")


@app.get("/icon.svg", response_class=FileResponse)
def icon():
    return FileResponse(os.path.join(BASE_DIR, "icon.svg"),
                        media_type="image/svg+xml")


# ===== 文档上传与理解相关路由 =====

@app.post("/upload")
async def upload(files: list[UploadFile] = File(None), url: str = Form(None)):
    """上传文档（支持多文件）+ 可选网页 URL。自动解析/切块/建索引，返回每篇摘要。
    解析/切块/建索引是 CPU 重活，放进线程池跑，避免阻塞事件循环（大文档也不卡其他请求）。"""
    results = []
    if url:
        results.append(await run_in_threadpool(ingest_url, url))
    if files:
        for f in files:
            if not f or not f.filename:
                continue
            # 用安全文件名保存到 uploads/
            safe = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]", "_", f.filename)
            dest = os.path.join("uploads", safe)
            os.makedirs("uploads", exist_ok=True)
            with open(dest, "wb") as out:
                shutil.copyfileobj(f.file, out)
            results.append(await run_in_threadpool(ingest_file, dest))
    if not results:
        raise HTTPException(status_code=400, detail="请至少提供一个文件或 URL")
    return {"uploaded": len(results), "docs": results}


@app.get("/documents")
def documents():
    """列出所有已上传文档的结构化摘要。"""
    return {"documents": list_document_summaries()}


@app.get("/documents/{doc_id}")
def document_detail(doc_id: str):
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    # 不返回完整全文，避免响应过大；全文用 /chat 或 read_document 工具获取
    return {
        "id": doc["id"], "name": doc["name"], "type": doc["type"],
        "chars": doc["chars"], "tables": len(doc["tables"]),
        "chunks": len(doc["chunks"]), "clauses": len(doc["clauses"]),
        "headings": len(doc["structure"]), "notes": doc.get("notes", ""),
        "structure": doc["structure"][:200],
    }


@app.get("/documents/{doc_id}/tables")
def document_tables(doc_id: str):
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"tables": doc["tables"]}


@app.get("/documents/{doc_id}/text")
def document_text(doc_id: str, max_chars: int = 4000):
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"text": read_document(doc_id, max_chars=max_chars)}


@app.get("/documents/{doc_id}/clauses")
def document_clauses(doc_id: str, keyword: str = ""):
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"text": extract_clauses(doc_id, keyword=keyword or None)}


@app.post("/documents/search")
def document_search(req: dict):
    query = req.get("query", "")
    top_k = int(req.get("top_k", 5))
    return {"result": search_documents(query, top_k=top_k)}


@app.post("/documents/compare")
def document_compare(req: dict):
    a = req.get("a", "")
    b = req.get("b", "")
    topic = req.get("topic")
    return {"result": compare_documents(a, b, topic=topic)}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not _rate_ok():
        raise HTTPException(status_code=429, detail="请求太频繁，请稍后再试")

    session_id = req.session_id

    # 情况 A：人类答复了某个待审批操作 -> 用 review_decision 唤醒被中断的图
    if req.review_decision is not None:
        if not session_id:
            raise HTTPException(status_code=400, detail="review_decision 必须带上 session_id")
        result = agent.run_trace(
            session_id, user_input=None, max_steps=req.max_steps,
            review_decision=req.review_decision,
        )
        reply = result["reply"]
        # 审核通过后，把最终回复落进历史（用户消息在上一轮已存）
        history.append_message(session_id, "bot", reply or "", result.get("steps", []))
        return ChatResponse(
            reply=reply, steps=result["steps"], session_id=session_id,
            needs_review=result.get("needs_review", False), review=result.get("review"),
        )

    # 情况 B：普通新消息
    # 安全护栏：如果该会话还卡在"等待人类审批"，先别让它开新话题，避免打断中断状态
    if session_id and session_id in agent._pending:
        raise HTTPException(
            status_code=409,
            detail="当前会话有操作正等待你审批，请先处理（全部通过 / 拒绝）再继续。",
        )

    # 没带 session_id 就新建一个；前端应把它存起来，后续请求原样带回，实现多轮上下文
    session_id = session_id or str(uuid.uuid4())
    result = agent.run_trace(session_id, req.message, max_steps=req.max_steps)
    reply = result["reply"]
    steps = result["steps"]
    # 持久化到历史记录：用户消息一定存；若需要人工审批，bot 回复先不存
    # （审批通过后会走情况 A 再存最终回复，避免存一条空的占位）
    title = (req.message or "").strip()[:20] or None
    history.append_message(session_id, "user", req.message or "", title=title)
    if not result.get("needs_review"):
        history.append_message(session_id, "bot", reply or "", steps)
    return ChatResponse(
        reply=reply, steps=steps, session_id=session_id,
        needs_review=result.get("needs_review", False), review=result.get("review"),
    )


@app.post("/reset")
def reset(req: ResetRequest):
    """清空某个会话的 LangGraph 上下文（不影响历史记录，历史由 chat_history 管理）。"""
    agent.reset_session(req.session_id)
    return {"status": "ok", "session_id": req.session_id}


# ===== 历史对话记录相关路由 =====
@app.get("/conversations")
def conversations():
    """列出所有历史会话（按最近更新倒序）。"""
    return {"conversations": history.list_conversations()}


@app.get("/conversations/{sid}")
def conversation(sid: str):
    """获取某次会话的完整内容（含全部消息），用于回看。"""
    c = history.get_conversation(sid)
    if not c:
        raise HTTPException(status_code=404, detail="会话不存在")
    return c


@app.post("/conversations")
def new_conversation(title: str = "新对话"):
    """新建一个空会话（会出现在历史列表里）。"""
    return history.create_conversation(title=title)


@app.delete("/conversations/{sid}")
def del_conversation(sid: str):
    """删除一条历史会话。"""
    return history.delete_conversation(sid)


# 允许通过 `python api.py` 直接启动，并支持平台注入的 PORT 环境变量
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("api:app", host="0.0.0.0", port=port)
