# main.py
# 命令行入口：读配置 -> 启动 Agent -> 循环接收你的输入。
# 支持人工审核（Human-in-the-loop）：当 Agent 想"写笔记 / 写长期记忆"时，会先问你确认。

import os
import uuid
from dotenv import load_dotenv
# 阶段 4+：用 LangGraph 版（自带人工审核节点）
from agent_langgraph import Agent

# 从 .env 读取配置（没有 .env 也不报错，会用默认值）
load_dotenv()


def _parse_cli_decision(ans, review):
    """把命令行输入解析成 review_decision 字典。

    支持：
      A / all / y / yes / 允许      -> 全部通过
      R / reject / n / no / 拒绝    -> 全部拒绝
      数字（可多个，逗号/空格分隔）   -> 只通过这些编号，其余拒绝
    """
    ans = ans.strip().lower()
    if ans in ("a", "all", "y", "yes", "允许", "通过"):
        return {"decision": "approve_all"}
    if ans in ("r", "reject", "n", "no", "拒绝"):
        return {"decision": "reject_all"}
    # 否则按编号解析：通过的编号 -> approved，其余 -> rejected
    ids = [a["id"] for a in review["actions"]]
    try:
        picks = [int(x) for x in ans.replace(",", " ").split() if x.strip()]
    except ValueError:
        picks = []
    approved, rejected = [], []
    for i, aid in enumerate(ids, start=1):
        (approved if i in picks else rejected).append(aid)
    return {"decision": "custom", "approved": approved, "rejected": rejected}


def main():
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")        # 可选，兼容 DeepSeek / 通义 / 智谱 等
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    mock = os.getenv("MOCK", "false").lower() == "true"

    print("迷你工具调用 Agent 已启动（输入 exit 退出，输入 new 开启新对话）")
    if mock:
        print("⚠️  当前为 MOCK 模式：离线演示，不调用真实大模型。")
    print("💡 写笔记 / 写长期记忆 前，Agent 会先问你确认（人工审核）。\n")

    agent = Agent(api_key=api_key, base_url=base_url, model=model, mock=mock)
    # 整个 CLI 会话共用一个 session_id，这样命令行里多轮对话也能共享上下文
    session_id = str(uuid.uuid4())

    while True:
        try:
            user_input = input("\n你> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if user_input.lower() in ("exit", "quit"):
            break
        if user_input.lower() == "new":
            agent.reset_session(session_id)
            session_id = str(uuid.uuid4())
            print("(已开启新对话)")
            continue
        if not user_input:
            continue

        res = agent.run_trace(session_id, user_input)

        # —— 人工审核分支 ——
        if res.get("needs_review"):
            review = res["review"]
            print("\n⚠️  Agent 想执行以下操作，需要你确认：")
            for i, a in enumerate(review["actions"], start=1):
                print(f"  [{i}] {a['label']}")
                for line in a["detail"].split("\n"):
                    print(f"        {line}")
            ans = input("是否允许？[A 全部通过 / R 全部拒绝 / 或输入编号如 1 2] > ").strip()
            decision = _parse_cli_decision(ans, review)
            res = agent.run_trace(session_id, None, review_decision=decision)

        print(f"\nAgent> {res['reply']}")
        if res["steps"]:
            print("  （调用工具：", ", ".join(s["tool"] for s in res["steps"]), "）")


if __name__ == "__main__":
    main()
