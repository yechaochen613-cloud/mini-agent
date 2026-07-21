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

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse, JSONResponse
from fastapi import File, UploadFile, Form

import auth as auth_store
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import json
import re
import time
import uuid
import shutil
import logging
import threading
from collections import deque, defaultdict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("api")
from documents import (
    ingest_file, ingest_url, list_documents, list_document_summaries,
    get_document, read_document, extract_tables, extract_clauses,
    search_documents, compare_documents,
)
import chat_history as history
from storage import UPLOAD_DIR, DATA_DIR
import connectors
import memory
import schedules
import sub_agents

# 阶段 4 引入：用 LangGraph 重写 Agent Loop（行为/接口与原手写版 agent.py 完全一致）
# 想回退到手写版，把这行改回 `from agent import Agent` 即可。
from agent_langgraph import Agent

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UI_FILE = os.path.join(BASE_DIR, "index.html")

app = FastAPI(title="Mini Tool-Calling Agent API", version="1.0")

# 允许跨域：仅放行已知来源（线上域名 + 本地开发），不再 * 全开。
# 可通过环境变量 ALLOWED_ORIGINS 覆盖（逗号分隔）。
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000,https://mini-agent-rbzb.onrender.com",
    ).split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ===== 按 IP 限流（防公网暴力破解 / 刷爆模型额度） =====
# 教学版：内存滑动窗口，按 (IP, 桶) 计。生产建议上 Redis + 按 IP 限流。
class _RateLimiter:
    def __init__(self):
        self.buckets: dict = defaultdict(deque)

    def allow(self, key: str, limit: int, window: int) -> bool:
        now = time.time()
        dq = self.buckets[key]
        while dq and now - dq[0] > window:
            dq.popleft()
        if len(dq) >= limit:
            return False
        dq.append(now)
        return True

_limiter = _RateLimiter()


def _client_ip(request: Request) -> str:
    """尽量取到真实客户端 IP（兼容反向代理的 x-forwarded-for）。"""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return getattr(request.client, "host", None) or "unknown"


def _rate_ok(request: Request, bucket: str, limit: int, window: int = 60) -> bool:
    """按 (IP, 桶) 的滑动窗口限流；超过 limit 返回 False。"""
    return _limiter.allow(f"{_client_ip(request)}|{bucket}", limit, window)


def _sse(event: dict) -> str:
    """把一个 dict 格式化成一行 SSE data（UTF-8，安全）。"""
    return "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"


def _fail(status: int, client_msg: str, exc: Exception | None = None) -> HTTPException:
    """把真实异常打到日志，但只把通用文案返回给客户端，避免泄露内部路径 / 堆栈。"""
    if exc is not None:
        logger.error("[%s] %s -> %s", status, client_msg, exc)
    return HTTPException(status_code=status, detail=client_msg)


# 懒加载全局 Agent：uvicorn 启动时不立即构建（避免 langgraph + MCP 子进程 + LLM 预热
# 在 Render 免费实例 512MB 上把冷启动拖爆/OOM，导致服务进程起不来 -> Render 显示 no-server）。
# 首次真实请求时才建，保证 /health 等轻量端点秒回、健康检查必过、服务稳定标记为 live。
_api_key = os.getenv("OPENAI_API_KEY")
_base_url = os.getenv("OPENAI_BASE_URL")
# 只要配置了真实密钥就强制走真模型，忽略 MOCK 开关（防 dashboard 残留 MOCK=true 导致假模式）
_mock = os.getenv("MOCK", "false").lower() == "true" and not (_api_key and _base_url)
_agent_instance = None
_agent_lock = threading.Lock()


def get_agent():
    """线程安全的懒加载 Agent（首次调用才真正构建 LangGraph 图 + 连 MCP）。"""
    global _agent_instance
    if _agent_instance is None:
        with _agent_lock:
            if _agent_instance is None:
                _agent_instance = Agent(
                    api_key=_api_key,
                    base_url=_base_url,
                    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    mock=_mock,
                )
    return _agent_instance

# 前端模型选择器档位 -> 真实模型名（pro 可改成你账号里更强的模型；留空则用默认）
MODEL_PRESETS = {
    "1.0": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    "lite": "gpt-4o-mini",
    "pro": os.getenv("OPENAI_MODEL_PRO", "gpt-4o"),
}


