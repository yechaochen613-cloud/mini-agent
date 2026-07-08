# agent.py
# 核心：Agent Loop（智能体循环）
#   推理 -> 模型决定调工具 -> 我们执行工具 -> 把结果喂回模型 -> 模型接着推理 ...
# 直到模型觉得"够了，给你最终答案"才停下。

import json
from tools import TOOL_FUNCTIONS, TOOL_SCHEMAS


class Agent:
    def __init__(self, api_key, base_url=None, model="gpt-4o-mini", mock=False):
        self.mock = mock
        self.model = model
        self.client = None
        self.steps = []  # 记录本轮调用过的工具，方便对外暴露（可观测性）
        # 多轮对话：session_id -> 该会话的对话历史（不含 system 消息）
        # 注意：历史存在进程内存里，服务重启会丢；长期记忆走 memory.json（另回事）。
        self.sessions = {}
        self.max_history = 24  # 每个会话最多保留的消息条数（约 12 轮），防止无限增长撑爆上下文
        if not mock:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key, base_url=base_url)

    def _build_system(self, user_input):
        """构建 system 提示：基础人设 + 当前问题相关的长期记忆（每轮重新计算，保证记忆新鲜）。"""
        try:
            from memory import relevant_context
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
        """清空某个会话的历史（开启新对话）。"""
        self.sessions.pop(session_id, None)

    def _chat(self, messages):
        """调用大模型一次，返回一条 message（含可能要调的工具）。"""
        if self.mock:
            from mock_llm import mock_respond
            return mock_respond(messages)

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=TOOL_SCHEMAS,      # 把工具清单交给模型
            tool_choice="auto",     # 让模型自己决定要不要调、调哪个
        )
        return resp.choices[0].message

    def run(self, session_id, user_input, max_steps=5):
        self.steps = []  # 每轮对话重新开始记录

        # 取出（或新建）这个会话的历史。历史里只存"对话内容"（user/assistant/tool），
        # system 提示每次都重新拼，这样可以把最新的长期记忆带进去。
        history = self.sessions.setdefault(session_id, [])

        system_content = self._build_system(user_input)

        # 完整消息 = system（含记忆） + 历史 + 本轮用户消息
        messages = [{"role": "system", "content": system_content}] + list(history)
        messages.append({"role": "user", "content": user_input})

        for step in range(1, max_steps + 1):
            print(f"\n--- 第 {step} 步：模型思考中 ---")
            message = self._chat(messages)

            # 情况 A：模型决定调用工具
            if getattr(message, "tool_calls", None):
                # 1) 把模型的"意图"原样记进对话历史（模型需要看到自己刚说了啥）
                messages.append({
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in message.tool_calls
                    ],
                })

                # 2) 真正执行每个工具，并把结果作为 tool 消息塞回对话
                for tc in message.tool_calls:
                    name = tc.function.name
                    args = json.loads(tc.function.arguments or "{}")
                    print(f"  [工具] 模型要调用: {name}({args})")
                    func = TOOL_FUNCTIONS.get(name)
                    result = func(**args) if func else f"找不到工具: {name}"
                    print(f"  [工具] 返回结果: {result}")
                    self.steps.append({"tool": name, "args": args, "result": str(result)})
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(result),
                    })

                # 3) 带着工具结果，让模型继续思考（进入下一轮循环）
                continue

            # 情况 B：模型觉得不需要工具了，给出最终回答
            print("--- 模型给出最终回答 ---")
            reply = message.content
            # 把本轮产生的新对话（去掉开头的 system）存回会话历史，并裁剪长度
            new_turn = messages[1:]
            history.extend(new_turn)
            if len(history) > self.max_history:
                history[:] = history[-self.max_history:]
            self.sessions[session_id] = history
            return reply

        # 达到最大步数：也把已产生的历史存下，避免丢失上下文
        new_turn = messages[1:]
        history.extend(new_turn)
        if len(history) > self.max_history:
            history[:] = history[-self.max_history:]
        self.sessions[session_id] = history
        return "（已达到最大步数，停止循环）"

    def run_trace(self, session_id, user_input, max_steps=5):
        """返回 {reply, steps}，方便 HTTP 接口直接序列化给前端。"""
        reply = self.run(session_id, user_input, max_steps=max_steps)
        return {"reply": reply, "steps": self.steps}
