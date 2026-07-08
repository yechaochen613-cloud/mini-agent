# agent_langgraph.py
# 用 LangGraph 重写的 Agent Loop —— 对应路线图阶段 4（框架实战：LangGraph 为主）
#
# 和手写版 agent.py 的关键对比（行为完全一致，工具/记忆/接口全复用）：
#   · 手写版：自己写 for 循环，手动把 assistant / tool 消息 append 进对话历史
#   · LangGraph 版：把"推理节点(agent)"和"工具节点(tools)"画成一张有向图，
#                   由框架负责"最后一条消息要不要继续调工具"的分支判断与循环
#   · 好处：循环/分支逻辑交给框架，节点可独立测试、可加 checkpoint（持久化）、
#           可观测（LangSmith）、可拼成更复杂的图（多 Agent、人工介入……）
#
# 本文件在阶段 4 基础上增加了【人工审核节点 / Human-in-the-loop】：
#   当 Agent 想执行"有副作用"的工具（save_note 写笔记、save_memory 写长期记忆）时，
#   图会先进入 review 节点并调用 interrupt() 暂停，把待执行的操作交给人类确认
#   （通过 / 拒绝 / 修改参数），确认后再真正执行。
#   这是 LangGraph 最经典、也最实用的生产级模式之一。
#
# 对外接口（兼容手写版，并扩展了 review）：
#   __init__(api_key, base_url, model, mock)
#   run_trace(session_id, user_input, max_steps, review_decision=None)
#       -> {"reply", "steps"}                                   （正常结束）
#       -> {"needs_review": True, "review": {...}}              （等待人类审批）
#   reset_session(session_id)
#   self.steps  （可观测性，记录本轮调过的工具）

import json
from typing import Annotated, TypedDict, Optional
from pydantic import Field, create_model

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphRecursionError
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    HumanMessage, SystemMessage, AIMessage, ToolMessage,
)
from langchain_core.tools import StructuredTool

from tools import TOOL_FUNCTIONS, TOOL_SCHEMAS
from memory import relevant_context


# ===== 哪些工具需要"人类审批"后才能执行（有副作用 / 会写入持久化数据） =====
# 计算、查时间、查天气、联网搜索、读笔记、回忆记忆 —— 都是只读/无副作用，自动放行。
# 写笔记、写长期记忆 —— 会改变外部状态，先问人类一声。
HUMAN_APPROVAL_TOOLS = {"save_note", "save_memory"}


# ---------------- 把现有工具的 JSON Schema 转换成 LangChain 需要的 pydantic 模型 ----------------
# 这样 TOOL_SCHEMAS（tools.py 里的"说明书"）就是唯一的真相来源，不重复写参数定义。
_TYPE_MAP = {"string": str, "integer": int, "number": float, "boolean": bool}


def _schema_to_model(func_name, schema_func):
    props = schema_func["parameters"].get("properties", {})
    required = schema_func["parameters"].get("required", [])
    fields = {}
    for pname, pspec in props.items():
        py_type = _TYPE_MAP.get(pspec.get("type"), str)
        desc = pspec.get("description", "")
        if pname in required:
            fields[pname] = (py_type, Field(description=desc))
        else:
            fields[pname] = (Optional[py_type], Field(default=None, description=desc))
    if not fields:
        return create_model(f"{func_name}_Args")
    return create_model(f"{func_name}_Args", **fields)


# 模块加载时一次性把 TOOL_FUNCTIONS 包装成 LangChain 工具（函数 + 说明书来自 tools.py）
_LG_TOOLS = []
for _s in TOOL_SCHEMAS:
    _f = _s["function"]
    _fn = TOOL_FUNCTIONS[_f["name"]]
    _args = _schema_to_model(_f["name"], _f)
    _LG_TOOLS.append(StructuredTool.from_function(
        func=_fn,
        name=_f["name"],
        description=_f["description"],
        args_schema=_args,
    ))