class ChatRequest(BaseModel):
    message: str | None = None          # 正常对话内容；处理待审批操作时留空
    max_steps: int = 5
    session_id: str | None = None       # 不传则由服务端生成新会话
    model: str | None = None            # 前端模型选择器选的档位：1.0 / lite / pro
    # 人工审核的答复：{decision:"approve_all"|"reject_all"|"custom", approved:[ids], rejected:[ids], edits:{id:args}}
    # 带上它就表示"人类已答复"，服务端会用它唤醒被中断的图。
    review_decision: dict | None = None
    # 角色人设 / 回答风格（来自前端「个性化设置」面板 + 名师·技能的学科召唤）。
    # 之前后端不接收 = 死功能；现在真正注入到 Agent 的 system 提示。
    persona: str | None = None          # tutor / strict / funny / gentle / 学科名(数学..)
    style: str | None = None            # concise / detailed / step / example


# ===== 登录态（会话）依赖 =====
def get_current_user(request: Request) -> dict:
    """从 Cookie 读取会话 token，解析出当前登录用户；未登录或失效抛 401。"""
    token = request.cookies.get("session")
    user = auth_store.get_session_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    return user


def _set_session_cookie(resp: Response, token: str, request: Request) -> None:
    """把会话 token 写入 HttpOnly Cookie；按请求协议决定是否 Secure。"""
    secure = (request.url.scheme == "https") or (request.headers.get("x-forwarded-proto") == "https")
    resp.set_cookie(
        "session", token,
        httponly=True, samesite="lax", path="/",
        secure=secure, max_age=auth_store.SESSION_TTL,
    )


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


@app.get("/debug/llm")
def debug_llm():
    """诊断用：用服务端环境变量直接打一次模型，返回延迟与错误（key 不外泄）。"""
    import time as _t
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    base = os.getenv("OPENAI_BASE_URL") or "(未设置)"
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return {"ok": False, "error": "OPENAI_API_KEY 未设置", "model": model, "base_url": base}
    try:
        llm = ChatOpenAI(model=model, api_key=key, base_url=os.getenv("OPENAI_BASE_URL"),
                         temperature=0, timeout=25, request_timeout=25)
        t0 = _t.time()
        resp = llm.invoke([HumanMessage(content="ping")])
        dt = round((_t.time() - t0) * 1000)
        return {"ok": True, "latency_ms": dt, "model": model, "base_url": base,
                "reply_len": len(getattr(resp, "content", "") or "")}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300], "model": model, "base_url": base}



@app.get("/tools")
def tools():
    """列出当前已加载的工具（本地 + 通过 MCP 接入的），方便排查 MCP 是否生效。"""
    return {"tools": [s["function"]["name"] for s in get_agent().tool_schemas]}


@app.get("/")
def root():
    # 直接把用户带到网页界面，/docs 仍是接口文档
    return RedirectResponse(url="/ui")


@app.get("/ui", response_class=FileResponse)
def ui():
    # 托管网页聊天界面，同源访问 /chat，无需处理跨域
    # no-store：禁止 CDN/浏览器缓存 HTML，任何一次新部署都立即生效，
    # 避免用户一直跑着旧版（此前 undefined 问题根因就是旧 HTML 在跑）
    return FileResponse(UI_FILE, headers={"Cache-Control": "no-store, no-cache, no-transform, must-revalidate"})


# ===== PWA 所需静态资源 =====
@app.get("/manifest.webmanifest", response_class=FileResponse)
def manifest():
    return FileResponse(os.path.join(BASE_DIR, "manifest.webmanifest"),
                        media_type="application/manifest+json")


@app.get("/sw.js", response_class=FileResponse)
def sw():
    # sw.js 本身必须 no-cache，否则 PWA 更新后浏览器仍跑旧 worker
    return FileResponse(os.path.join(BASE_DIR, "sw.js"),
                        media_type="text/javascript",
                        headers={"Cache-Control": "no-cache, no-transform"})


