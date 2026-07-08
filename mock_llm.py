# mock_llm.py
# 离线"假大脑"：不花钱、不联网也能看到 Agent Loop 怎么转。
# 它不会真的理解语义，只是按关键词规则"假装"模型在决策调工具。
# 仅用于学习演示——接上真实大模型后就不会用到它了。

import json
import re
from types import SimpleNamespace


def mock_respond(messages):
    last = messages[-1]

    # 如果上一条已经是"工具返回结果"，说明工具跑完了，直接收尾
    if last.get("role") == "tool":
        return SimpleNamespace(
            content=f"（mock 演示）工具已执行，结果是：{last.get('content')}",
            tool_calls=None,
        )

    text = (last.get("content") or "").lower()

    # 规则 1：问时间
    if "时间" in text or "几点" in text:
        return SimpleNamespace(content="", tool_calls=[
            SimpleNamespace(id="call_1",
                            function=SimpleNamespace(name="get_current_time", arguments="{}"))
        ])

    # 规则 2：包含算术（数字 + 运算符）
    if re.search(r"[\d\.]+\s*[\+\-\*/%]", text):
        m = re.search(r"[\d\.]+[\d\.\s\+\-\*/%\(\)]*", text)
        expr = m.group(0).strip()
        return SimpleNamespace(content="", tool_calls=[
            SimpleNamespace(id="call_2",
                            function=SimpleNamespace(name="calculator",
                                                     arguments=json.dumps({"expression": expr})))
        ])

    # 规则 3：看笔记（放在"记笔记"之前，避免 "看笔记" 被误判）
    if "看" in text and "笔记" in text:
        return SimpleNamespace(content="", tool_calls=[
            SimpleNamespace(id="call_4",
                            function=SimpleNamespace(name="read_notes", arguments="{}"))
        ])

    # 规则 4：让记笔记
    if "记" in text and "笔记" in text:
        return SimpleNamespace(content="", tool_calls=[
            SimpleNamespace(id="call_3",
                            function=SimpleNamespace(name="save_note",
                                                     arguments=json.dumps({"title": "来自用户的便签",
                                                                            "content": last.get("content")})))
        ])

    # 规则 4.5：让"记住"信息（长期记忆，区别于上面的便签）
    if "记住" in text or re.search(r"我是|我叫|我的名字|我喜欢|我住在|我的偏好", text):
        return SimpleNamespace(content="", tool_calls=[
            SimpleNamespace(id="call_7",
                            function=SimpleNamespace(name="save_memory",
                                                     arguments=json.dumps({"text": last.get("content")})))
        ])

    # 规则 4.6：让"回忆"/"你还记得"
    if "还记得" in text or "回忆" in text or "你记得" in text or "想起" in text:
        return SimpleNamespace(content="", tool_calls=[
            SimpleNamespace(id="call_8",
                            function=SimpleNamespace(name="search_memory",
                                                     arguments=json.dumps({"query": last.get("content")})))
        ])

    # 规则 5：查天气（mock 里城市固定为"北京"，仅演示工具触发；真实模式会智能提取城市）
    if "天气" in text:
        return SimpleNamespace(content="", tool_calls=[
            SimpleNamespace(id="call_5",
                            function=SimpleNamespace(name="get_weather",
                                                     arguments=json.dumps({"city": "北京"})))
        ])

    # 规则 6：联网搜索
    if "搜索" in text or "查一下" in text or "搜" in text or "百科" in text:
        return SimpleNamespace(content="", tool_calls=[
            SimpleNamespace(id="call_6",
                            function=SimpleNamespace(name="web_search",
                                                     arguments=json.dumps({"query": last.get("content")})))
        ])

    # 默认：直接回答（不调工具）
    return SimpleNamespace(
        content="（这是 mock 模式，我只会按关键词触发工具。试试说：现在几点 / 计算 23*4 / 记一条笔记：买牛奶 / 看笔记）",
        tool_calls=None,
    )
