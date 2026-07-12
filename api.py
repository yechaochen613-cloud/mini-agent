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
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse
from fastapi import File, UploadFile, Form
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import json
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


def _sse(event: dict) -> str:
    """把一个 dict 格式化成一行 SSE data（UTF-8，安全）。"""
    return "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"


# 启动时构建一个全局 Agent 实例（复用连接，避免每次请求都重建）
_api_key = os.getenv("OPENAI_API_KEY")
_base_url = os.getenv("OPENAI_BASE_URL")
# 只要配置了真实密钥就强制走真模型，忽略 MOCK 开关（防 dashboard 残留 MOCK=true 导致假模式）
_mock = os.getenv("MOCK", "false").lower() == "true" and not (_api_key and _base_url)
agent = Agent(
    api_key=_api_key,
    base_url=_base_url,
    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    mock=_mock,
)

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
def chat(req: ChatRequest):
    if not _rate_ok():
        raise HTTPException(status_code=429, detail="请求太频繁，请稍后再试")

    session_id = req.session_id

    # 前端模型档位（1.0/lite/pro）映射到真实模型名，仅非 mock 模式生效
    model_arg = MODEL_PRESETS.get(req.model) if req.model else None

    # 情况 A：人类答复了某个待审批操作 -> 用 review_decision 唤醒被中断的图
    if req.review_decision is not None:
        if not session_id:
            raise HTTPException(status_code=400, detail="review_decision 必须带上 session_id")
        result = agent.run_trace(
            session_id, user_input=None, max_steps=req.max_steps,
            review_decision=req.review_decision, model=model_arg,
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
    result = agent.run_trace(session_id, req.message, max_steps=req.max_steps, model=model_arg)
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


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    """流式对话（SSE）：边执行边吐事件，让前端实时呈现"执行步骤"与打字机式回复。
    对标 Manus 的"活着的智能体"体感。历史记录在服务端落库（用户消息 + 最终回复）。"""
    if not _rate_ok():
        raise HTTPException(status_code=429, detail="请求太频繁，请稍后再试")

    session_id = req.session_id or str(uuid.uuid4())
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
                result = agent.run_trace(
                    session_id, user_input=None, max_steps=req.max_steps,
                    review_decision=req.review_decision, model=model_arg,
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
                history.append_message(session_id, "user", req.message, title=title)
            for ev in agent.run_stream(session_id, req.message, max_steps=req.max_steps, model=model_arg):
                if ev.get("type") == "done":
                    final_reply = ev.get("reply", "")
                yield _sse(ev)
            # 流式结束，落库最终回复（带上逐步记录）
            if final_reply:
                history.append_message(session_id, "bot", final_reply, agent.steps)
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
def reset(req: ResetRequest):
    """清空某个会话的 LangGraph 上下文（不影响历史记录，历史由 chat_history 管理）。"""
    agent.reset_session(req.session_id)
    return {"status": "ok", "session_id": req.session_id}


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


# ===== 视觉理解（屏幕截图） =====
@app.post("/vision")
async def vision(image: str = Form(...), prompt: str = Form("请描述这张图片，并说明它能用来做什么")):
    """接收截图（base64 data URL 或纯 base64），用多模态模型理解。mock 模式返回演示文字。"""
    import base64
    if image.startswith("data:"):
        _, b64 = image.split(",", 1)
    else:
        b64 = image
    if agent.mock:
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
        raise HTTPException(status_code=500, detail=f"视觉识别失败：{e}")


# ===== 语音识别（STT） =====
@app.post("/stt")
async def stt(audio: UploadFile = File(None)):
    """语音识别：接收音频，真实模式调 OpenAI whisper；mock 模式返回 501 提示用浏览器内置识别。"""
    if not audio or not audio.filename:
        raise HTTPException(status_code=400, detail="请提供音频文件")
    if agent.mock:
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
        raise HTTPException(status_code=500, detail=f"语音识别失败：{e}")


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
        raise HTTPException(status_code=500, detail=str(e))


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
DEPLOY_TAG = "2026-07-12-subagents-schedules"


@app.get("/version")
def version():
    return {"deploy_tag": DEPLOY_TAG, "status": "ok"}


# 允许通过 `python api.py` 直接启动，并支持平台注入的 PORT 环境变量
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("api:app", host="0.0.0.0", port=port)