# 抽离出的样式表：HTML 里以 /static/styles.css?v=版本号 引用，
# 这里按路径返回并长效缓存（immutable）。版本变化即视为新资源，
# 避免改动 CSS 后浏览器仍跑旧缓存导致更新不可见。
@app.get("/static/styles.css")
def serve_styles():
    return FileResponse(os.path.join(BASE_DIR, "styles.css"),
                        media_type="text/css",
                        headers={"Cache-Control": "public, max-age=31536000, immutable"})


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
            dest = os.path.join(UPLOAD_DIR, safe)
            os.makedirs(UPLOAD_DIR, exist_ok=True)
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
def chat(req: ChatRequest, request: Request, user: dict = Depends(get_current_user)):
    if not _rate_ok(request, "chat", 30, 60):
        raise HTTPException(status_code=429, detail="请求太频繁，请稍后再试")

    session_id = req.session_id
    owner = user["id"]

    # 前端模型档位（1.0/lite/pro）映射到真实模型名，仅非 mock 模式生效
    model_arg = MODEL_PRESETS.get(req.model) if req.model else None

    # 情况 A：人类答复了某个待审批操作 -> 用 review_decision 唤醒被中断的图
    if req.review_decision is not None:
        if not session_id:
            raise HTTPException(status_code=400, detail="review_decision 必须带上 session_id")
        result = get_agent().run_trace(
            session_id, user_input=None, max_steps=req.max_steps,
            review_decision=req.review_decision, model=model_arg,
            persona=req.persona, style=req.style,
        )
        reply = result["reply"]
        # 审核通过后，把最终回复落进历史（用户消息在上一轮已存）
        history.append_message(session_id, "bot", reply or "", result.get("steps", []), owner=owner)
        return ChatResponse(
            reply=reply, steps=result["steps"], session_id=session_id,
            needs_review=result.get("needs_review", False), review=result.get("review"),
        )

    # 情况 B：普通新消息
    # 安全护栏：如果该会话还卡在"等待人类审批"，先别让它开新话题，避免打断中断状态
    if session_id and session_id in get_agent()._pending:
        raise HTTPException(
            status_code=409,
            detail="当前会话有操作正等待你审批，请先处理（全部通过 / 拒绝）再继续。",
        )

    # 没带 session_id 就新建一个；前端应把它存起来，后续请求原样带回，实现多轮上下文
    session_id = session_id or str(uuid.uuid4())
    result = get_agent().run_trace(
        session_id, req.message, max_steps=req.max_steps, model=model_arg,
        persona=req.persona, style=req.style,
    )
    reply = result["reply"]
    steps = result["steps"]
    # 持久化到历史记录：用户消息一定存；若需要人工审批，bot 回复先不存
    # （审批通过后会走情况 A 再存最终回复，避免存一条空的占位）
    title = (req.message or "").strip()[:20] or None
    history.append_message(session_id, "user", req.message or "", title=title, owner=owner)
    if not result.get("needs_review"):
        history.append_message(session_id, "bot", reply or "", steps, owner=owner)
        return ChatResponse(
            reply=reply, steps=steps, session_id=session_id,
            needs_review=result.get("needs_review", False), review=result.get("review"),
        )


@app.post("/chat/stream")
def chat_stream(req: ChatRequest, request: Request, user: dict = Depends(get_current_user)):
    """流式对话（SSE）：边执行边吐事件，让前端实时呈现"执行步骤"与打字机式回复。
    对标 Manus 的"活着的智能体"体感。历史记录在服务端落库（用户消息 + 最终回复）。"""
    if not _rate_ok(request, "chat", 30, 60):
        raise HTTPException(status_code=429, detail="请求太频繁，请稍后再试")

    session_id = req.session_id or str(uuid.uuid4())
    owner = user["id"]
    model_arg = MODEL_PRESETS.get(req.model) if req.model else None
    title = (req.message or "").strip()[:20] or None

    def event_gen():
        final_reply = ""
        try:
            # 情况 A：人类答复了待审批操作 -> 走非流式 run_trace 并一次性吐出
            if req.review_decision is not None:
                if not session_id:
                    yield _sse({"type": "error", "message": "review_decision 必须带 session_id"})
                    return
                result = get_agent().run_trace(
                    session_id, user_input=None, max_steps=req.max_steps,
                    review_decision=req.review_decision, model=model_arg,
                    persona=req.persona, style=req.style,
                )
                final_reply = result.get("reply", "")
                yield _sse({
                    "type": "done", "reply": final_reply, "session_id": session_id,
                    "steps": result.get("steps", []),
                    "needs_review": result.get("needs_review", False),
                    "review": result.get("review"),
                })
                return

            # 情况 B：普通新消息 —— 先落用户消息，再流式跑 Agent
            if req.message:
                history.append_message(session_id, "user", req.message, title=title, owner=owner)
            for ev in get_agent().run_stream(
                session_id, req.message, max_steps=req.max_steps, model=model_arg,
                persona=req.persona, style=req.style,
            ):
                if ev.get("type") == "done":
                    final_reply = ev.get("reply", "")
                yield _sse(ev)
            # 流式结束，落库最终回复（带上逐步记录）
            if final_reply:
                history.append_message(session_id, "bot", final_reply, get_agent().steps, owner=owner)
        except Exception as e:
            yield _sse({"type": "error", "message": f"流式处理出错：{e}"})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",   # 让 Render/Nginx 不缓冲，事件即时下发
        },
    )


@app.post("/reset")
def reset(req: ResetRequest, user: dict = Depends(get_current_user)):
    """清空某个会话的 LangGraph 上下文（不影响历史记录，历史由 chat_history 管理）。"""
    get_agent().reset_session(req.session_id)
    return {"status": "ok", "session_id": req.session_id}