class Agent:
    def __init__(self, api_key, base_url=None, model="gpt-4o-mini", mock=False):
        self.mock = mock
        self.model = model
        self.steps = []        # 记录本轮调用过的工具，方便对外暴露（可观测性）
        self._pending = set()  # 哪些 session 当前正卡在"等待人类审批"
        # 注意：对话历史现在交给 LangGraph 的 checkpointer（按 thread_id 管理），
        #       不再用 self.sessions 自己维护；服务重启仍然会丢（MemorySaver 在内存里）。

        if not mock:
            llm = ChatOpenAI(
                model=model,
                api_key=api_key,
                base_url=base_url,
                temperature=0,   # 工具调用追求确定性，temperature 设 0
            )
            self.llm_with_tools = llm.bind_tools(_LG_TOOLS)
        else:
            # MOCK 模式：不绑定真实 LLM，agent 节点改用离线"假大脑"
            self.llm_with_tools = None

        # ---- 构建 LangGraph 图（online / mock 共用同一张图，只有 agent 节点内部不同） ----
        class State(TypedDict):
            # add_messages 是 LangGraph 的"消息归约器"：新消息自动追加，而非整体替换
            messages: Annotated[list, add_messages]

        def agent_node(state):
            """推理节点：注入记忆 → 调 LLM（或 mock）→ 返回模型这条消息。"""
            msgs = list(state["messages"])
            # 找出最后一条 user 消息，用于检索相关长期记忆
            last_user = ""
            for m in reversed(msgs):
                if isinstance(m, HumanMessage):
                    last_user = m.content
                    break
            system_content = self._build_system(last_user)
            # 每轮重新注入（带最新记忆）的 system，插到最前；它只传给 LLM，不写回 state
            if msgs and isinstance(msgs[0], SystemMessage):
                msgs[0] = SystemMessage(content=system_content)
            else:
                msgs.insert(0, SystemMessage(content=system_content))

            if self.mock:
                from mock_llm import mock_respond
                resp = mock_respond([_lc_to_dict(m) for m in msgs])
                tool_calls = []
                if getattr(resp, "tool_calls", None):
                    for tc in resp.tool_calls:
                        tool_calls.append({
                            "id": tc.id,
                            "name": tc.function.name,
                            "args": json.loads(tc.function.arguments or "{}"),
                        })
                ai = AIMessage(content=resp.content or "", tool_calls=tool_calls)
            else:
                ai = self.llm_with_tools.invoke(msgs)
            return {"messages": [ai]}

        def review_node(state):
            """人工审核节点：把"有副作用"的工具调用列出来，交给人类确认后再放行。"""
            last = state["messages"][-1]
            tool_calls = list(last.tool_calls) if getattr(last, "tool_calls", None) else []
            sensitive = [tc for tc in tool_calls if tc["name"] in HUMAN_APPROVAL_TOOLS]
            safe = [tc for tc in tool_calls if tc["name"] not in HUMAN_APPROVAL_TOOLS]

            # 给人类看的待审批清单（只列需要审批的，安全工具默认放行）
            actions = []
            for tc in sensitive:
                label, detail = _describe_action(tc["name"], tc["args"])
                actions.append({
                    "id": tc["id"], "name": tc["name"],
                    "label": label, "detail": detail, "args": tc["args"],
                })

            # ★ 关键：在这里暂停，把决策权交给人类。
            #   interrupt() 会让 graph.invoke() 立即返回，并把 actions 透传出来；
            #   人类答复后，用 Command(resume=decision) 唤醒，interrupt() 才会"返回值"继续往下走。
            decision = interrupt({"type": "approval", "actions": actions})

            # ---- 以下代码在"人类答复后"才执行 ----
            d = decision.get("decision", "approve_all") if isinstance(decision, dict) else "approve_all"
            approved = set(decision.get("approved", [])) if isinstance(decision, dict) else set()
            rejected = set(decision.get("rejected", [])) if isinstance(decision, dict) else set()
            edits = decision.get("edits", {}) if isinstance(decision, dict) else {}

            new_tcs = list(safe)     # 安全工具直接放行
            reject_msgs = []         # 被拒绝的工具 -> 生成 ToolMessage 让模型知道"没办成"
            for tc in sensitive:
                if d == "reject_all" or tc["id"] in rejected:
                    reject_msgs.append(ToolMessage(
                        content=f"用户拒绝了执行 {tc['name']}。", tool_call_id=tc["id"]))
                elif d == "approve_all" or tc["id"] in approved or tc["id"] in edits:
                    if tc["id"] in edits:
                        m = dict(tc)
                        m["args"] = edits[tc["id"]]
                        new_tcs.append(m)
                    else:
                        new_tcs.append(tc)
                else:
                    # custom 模式下没有被明确列出的敏感工具：默认拒绝（更安全）
                    reject_msgs.append(ToolMessage(
                        content=f"用户未批准执行 {tc['name']}，已跳过。", tool_call_id=tc["id"]))

            # 用相同 id 替换 AIMessage，更新它的 tool_calls（LangGraph 按 id 识别并原地更新）
            updates = []
            if new_tcs != tool_calls:
                updates.append(AIMessage(content=last.content or "", tool_calls=new_tcs, id=last.id))
            updates.extend(reject_msgs)

            if new_tcs:
                # 还有要执行的工具 -> 去 tools 节点
                update = {"messages": updates} if updates else {}
                return Command(goto="tools", update=update)
            # 全被拒了 -> 回 agent 节点，让模型向用户说明"没能办成"
            return Command(goto="agent", update={"messages": updates})

        def route_from_agent(state):
            """分支：有工具调用且含敏感工具 -> review；有工具调用但都是安全的 -> tools；否则结束。"""
            last = state["messages"][-1]
            if not getattr(last, "tool_calls", None):
                return END
            names = [tc["name"] for tc in last.tool_calls]
            if any(n in HUMAN_APPROVAL_TOOLS for n in names):
                return "review"
            return "tools"

        builder = StateGraph(State)
        builder.add_node("agent", agent_node)
        builder.add_node("tools", ToolNode(_LG_TOOLS))   # 框架预置：执行工具 → 返回 ToolMessage
        builder.add_node("review", review_node)          # 人工审核节点
        builder.add_edge(START, "agent")                 # 入口：先走推理
        builder.add_conditional_edges("agent", route_from_agent)
        builder.add_edge("tools", "agent")               # 工具结果送回推理，形成循环
        # review 节点内部用 Command 决定去 tools 还是回到 agent，无需额外边
        # ★ 用 MemorySaver 做 checkpointer —— 这是 interrupt() 能暂停/恢复的底座
        self.app = builder.compile(checkpointer=MemorySaver())

    def _build_system(self, user_input):
        """构建 system 提示：基础人设 + 当前问题相关的长期记忆（每轮重新计算，保证记忆新鲜）。"""
        try:
            mem_ctx = relevant_context(user_input, top_k=5)
        except Exception:
            mem_ctx = ""

        system_content = (
            "你是一个乐于助人的中文助理，能调用工具完成任务。"
            "如果用户透露了姓名、偏好、计划、重要事实等信息，请主动调用 save_memory 工具记下来，"
            "方便以后跨对话回忆。"
        )
        if mem_ctx:
            system_content += (
                "\n\n以下是你之前记住的、可能与当前对话相关的信息，请善加利用：\n"
                + mem_ctx
            )
        return system_content

    def reset_session(self, session_id):
        """清空某个会话（包括等待中的审批）。等价于"开启新对话"。"""
        try:
            self.app.checkpointer.delete_thread(session_id)
        except Exception:
            pass
        self._pending.discard(session_id)

    def run_trace(self, session_id, user_input=None, max_steps=5, review_decision=None):
        """返回 {reply, steps} 或 {needs_review, review}。

        - 正常结束：{"reply": ..., "steps": [...], "needs_review": False, "review": None}
        - 需要人类审批：{"reply": "", "steps": [], "needs_review": True, "review": {...}}
        - review_decision 不为 None 时，表示人类已答复，用它唤醒（resume）被暂停的图。
        """
        self.steps = []  # 每轮对话重新开始记录
        self._pending.discard(session_id)
        config = {
            "configurable": {"thread_id": session_id},
            "recursion_limit": max_steps * 3 + 5,
        }

        try:
            if review_decision is not None:
                # 人类已经答复 -> 用 Command(resume=...) 唤醒被 interrupt 暂停的图
                result = self.app.invoke(Command(resume=review_decision), config=config)
            else:
                result = self.app.invoke(
                    {"messages": [HumanMessage(content=user_input)]},
                    config=config,
                )
        except GraphRecursionError:
            return {"reply": "（已达到最大步数，停止循环）", "steps": self.steps,
                    "needs_review": False, "review": None}
        except Exception as e:
            return {"reply": f"（执行出错或超过最大步数：{e}）", "steps": self.steps,
                    "needs_review": False, "review": None}

        # 检测是否被 interrupt 暂停（等待人类审批）
        interrupts = _extract_interrupt(result)
        if interrupts:
            self._pending.add(session_id)
            return {"reply": "", "steps": [], "needs_review": True, "review": interrupts}

        # 正常结束：从最终消息里抽取回复 + 工具步骤
        out = result["messages"]
        tool_results = {}
        for m in out:
            if isinstance(m, ToolMessage):
                tool_results[m.tool_call_id] = m.content
        for m in out:
            if getattr(m, "tool_calls", None):
                for tc in m.tool_calls:
                    self.steps.append({
                        "tool": tc["name"],
                        "args": tc["args"],
                        "result": str(tool_results.get(tc["id"], "")),
                    })

        reply = ""
        for m in reversed(out):
            if isinstance(m, AIMessage):
                reply = m.content
                break
        self._pending.discard(session_id)
        return {"reply": reply, "steps": self.steps, "needs_review": False, "review": None}


