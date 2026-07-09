# mcp_server.py
# 路线 B：把 mini-agent 的「本地工具」暴露成一个标准 MCP Server（FastMCP 实现）。
# 这样 Claude Desktop、Cursor、Cline、以及任意 MCP 客户端都能即插即用地调用我们的工具。
#
# 与路线 A 的区别（帮小白分清两个方向）：
#   路线 A：我们的 Agent 是 MCP「客户端」，去连别人的 server（如 demo_mcp_server.py）。
#   路线 B：我们把自己的工具做成 MCP「服务端」，让别人（或我们自己的）客户端来连。
#
# 这是 MCP 协议最标准的「服务端」写法：每个工具 = 一个 Python 函数 + @mcp.tool() 装饰器。
#   函数签名（类型注解）自动变成工具的入参 schema；
#   docstring 自动变成工具说明（给大模型「看懂」用）。
#
# 工具逻辑只写一遍：这里直接复用 tools.py 里的底层函数（calculator / get_weather ...），
# 不重复维护两份代码 —— 改 tools.py，MCP server 自动跟着变。
#
# 启动方式（stdio 传输，是 MCP 客户端默认的、也最安全的连接方式）：
#   python mcp_server.py
# （Claude Desktop 等客户端会在自己的进程里拉起这个脚本，通过标准输入输出通信，不用开端口。）
#
# 想让远程客户端用 HTTP 连？把最后一行换成：
#   mcp.run(transport="streamable-http")   # 默认端口 8000，可加 host/port 参数

import sys

# 复用现有工具实现，保证「单一数据源」
import tools
from mcp.server.fastmcp import FastMCP

# MCP Server 的名字（客户端连接时看到的 server 标识）
mcp = FastMCP("mini-agent-local-tools")


@mcp.tool()
def calculator(expression: str) -> str:
    """计算四则运算表达式，例如 '23 * 4 + 1'。支持 + - * / 和括号。"""
    return tools.calculator(expression)


@mcp.tool()
def get_current_time() -> str:
    """返回当前的日期和时间（本地时区）。"""
    return tools.get_current_time()


@mcp.tool()
def save_note(title: str, content: str) -> str:
    """保存一条笔记。title: 笔记标题；content: 笔记内容。"""
    return tools.save_note(title, content)


@mcp.tool()
def read_notes() -> str:
    """读取所有已保存的笔记列表。"""
    return tools.read_notes()


@mcp.tool()
def get_weather(city: str) -> str:
    """查询城市当前天气（温度、天气状况、湿度、风速）。city 支持中文或英文，如 '北京' / 'Tokyo'。"""
    return tools.get_weather(city)


@mcp.tool()
def web_search(query: str) -> str:
    """联网搜索资料（基于维基百科公开数据，无需 Key），返回最相关的摘要与来源链接。"""
    return tools.web_search(query)


@mcp.tool()
def save_memory(text: str) -> str:
    """把用户透露的重要长期信息存入记忆，例如姓名、喜好、计划、关键事实，方便以后跨对话回忆。"""
    return tools.save_memory(text)


@mcp.tool()
def search_memory(query: str) -> str:
    """从长期记忆中检索与 query 相关的信息，用于主动"回忆"用户之前说过的话。"""
    return tools.search_memory_tool(query)


if __name__ == "__main__":
    # 默认 stdio 传输：MCP 客户端通过标准输入输出与本进程通信（最常见、最安全，无需开端口）。
    mcp.run()