# ===== 用户认证（注册 / 登录 / 退出 / 当前用户） =====
class AuthRequest(BaseModel):
    username: str = ""
    password: str = ""


@app.post("/auth/register")
def auth_register(req: AuthRequest, request: Request):
    """注册新用户；成功自动登录（写入会话 Cookie）。"""
    if not _rate_ok(request, "auth", 10, 60):
        raise HTTPException(status_code=429, detail="操作过于频繁，请稍后再试")
    try:
        u = auth_store.register_user(req.username, req.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    token = auth_store.create_session(u["id"])
    resp = JSONResponse({"username": u["username"]})
    _set_session_cookie(resp, token, request)
    return resp


@app.post("/auth/login")
def auth_login(req: AuthRequest, request: Request):
    """用户名 + 密码登录；成功写入会话 Cookie。"""
    if not _rate_ok(request, "auth", 10, 60):
        raise HTTPException(status_code=429, detail="操作过于频繁，请稍后再试")
    u = auth_store.verify_user(req.username, req.password)
    if not u:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = auth_store.create_session(u["id"])
    resp = JSONResponse({"username": u["username"]})
    _set_session_cookie(resp, token, request)
    return resp


@app.post("/auth/logout")
def auth_logout(request: Request):
    """注销当前会话（清除 Cookie）。"""
    token = request.cookies.get("session")
    auth_store.delete_session(token)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("session", path="/")
    return resp


@app.get("/auth/me")
def auth_me(request: Request):
    """返回当前登录用户；未登录返回 401。前端据此决定显示登录页还是主页。"""
    token = request.cookies.get("session")
    u = auth_store.get_session_user(token)
    if not u:
        raise HTTPException(status_code=401, detail="未登录")
    return {"username": u["username"], "id": u["id"]}


# ===== 账户（用户名）相关 =====
def _account_path() -> str:
    return os.path.join(DATA_DIR, "account.json")


def get_account() -> dict:
    """读取当前账户用户名；未设置返回空字符串。"""
    p = _account_path()
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return {"name": json.load(f).get("name", "") or ""}
        except Exception:
            pass
    return {"name": ""}


def set_account(name: str) -> dict:
    """保存用户名到 DATA_DIR/account.json（含非空 / 长度校验）。"""
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="名字不能为空")
    if len(name) > 40:
        raise HTTPException(status_code=400, detail="名字过长（最多 40 字）")
    with open(_account_path(), "w", encoding="utf-8") as f:
        json.dump({"name": name}, f, ensure_ascii=False)
    return {"name": name}


class AccountUpdate(BaseModel):
    name: str


@app.get("/account")
def account_get():
    """读取当前账户用户名。"""
    return get_account()


@app.post("/account")
def account_post(body: AccountUpdate):
    """设置 / 保存用户名（顾名思义：管理账户的名字）。"""
    return set_account(body.name)


# ===== 历史对话记录相关路由（均按登录用户隔离） =====
@app.get("/conversations")
def conversations(user: dict = Depends(get_current_user)):
    """列出当前登录用户的历史会话（按最近更新倒序）。"""
    return {"conversations": history.list_conversations(owner=user["id"])}


@app.get("/conversations/{sid}")
def conversation(sid: str, user: dict = Depends(get_current_user)):
    """获取某次会话的完整内容（含全部消息），用于回看；非本人会话视为不存在。"""
    c = history.get_conversation(sid, owner=user["id"])
    if not c:
        raise HTTPException(status_code=404, detail="会话不存在")
    return c


@app.post("/conversations")
def new_conversation(title: str = "新对话", user: dict = Depends(get_current_user)):
    """新建一个空会话（会出现在历史列表里），归属当前用户。"""
    return history.create_conversation(title=title, owner=user["id"])


@app.delete("/conversations/{sid}")
def del_conversation(sid: str, user: dict = Depends(get_current_user)):
    """删除一条历史会话（仅能删自己的）。"""
    return history.delete_conversation(sid, owner=user["id"])


