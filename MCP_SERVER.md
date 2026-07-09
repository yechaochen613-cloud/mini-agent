# 路线 B：把本地工具做成 MCP Server（`mcp_server.py`）

> 配套路线 A（Agent 当 MCP 客户端，见 `agent_langgraph.py` + `demo_mcp_server.py`）。
> 这条路线反过来：**把我们自己手写的工具，用 MCP 协议暴露出去**，让别的客户端也能调。

---

## 它解决了什么

之前我们的 8 个工具（`calculator` / `get_weather` / `save_note` …）只活在 `tools.py` 里，
只有「我们自己的 Agent」能用。现在把它们封装成标准 MCP Server 后，**任何实现了 MCP 的客户端**
（Claude Desktop、Cursor、Cline、VS Code Copilot 自定义、甚至你另一个 Agent）都能即插即用。

一句话：**从「自己人用」变成「全行业通用插头」。**

---

## 文件构成

| 文件 | 作用 |
|------|------|
| `mcp_server.py` | 路线 B 核心。用 `FastMCP` 把 8 个本地工具 `@mcp.tool()` 暴露成 MCP 工具。逻辑全部复用 `tools.py`，不重复写。 |
| `tools.py` | 真正的工具实现（被 `mcp_server.py` import 复用）。 |
| `mcp_servers_local.json` | 一份「反向整合」演示配置：让路线 A 的 Agent 也通过 MCP 协议加载这 8 个本地工具，证明「本地工具 MCP 化后代码不用改」。 |

---

## 用法一：给 Claude Desktop / Cursor 等外部客户端用

### 1. 确认能独立启动
```bash
cd mini-agent
python mcp_server.py        # stdio 模式，启动后进程会一直挂着等待客户端连接
```

### 2. 在客户端配置里登记这个 server

**Claude Desktop**（`claude_desktop_config.json`，位置见官方文档）：
```json
{
  "mcpServers": {
    "mini-agent-tools": {
      "command": "/Users/tawei/.workbuddy/binaries/python/envs/default/bin/python",
      "args": ["/Users/tawei/WorkBuddy/2026-07-08-10-56-46/mini-agent/mcp_server.py"]
    }
  }
}
```
> ⚠️ 重点：**`command` 用绝对路径的 Python**（要能 `import mcp`，所以用本项目 venv 的解释器）；
> **`args` 用 `mcp_server.py` 的绝对路径**。相对路径在客户端进程里会找不到文件。

**Cursor / Cline** 的 MCP 配置字段名可能略有不同，但本质都是 `command` + `args`（stdio 模式）。

### 3. 重启客户端，验证

在客户端里问「帮我算一下 (88+12)*3」「北京天气怎么样」「记一条笔记：买牛奶」，
如果工具能被调用、结果能回显，说明我们的 MCP Server 被成功接入了。

---

## 用法二：让「自己的 Agent」也通过 MCP 加载本地工具（反向整合演示）

这能直观证明：**工具从「import 本地函数」换成「MCP 协议拉取」，Agent 业务代码一行都不用改。**

```bash
cd mini-agent
MCP_SERVERS_FILE=mcp_servers_local.json PORT=8055 \
  python -m uvicorn api:app --host 0.0.0.0 --port 8055 --log-level warning
```
然后访问 `http://localhost:8055/tools`，你会看到工具清单里仍然有这 8 个工具——
只不过它们现在是通过 `mcp_server.py` 子进程、走 stdio 协议被 Agent 调用的（不是直接 import）。
`agent_langgraph.py` 在合并工具时已按名字去重，所以不会出现重复工具、也不会影响现有行为。

---

## 和安全相关的提醒

- `mcp_server.py` 里的 `save_note` / `save_memory` 是**有副作用**的写操作。
  当**别的客户端**直接连这个 server 时，写操作会**立即执行、没有人工审核**——
  因为人工审核（HITL）是「Agent 侧」的逻辑（在 `agent_langgraph.py` 的 `review_node`），
  不在 MCP server 里。换句话说：把写工具暴露给外部客户端，等于把「能不能写」的开关交给了对方。
  - 学习/个人用：没问题。
  - 给别人用：建议在客户端侧或 server 侧再加一道确认（比如给这些工具单独包一层确认逻辑）。
- `web_search` / `get_weather` 会**真实联网**（维基百科 / Open-Meteo），注意运行环境能否访问外网。

---

## 下一步可以玩的方向

- 给 `mcp_server.py` 加 HTTP 传输（`mcp.run(transport="streamable-http")`），让远程客户端也能连。
- 把更多能力（比如读文件、查数据库）做成 MCP 工具，逐步把本地能力「插件化」。
- 反过来：在 `mcp_servers.json` 里加入社区现成 server（文件系统、GitHub、PostgreSQL…），
  让 Agent 的工具数从 8 个变成上千个（路线 A 的威力）。
