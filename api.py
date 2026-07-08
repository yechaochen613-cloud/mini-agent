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
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import time
import uuid
from collections import deque

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
        return ChatResponse(
            reply=result["reply"], steps=result["steps"], session_id=session_id,
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
    return ChatResponse(
        reply=result["reply"], steps=result["steps"], session_id=session_id,
        needs_review=result.get("needs_review", False), review=result.get("review"),
    )


@app.post("/reset")
def reset(req: ResetRequest):
    """清空某个会话的历史，相当于"开启新对话"。"""
    agent.reset_session(req.session_id)
    return {"status": "ok", "session_id": req.session_id}


# 允许通过 `python api.py` 直接启动，并支持平台注入的 PORT 环境变量
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("api:app", host="0.0.0.0", port=port)