# ===== 视觉理解（屏幕截图） =====
@app.post("/vision")
async def vision(image: str = Form(...), prompt: str = Form("请描述这张图片，并说明它能用来做什么")):
    """接收截图（base64 data URL 或纯 base64），用多模态模型理解。mock 模式返回演示文字。"""
    import base64
    if image.startswith("data:"):
        _, b64 = image.split(",", 1)
    else:
        b64 = image
    if get_agent().mock:
        return {"reply": "（演示模式）已收到你的截图 ✅\n接入真实多模态模型后即可识别图中内容——在部署平台的 Environment 里把 OPENAI_MODEL 设为支持视觉的模型（如 gpt-4o）并填入密钥即可。"}
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage
        model = os.getenv("OPENAI_MODEL_PRO", os.getenv("OPENAI_MODEL", "gpt-4o"))
        llm = ChatOpenAI(model=model, api_key=os.getenv("OPENAI_API_KEY"),
                         base_url=os.getenv("OPENAI_BASE_URL"), temperature=0)
        msg = HumanMessage(content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ])
        resp = llm.invoke([msg])
        return {"reply": resp.content}
    except Exception as e:
        raise _fail(500, "视觉识别失败，请稍后重试", e)


# ===== 语音识别（STT） =====
@app.post("/stt")
async def stt(audio: UploadFile = File(None)):
    """语音识别：接收音频，真实模式调 OpenAI whisper；mock 模式返回 501 提示用浏览器内置识别。"""
    if not audio or not audio.filename:
        raise HTTPException(status_code=400, detail="请提供音频文件")
    if get_agent().mock:
        raise HTTPException(status_code=501, detail="演示模式未启用云端语音识别，请使用浏览器内置语音输入（点击 🎤）")
    try:
        import openai
        import tempfile
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL"))
        suffix = os.path.splitext(audio.filename)[1] or ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
            shutil.copyfileobj(audio.file, tf)
            tmp = tf.name
        with open(tmp, "rb") as f:
            resp = client.audio.transcriptions.create(model="whisper-1", file=f)
        os.unlink(tmp)
        return {"text": resp.text}
    except Exception as e:
        raise _fail(500, "语音识别失败，请稍后重试", e)


