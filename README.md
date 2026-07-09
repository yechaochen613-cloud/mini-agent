# Mini-Agent · 会自己调工具的中文智能体

一个基于 **FastAPI + LangGraph** 的中文对话智能体，支持工具调用、文档理解（多格式上传 / 跨文档比对）、历史对话持久化。前端是一个内置的聊天界面（`/ui`）。

> 标语：*the future* — 会自己调工具的中文智能体。

---

## ✨ 功能一览

- 🤖 **工具调用**：内置联网搜索、计算、笔记、记忆、时间等工具，Agent 自主决定何时调用（基于 LangGraph ReAct 循环）。
- 📎 **文档理解引擎**：上传 PDF / Word / Excel / PPT / CSV / HTML / 网页 / Markdown / 图片等，自动解析、抽取**表格 / 条款 / 层级结构**，支持**百万字级长文档**与**跨文档关联比对**。
- 🕘 **历史对话**：左侧抽屉查看 / 回看 / 删除历史会话，刷新不丢。
- 💾 **持久化**：对话历史落 **SQLite**，上传文件 / 文档索引 / 记忆 / 笔记统一写入持久目录；部署到 Render 并挂载 Disk 后，**重启 / redeploy 数据不丢**。
- 🎭 **Mock 模式**：不配置任何密钥也能跑（用内置 Mock LLM 演示工具链路），开箱即用。

---

## 🗂️ 目录结构（关键文件）

```
mini-agent/
├── api.py              # FastAPI 入口，把 Agent 包成 HTTP 接口 + 内置聊天界面 /ui
├── agent_langgraph.py  # LangGraph 版 Agent Loop（工具调度核心）
├── tools.py            # 工具定义（搜索/计算/笔记/记忆/文档…），含 MCP 扩展位
├── documents.py        # 文档理解引擎（解析 / 抽取 / 检索 / 比对，依赖懒加载）
├── chat_history.py     # 对话历史，SQLite 持久化（conversations / messages 两表）
├── storage.py          # 统一持久化目录 DATA_DIR（Render Disk 优先，否则 data/）
├── memory.py           # Agent 长期记忆
├── mock_llm.py         # Mock LLM（MOCK=true 时启用）
├── index.html          # 聊天界面前端
├── requirements.txt    # 锁版依赖
├── render.yaml         # Render Blueprint 一键部署配置（含 1GB 持久盘）
└── data/               # 运行时数据（对话 SQLite / 上传文件 / 索引…），已被 .gitignore 忽略
```

---

## 💻 本地开发

要求 Python 3.11+。

```bash
cd mini-agent

# 1. 建虚拟环境并装依赖
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. 启动（--reload 热重载，方便调试）
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

启动后：

- 聊天界面：<http://localhost:8000/ui>
- 接口文档（自动生成）：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/health>

本地未设 `RENDER_DISK_MOUNT_PATH` 时，数据回退写到项目内 `data/`（已被 git 忽略）。

---

## 🚀 部署到 Render（拿固定公网地址）

本仓库自带 `render.yaml`，用 **Blueprint** 方式一键部署，自动挂载持久盘，重启 / redeploy 数据不丢。

### 方式一：Blueprint 自动部署（推荐）

1. 把本仓库推到 GitHub。
2. 打开 <https://dashboard.render.com> → **New** → **Blueprint**。
3. 连接你的 GitHub 仓库，Render 会自动读取 `render.yaml` 并创建名为 `mini-agent` 的 Web 服务。
4. 在 **Environment** 里按需填写密钥（见下表，`sync: false` 的变量不会从仓库读取，需手动填）。
5. 点击 **Deploy**，完成后得到固定地址 `https://mini-agent-xxxx.onrender.com`。

> `render.yaml` 默认 `MOCK=true`，**不填任何密钥也能直接跑起来**（用 Mock LLM 演示工具链路）。
> 想接真实大模型，把 `MOCK` 改为 `false` 并填好下方三个密钥即可。

### 方式二：手动新建 Web Service

如果你不想用 Blueprint，也可以手动建：

- **Environment**: `Python 3.11`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn api:app --host 0.0.0.0 --port $PORT`
- **Health Check Path**: `/health`
- **Disk**（关键，否则数据随容器销毁）：Mount Path `/var/data`，Size `1 GB`（名字随意）
- **环境变量**：见下表

---

## 🔐 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `MOCK` | 否 | `true` | `true`=使用内置 Mock LLM（无需密钥即可演示）；`false`=接入真实 OpenAI 兼容接口 |
| `OPENAI_API_KEY` | MOCK=false 时必填 | 空 | 大模型 API Key |
| `OPENAI_BASE_URL` | 否 | OpenAI 官方 | OpenAI 兼容网关地址（如第三方代理 / 国内转发） |
| `OPENAI_MODEL` | 否 | 见代码 | 使用的模型名 |
| `PYTHON_VERSION` | 否 | `3.11` | 运行环境 Python 版本 |
| `RENDER_DISK_MOUNT_PATH` | 否 | 空 | Render Disk 挂载点（如 `/var/data`）。设置后数据写到 `<挂载点>/mini-agent`，实现持久化 |

> 密钥类变量（`OPENAI_*`）在 `render.yaml` 中标记为 `sync: false`，**务必在 Render 后台手动填写**，不要写进仓库。

---

## 💾 持久化说明

数据统一由 `storage.py` 管理：

- 设了 `RENDER_DISK_MOUNT_PATH`（如 `/var/data`）→ 数据落 `<挂载点>/mini-agent`
- 未设 → 回退到项目内 `data/`

持久盘（Render Disk）在重启 / redeploy 后保留，因此对话历史（SQLite）、上传文件、文档索引、记忆、笔记都不会丢。

对话历史使用 `PRAGMA journal_mode=DELETE`（每次 commit 直接落主库），避免 WAL 在异常退出时丢失已提交数据。

---

## 📌 限制与备注

- **免费版休眠**：Render 免费 plan 在一段时间无访问后会休眠，首次访问需冷启动（数秒），属正常。
- **OCR 可选**：扫描件 / 图片的文字识别依赖系统级 `tesseract`，云端未安装则自动降级（不报错，只是跳过 OCR）。
- **区域选择**：`render.yaml` 默认 `region: oregon`；离国内更近可在 Render 后台改成 `singapore`。
- **Disk 大小**：当前 `sizeGB: 1`；文档量很大可在 `render.yaml` 调大（或后台改）。

---

## 🧪 接口速查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查（部署 Health Check 用） |
| GET | `/ui` | 聊天界面 |
| POST | `/chat` | 发消息，返回 Agent 回复（自动落历史） |
| GET | `/conversations` | 历史会话列表 |
| DELETE | `/conversations/{id}` | 删除某个会话 |
| POST | `/upload` | 上传文档（multipart，字段 `files`） |
| GET | `/documents` | 已上传文档列表 |
| POST | `/documents/search` | 文档内检索 |
| POST | `/documents/compare` | 跨文档比对 |

完整字段见 `/docs` 自动生成的 Swagger 文档。