# ===== 模块级辅助函数 =====

def _describe_action(name, args):
    """把待审批工具转成人类友好的中文描述。"""
    if name == "save_note":
        return ("保存笔记", f"标题：{args.get('title', '')}\n内容：{args.get('content', '')}")
    if name == "save_memory":
        return ("写入长期记忆", f"要记住：{args.get('text', '')}")
    return (name, json.dumps(args, ensure_ascii=False))


def _lc_to_dict(m):
    """把 LangChain 消息转成 mock_llm 能看懂的 dict 格式。"""
    if isinstance(m, SystemMessage):
        return {"role": "system", "content": m.content}
    if isinstance(m, HumanMessage):
        return {"role": "user", "content": m.content}
    if isinstance(m, ToolMessage):
        return {"role": "tool", "content": m.content, "tool_call_id": m.tool_call_id}
    if isinstance(m, AIMessage):
        tcs = None
        if getattr(m, "tool_calls", None):
            tcs = [{"id": tc["id"], "name": tc["name"], "args": tc["args"]}
                   for tc in m.tool_calls]
        return {"role": "assistant", "content": m.content or "", "tool_calls": tcs}
    return {"role": "user", "content": str(getattr(m, "content", ""))}


def _extract_interrupt(result):
    """从被中断的图返回结果里取出 interrupt 透传出来的 payload。"""
    interrupts = result.get("__interrupt__")
    if not interrupts:
        return None
    first = interrupts[0]
    val = getattr(first, "value", first)
    # 个别版本会把 value 包成单元素元组，统一解包一下
    if isinstance(val, tuple) and len(val) == 1:
        val = val[0]
    return val