# ===== 会话导出（Markdown / JSON） =====
@app.get("/conversations/{sid}/export")
def export_conversation(sid: str, format: str = "md"):
    """把某次会话导出为 Markdown 或 JSON 文件下载。"""
    c = history.get_conversation(sid)
    if not c:
        raise HTTPException(status_code=404, detail="会话不存在")
    if format == "json":
        data = json.dumps(c, ensure_ascii=False, indent=2)
        return Response(content=data, media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="conversation_{sid}.json"'})
    # Markdown
    title = (c.get("title") or "Mini Agent 对话").replace("#", "")
    lines = [f"# {title}", f"> 导出时间：{time.strftime('%Y-%m-%d %H:%M')}", ""]
    for m in c.get("messages", []):
        role = "🧑 用户" if m.get("role") == "user" else ("🤖 Mini Agent" if m.get("role") == "bot" else "系统")
        lines.append(f"## {role}")
        lines.append(m.get("text", ""))
        lines.append("")
    md = "\n".join(lines)
    return Response(content=md, media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="conversation_{sid}.md"'})


# ===== 连接器（Connectors）面板 API — 参考 Manus =====
@app.get("/connectors")
def list_connectors():
    """列出全部连接器及其连接状态。"""
    return {"connectors": connectors.list_connectors()}


@app.get("/connectors/{conn_id}")
def get_connector(conn_id: str):
    """获取单个连接器详情与状态。"""
    c = connectors.get_connector(conn_id)
    if not c:
        raise HTTPException(status_code=404, detail=f"连接器不存在: {conn_id}")
    return c


class ConnectRequest(BaseModel):
    config: dict | None = None   # 连接所需配置（如 GitHub token、Gmail credentials）


@app.post("/connectors/{conn_id}/connect")
def connect_connector(conn_id: str, req: ConnectRequest = ConnectRequest()):
    """连接一个连接器（可能需要附带配置）。"""
    result = connectors.connect_connector(conn_id, config=req.config)
    if not result.pop("ok", True):
        raise HTTPException(status_code=400, detail=result.get("message", "连接失败"))
    return result


@app.post("/connectors/{conn_id}/disconnect")
def disconnect_connector(conn_id: str):
    """断开一个连接器。"""
    result = connectors.disconnect_connector(conn_id)
    if not result.pop("ok", True):
        raise HTTPException(status_code=400, detail=result.get("message", "断开失败"))
    return result


# ── 各连接器的能力调用端点 ──
@app.post("/connectors/github/action")
def github_action(req: dict):
    action = req.get("action", "search_repos")
    params = req.get("params", {})
    return connectors.github_action(action, params)


@app.post("/connectors/calendar/action")
def calendar_action(req: dict):
    action = req.get("action", "list_events")
    params = req.get("params", {})
    return connectors.calendar_action(action, params)


@app.post("/connectors/notion/action")
def notion_action(req: dict):
    action = req.get("action", "list")
    params = req.get("params", {})
    return connectors.notion_action(action, params)


# ===== 长期记忆 =====
@app.post("/memory/clear")
def memory_clear():
    """清空长期记忆（主动遗忘）。"""
    try:
        memory.clear_memory()
        return {"ok": True, "message": "长期记忆已清空"}
    except Exception as e:
        raise _fail(500, "清空长期记忆失败，请稍后重试", e)


# ===== 学情档案 + 试卷分析（私人家教 Phase 2） =====
class ProfileUpdate(BaseModel):
    name: str = ""
    grade: str = ""
    subjects: dict = {}
    weak_points: list = []
    strengths: list = []
    goals: list = []


class PaperAnalyze(BaseModel):
    doc_id: str


class PlanCreate(BaseModel):
    goal: str = ""
    days: int = 14


@app.get("/profile")
def get_profile_route():
    """读取学情档案。"""
    from tutor import get_profile
    return {"profile": get_profile()}


@app.post("/profile")
def update_profile_route(req: ProfileUpdate):
    """局部更新学情档案。"""
    from tutor import update_profile
    partial = {k: v for k, v in req.dict().items() if v not in (None, "", [], {})}
    return {"profile": update_profile(partial)}


@app.get("/papers")
def list_papers_route():
    """列出已分析的试卷（不含全文）。"""
    from tutor import list_papers
    return {"papers": list_papers()}


@app.post("/analyze-paper")
def analyze_paper_route(req: PaperAnalyze):
    """分析一篇已上传的试卷文档，更新学情档案，返回分析摘要与分析结果。"""
    from tutor import analyze_exam_paper, get_profile
    try:
        summary = analyze_exam_paper(req.doc_id)
        # 返回结构：摘要文本 + 最新档案 + 最近一份试卷分析
        from tutor import list_papers
        papers = list_papers()
        return {
            "summary": summary,
            "profile": get_profile(),
            "paper": papers[0] if papers else None,
        }
    except Exception as e:
        raise _fail(500, "试卷分析失败，请稍后重试", e)


@app.post("/study-plan")
def study_plan_route(req: PlanCreate):
    """基于学情档案与历史试卷生成针对性提升计划（JSON）。"""
    from tutor import make_study_plan
    try:
        plan = make_study_plan(goal=req.goal, days=req.days)
        return {"plan": json.loads(plan) if isinstance(plan, str) else plan}
    except Exception as e:
        raise _fail(500, "生成计划失败，请稍后重试", e)


# ===== 定时任务（Schedules） =====
class ScheduleCreate(BaseModel):
    title: str = "定时任务"
    prompt: str
    recurrence: dict = {"type": "interval", "minutes": 60}


@app.get("/schedules")
def get_schedules():
    return {"schedules": schedules.list_schedules()}


@app.post("/schedules")
def create_schedule(req: ScheduleCreate):
    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt 不能为空")
    item = schedules.create_schedule(req.model_dump())
    return item


@app.delete("/schedules/{sid}")
def delete_schedule(sid: str):
    ok = schedules.delete_schedule(sid)
    if not ok:
        raise HTTPException(status_code=404, detail="定时任务不存在")
    return {"ok": True}


@app.post("/schedules/{sid}/tick")
def tick_schedule(sid: str):
    """前端 ticker 到点触发后调用：回写 last_run 并按 recurrence 重算 next_run。"""
    item = schedules.mark_run(sid)
    if not item:
        raise HTTPException(status_code=404, detail="定时任务不存在")
    return item


# ===== 子智能体（Sub-Agents） =====
class SubAgentCreate(BaseModel):
    name: str = "新子智能体"
    role: str = ""
    tools: list = []
    color: str = "#a855f7"
    icon: str = "🤖"


class SubAgentUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    tools: list | None = None
    color: str | None = None
    icon: str | None = None
    enabled: bool | None = None


class SubAgentRun(BaseModel):
    message: str
    session_id: str | None = None


@app.get("/sub-agents")
def get_sub_agents():
    return {"sub_agents": sub_agents.list_sub_agents()}


@app.post("/sub-agents")
def create_sub_agent(req: SubAgentCreate):
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="name 不能为空")
    item = sub_agents.create_sub_agent(req.model_dump())
    return item


@app.get("/sub-agents/{sid}")
def get_sub_agent(sid: str):
    s = sub_agents.get_sub_agent(sid)
    if not s:
        raise HTTPException(status_code=404, detail="子智能体不存在")
    return s


@app.put("/sub-agents/{sid}")
def update_sub_agent(sid: str, req: SubAgentUpdate):
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    item = sub_agents.update_sub_agent(sid, data)
    if not item:
        raise HTTPException(status_code=404, detail="子智能体不存在")
    return item


@app.delete("/sub-agents/{sid}")
def delete_sub_agent(sid: str):
    ok = sub_agents.delete_sub_agent(sid)
    if not ok:
        raise HTTPException(status_code=404, detail="子智能体不存在")
    return {"ok": True}


@app.post("/sub-agents/{sid}/run")
def run_sub_agent(sid: str, req: SubAgentRun):
    """直接运行一个子智能体处理 message，返回回复文本。"""
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="message 不能为空")
    reply = sub_agents.run_sub_agent(sid, req.message, session_id=req.session_id)
    return {"reply": reply, "sub_agent_id": sid}


