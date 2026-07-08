# 部署与上线指南（Mini Agent）

本项目 = FastAPI 后端（调大模型 + 工具调用）+ 内置网页聊天界面（PWA）。
要"发给朋友用"，就是把后端跑在一台公网可达的服务器上，并把你的模型 Key 配到服务器的环境变量。

> ⚠️ 安全底线：Key 只放在平台的环境变量 / 密钥管理里，不要写进代码或提交到 Git（`.gitignore` 已忽略 `.env`）。

---

## 我已经帮你准备好的东西（部署零配置）

为了让部署尽量"傻瓜化"，仓库里已经放了：

- `requirements.txt` —— **已锁定版本**，保证云端装出来的依赖和你本地跑通的一致，不会出现"本地好使、上线炸"的情况。
- `render.yaml` —— Render 的 Blueprint 文件。推到 GitHub 后，在 Render 后台点一下就能按它自动建好服务（构建命令、启动命令、健康检查、Python 版本都写好了）。
- `Procfile` —— `web: uvicorn api:app --host 0.0.0.0 --port $PORT`，Railway / 其他 PaaS 通用。
- 代码已支持平台注入的 `PORT` 环境变量，无需任何改动。

---

## 方式一：Render（推荐新手，几分钟，免费）

1. 把本仓库推到 GitHub（见文末命令）。
2. 打开 https://dashboard.render.com → **New** → **Blueprint** → 选中你的仓库。
3. Render 会自动按 `render.yaml` 创建 Web Service。**唯一要手动填的**：在 Environment 里补全三个密钥
   （`render.yaml` 里用 `sync: false` 标记了，不会从仓库读）：
   ```
   OPENAI_API_KEY=你的智谱Key
   OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
   OPENAI_MODEL=glm-4-flash
   ```
   （`PYTHON_VERSION=3.11`、`MOCK=false` 已在文件里设好，不用动。）
4. 点 Deploy。完成后得到一个 `https://你的项目.onrender.com`，打开 `/ui` 就能聊天。

> 免费版特性：15 分钟无访问会休眠，下次访问冷启动约几秒；redeploy 会重置运行时写的 `notes.json` / `memory.json`（见下方"已知注意"）。

---

## 方式二：Railway（不用 GitHub，本地直接推，免费额度）

1. 装 CLI：`npm i -g @railway/cli` 然后 `railway login`。
2. 在项目目录执行：
   ```bash
   railway init        # 新建项目
   railway up          # 把当前目录直接部署上去（不需要 Git）
   ```
3. 在 Railway 后台的 Variables 里加上面 4 个环境变量。
4. 生成域名即可分享（Railway 也支持 `$PORT`，已兼容）。

---

## 环境变量一览

| 变量 | 说明 | 示例 |
|------|------|------|
| `OPENAI_API_KEY` | 模型 API Key（**必填，机密**） | `你的智谱Key` |
| `OPENAI_BASE_URL` | 兼容 OpenAI 的端点 | `https://open.bigmodel.cn/api/paas/v4/` |
| `OPENAI_MODEL` | 模型名 | `glm-4-flash` |
| `MOCK` | `true`=离线演示不调模型；`false`=联网 | `false` |
| `PORT` | 平台注入的监听端口 | `8000`（本地）/ 由平台给 |

---

## 已知注意（上线前要知道）

- **运行时数据不持久**：`notes.json` / `memory.json` 写在容器磁盘上。Render 免费版的磁盘在每次 redeploy 会被重置，所以"记的笔记 / 长期记忆"重启后可能清空。Agent 的多轮会话存在内存（`MemorySaver`），重启同样会丢。
  - 想要"重启不丢"：下一步做 **SqliteSaver + 挂载 Render Disk**（把 checkpoint 和记忆落到持久卷），这也是生产标配。
- **CORS**：当前 `allow_origins=["*"]` 方便演示，正式产品改成你的前端域名。
- **限流**：当前是单进程内存限流（60 次/分），多副本时需要换 Redis 共享计数。
- **鉴权**：仅给朋友用，可加一个简单口令（请求头带 token），避免被陌生人刷额度。

---

## 推到 GitHub 的命令（我已在本地 `git init` 并提交）

```bash
git remote add origin https://github.com/你的用户名/mini-agent.git
git branch -M main
git push -u origin main
```

（`.env`、`notes.json`、`memory.json`、`__pycache__` 都已被 `.gitignore` 忽略，不会进仓库。）
