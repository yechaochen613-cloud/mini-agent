# demo_mcp_server.py
# 一个最小可运行的 MCP Server，用 FastMCP 暴露两个工具，专门用来演示：
#   我们的 mini-agent 通过 MCP 协议，跨进程调用「别人（或你自己）写的工具」。
#
# 这个 server 会被 agent_langgraph.py 在启动时以 stdio 方式拉起（见 mcp_servers.json），
# 它的工具会被自动合并进 Agent 的工具箱，和大模型对话时就能直接调用。
#
# 想加自己的工具？照着下面 @mcp.tool() 的样子写一个函数即可，无需改 Agent 代码。

import datetime
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("demo-server")


@mcp.tool()
def reverse_text(text: str) -> str:
    """把一段文本反转（例如 'hello' -> 'olleh'）。用于演示 Agent 跨进程调用 MCP 工具。"""
    return text[::-1]


@mcp.tool()
def get_server_time() -> str:
    """返回 MCP server 进程当前的服务器时间，用于证明工具确实运行在独立进程里。"""
    return datetime.datetime.now().strftime("MCP server 时间: %Y-%m-%d %H:%M:%S")


if __name__ == "__main__":
    # 默认 transport 就是 stdio：从 stdin 读 JSON-RPC，往 stdout 写结果，
    # 由 agent_langgraph.py 作为子进程拉起并通信。
    mcp.run()