# 部署版本标识（用于验证线上是否拉取到最新代码）
DEPLOY_TAG = "2026-07-21-hotfix4"


# ===== GitHub OAuth 授权流程 =====
import urllib.parse
import secrets

# 从环境变量读取（需在 Render 后台或 .env 中配置）
_GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
_GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
# 回调地址：自动根据请求根 URL 拼接，也可通过环境变量覆盖
_GITHUB_CALLBACK_OVERRIDE = os.getenv("GITHUB_CALLBACK_URL", "")


def _github_callback_url(request) -> str:
    """构建 GitHub OAuth 回调 URL。"""
    if _GITHUB_CALLBACK_OVERRIDE:
        return _GITHUB_CALLBACK_OVERRIDE
    # 从请求头推断根 URL
    host = request.headers.get("host", "")
    proto = request.headers.get("x-forwarded-proto", "https")
    return f"{proto}://{host}/auth/github/callback"


@app.get("/auth/github")
def github_auth_redirect(request: Request):
    """
    第一步：重定向到 GitHub OAuth 授权页面。
    用户在这里会看到和 Manus Connector 一样的官方授权界面：
      - App 名称、权限列表
      - 「授权」/「取消」按钮
    """
    if not _GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=501,
            detail="未配置 GITHUB_CLIENT_ID。请先在 GitHub 注册一个 OAuth App，"
                   "然后在 Render Environment 中填入 Client ID 和 Secret。",
        )

    # 生成随机 state 防 CSRF，持久化到 DB（重启 / 多实例也不丢，回调校验仍可靠）
    state = secrets.token_urlsafe(32)
    auth_store.save_oauth_state(state)

    params = urllib.parse.urlencode({
        "client_id": _GITHUB_CLIENT_ID,
        "redirect_uri": _github_callback_url(request),
        "scope": "repo read:org user:email",
        "state": state,
    })
    return RedirectResponse(url=f"https://github.com/login/oauth/authorize?{params}")


@app.get("/auth/github/callback")
async def github_auth_callback(code: str, state: str, request: Request):
    """
    第二步：GitHub 授权后回调。
    用 code 换 access token → 存入 connectors DB → 重定向回前端。
    """
    # 校验 state（DB 持久化：存在且未被消费过才放行；过期 state 已被清理任务回收）
    if not auth_store.consume_oauth_state(state):
        raise HTTPException(status_code=400, detail="授权状态无效或已过期，请重新连接 GitHub")

    if not code:
        raise HTTPException(status_code=400, detail="GitHub 未返回授权码")

    # 用 code 换 access token
    import httpx
    token_url = "https://github.com/login/oauth/access_token"
    data = {
        "client_id": _GITHUB_CLIENT_ID,
        "client_secret": _GITHUB_CLIENT_SECRET,
        "code": code,
        "redirect_uri": _github_callback_url(request),
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(token_url, data=data, headers={"Accept": "application/json"}, timeout=15)
            resp.raise_for_status()
            token_data = resp.json()
    except Exception as e:
        raise _fail(500, "GitHub 授权连接失败，请稍后重试", e)

    if "access_token" not in token_data:
        error_desc = token_data.get("error_description", token_data.get("error", "未知错误"))
        raise HTTPException(status_code=400, detail=f"GitHub 授权失败: {error_desc}")

    access_token = token_data["access_token"]

    # 获取用户信息（用于显示连接的是谁）
    async with httpx.AsyncClient() as client:
        user_resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {access_token}", "Accept": "application/vnd.github.v3+json"},
            timeout=10,
        )
        user_data = user_resp.json()

    github_login = user_data.get("login", "unknown")

    # 存入 connectors DB
    connectors.connect_connector("github", config={
        "token": access_token,
        "login": github_login,
        "auth_method": "oauth",
    })

    # 重定向回前端，带 hash 标记让 JS 知道连接成功
    return RedirectResponse(url=f"/ui#github-connected={github_login}")


# ===== 学习库（错题本 + 收藏） =====
class WrongQuestionCreate(BaseModel):
    subject: str = ""
    question: str = ""
    my_answer: str = ""
    correct_answer: str = ""
    explanation: str = ""


class WrongQuestionUpdate(BaseModel):
    subject: str | None = None
    question: str | None = None
    my_answer: str | None = None
    correct_answer: str | None = None
    explanation: str | None = None
    mastery: int | None = None


class WrongQuestionReview(BaseModel):
    mastery: int = 0


class FavoriteCreate(BaseModel):
    title: str = "收藏"
    content: str = ""


@app.get("/wrong-questions")
def get_wrong_questions(subject: str = ""):
    """列出错题本；可传 subject 按学科过滤。"""
    from library import list_wrong_questions
    return {"wrong_questions": list_wrong_questions(subject or None)}


@app.post("/wrong-questions")
def create_wrong_question(req: WrongQuestionCreate):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="题目不能为空")
    from library import add_wrong_question
    return add_wrong_question(req.model_dump())


@app.delete("/wrong-questions/{wid}")
def delete_wrong_question_route(wid: str):
    from library import delete_wrong_question
    if not delete_wrong_question(wid):
        raise HTTPException(status_code=404, detail="错题不存在")
    return {"ok": True}


@app.put("/wrong-questions/{wid}")
def update_wrong_question_route(wid: str, req: WrongQuestionUpdate):
    from library import update_wrong_question
    item = update_wrong_question(wid, req.model_dump(exclude_unset=True))
    if not item:
        raise HTTPException(status_code=404, detail="错题不存在")
    return item


@app.patch("/wrong-questions/{wid}/review")
def review_wrong_question_route(wid: str, req: WrongQuestionReview):
    """标记一次复习（艾宾浩斯复习闭环）：更新掌握度并推算下次复习时间。"""
    from library import review_wrong_question
    item = review_wrong_question(wid, req.mastery)
    if not item:
        raise HTTPException(status_code=404, detail="错题不存在")
    return item


@app.get("/wrong-questions/due")
def get_due_wrong_questions():
    """今日待复习的错题（下次复习时间已到或从未排期）。"""
    from library import due_wrong_questions
    due = due_wrong_questions()
    return {"due": due, "count": len(due)}


@app.get("/favorites")
def get_favorites():
    from library import list_favorites
    return {"favorites": list_favorites()}


@app.post("/favorites")
def create_favorite(req: FavoriteCreate):
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="内容不能为空")
    from library import add_favorite
    return add_favorite(req.model_dump())


@app.delete("/favorites/{fid}")
def delete_favorite_route(fid: str):
    from library import delete_favorite
    if not delete_favorite(fid):
        raise HTTPException(status_code=404, detail="收藏不存在")
    return {"ok": True}


@app.get("/version")
def version():
    return {"deploy_tag": DEPLOY_TAG, "status": "ok"}


@app.post("/debug/chat")
def debug_chat(req: ChatRequest):
    """无需登录的诊断接口——直接调 Agent 并返回完整原始响应，用于排查 undefined 等异常。
    ⚠️ 仅限排查使用，正式接口请用 /chat（需登录）。"""
    try:
        model_arg = MODEL_PRESETS.get(req.model) if req.model else None
        t0 = time.time()
        result = get_agent().run_trace(
            (req.session_id or f"debug-{uuid.uuid4().hex[:8]}"),
            req.message,
            max_steps=req.max_steps or 3,
            model=model_arg,
            persona=req.persona,
            style=req.style,
        )
        dt = round((time.time() - t0) * 1000)
        reply = result.get("reply", "")
        # 服务端兜底：字面量 "undefined" → 替换为明确错误信息
        if reply == "undefined" or (reply and str(reply).strip() == "undefined"):
            logger.warning("[debug_chat] 检测到字面量 'undefined' reply，已替换")
            reply = "⚠️ [诊断] 后端返回了字面量字符串 'undefined'，请检查 Agent / LLM 输出"
        return {
            "ok": True,
            "latency_ms": dt,
            "reply": reply,
            "reply_type": type(reply).__name__,
            "reply_len": len(reply),
            "reply_repr": repr(reply)[:200],
            "steps": result.get("steps", []),
            "needs_review": result.get("needs_review", False),
            "raw_result_keys": list(result.keys()),
            "result_types": {k: type(v).__name__ for k, v in result.items()},
        }
    except Exception as e:
        logger.error("[debug_chat] 异常: %s", e, exc_info=True)
        return {"ok": False, "error": str(e)[:500], "error_type": type(e).__name__}


# 允许通过 `python api.py` 直接启动，并支持平台注入的 PORT 环境变量
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("api:app", host="0.0.0.0", port=port)
