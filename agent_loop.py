"""
agent_loop.py —— Agent 内层循环(决策权移交发动机)

职责:把"模型 + 工具"接成 执行→回灌→再决策 的循环,直到模型给出最终答案
     或触发 max_steps 保险丝。入口层模块(main.py / GUI.py)共用本文件。

循环消息契约(每一步的形状,违反任何一条都会 400):
    1. assistant 消息必须原样回存——含 tool_calls 字段,缺了模型就"忘了"自己调过工具
    2. 每个 tool_call 必须紧跟一条 {"role":"tool","tool_call_id":id,"content":结果}
    3. 并行多个 tool_calls 必须全部执行、全部回复,不能只回一个
    4. reasoning_content:deepseek/glm 需要随 assistant 回传(缺失可能 400),gpt 不传

持久化策略:工具往返只活在本循环的 messages 里,不进聊天记录——
    落盘的只有 user 原始输入 + 最终 assistant 回答(由调用方 chat_add 完成)

函数结构:
├─ PROVIDER_NAMES        厂商名 → Model_Function 里低层入口函数名的映射
├─ MAX_STEPS             跑飞保险丝(默认 8 轮"模型→工具"往返)
└─ run_agent_turn(...)   主入口:一轮完整的自主决策对话,返回 dict

自测:python agent_loop.py   (假模型驱动,零 API 花费)
"""
from tool import Model_Function, Agent_tool

# 用"函数名字符串"而非函数引用:运行时经 getattr 解析,自测时才能整体替换假模型
PROVIDER_NAMES = {
    "deepseek": "Deepseek_messages",
    "glm": "GLM_messages",
    "gpt": "GPT_messages",
}
MAX_STEPS = 8


def run_agent_turn(user_input, prompt="", history=None,
                   provider="deepseek", approval="ask",
                   max_steps=MAX_STEPS, show_thinking=False, verbose=True):
    """跑一轮"模型自主决策"的对话。

    参数:
        user_input   用户这句话
        prompt       system prompt(Agent 模式建议只给 base 规则;检索/记忆等动作模型自己决定调不调)
        history      [{"role","content"}] 最近对话(chat_to_messages 的产物)
        provider     "deepseek" / "glm" / "gpt"
        approval     透传给 Agent_tool.execute_tool:终端 'ask'(危险工具弹确认),GUI 后台线程必须 'auto'
        max_steps    保险丝:最多几轮"模型→工具"往返,防跑飞烧钱
        verbose      是否把工具调用过程打印到控制台
    返回:
        {"content":  最终回答(触发保险丝时是停止提示语),
         "steps":    实际发生的工具轮数,
         "messages": 全程消息(含工具往返,供调试;不要整段落盘)}
    """
    # 运行时再解析函数:自测时替换 Model_Function.Deepseek_messages 才能生效
    fn_name = PROVIDER_NAMES.get(provider, "Deepseek_messages")
    call_model = getattr(Model_Function, fn_name)
    # GPT 的 chat API 不接受 reasoning_content 回传;deepseek/glm 用自家字段,回传无碍
    echo_reasoning = provider != "gpt"

    messages = []
    if prompt:
        messages.append({"role": "system", "content": prompt})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_input})

    final = None
    steps = 0
    for step in range(1, max_steps + 1):
        result = call_model(messages, tools=Agent_tool.get_tools(), show_thinking=show_thinking)

        # assistant 消息原样回存:有 tool_calls 必须带上(契约1)
        assistant = {"role": "assistant", "content": result["content"]}
        if result["reasoning"] and echo_reasoning:
            assistant["reasoning_content"] = result["reasoning"]
        if result["tool_calls"]:
            assistant["tool_calls"] = result["tool_calls"]
        messages.append(assistant)

        if not result["tool_calls"]:                 # 模型给出最终答案 → 循环唯一正常出口
            final = result["content"] or ""
            break

        steps = step
        for call in result["tool_calls"]:            # 并行调用:全部执行、全部回复(契约3)
            name = call["function"]["name"]
            args = call["function"]["arguments"]
            if verbose:
                print(f"[agent {step}/{max_steps}] {name}({args})")
            text = Agent_tool.execute_tool(name, args, approval=approval)
            if verbose:
                print(f"    -> {text[:100]}")
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": text})  # 契约2

    if final is None:                                # 保险丝熔断:轮数用尽仍未给答案
        final = f"已达到最大步数 {max_steps},任务未完成,已停止。"
    return {"content": final, "steps": steps, "messages": messages}


# ==================== 自测(直接运行本文件才会执行) ====================
if __name__ == "__main__":
    # 假模型:第一次调用返回工具请求,见到 tool 结果后给最终答案(全程零 API 花费)
    def fake_messages(messages, tools=None, show_thinking=False):
        if not any(m.get("role") == "tool" for m in messages):
            return {"content": "", "reasoning": "用户让我记住,调 remember",
                    "usage": None,
                    "tool_calls": [{"id": "call_test", "type": "function",
                                    "function": {"name": "remember",
                                                 "arguments": '{"content":"假测试记忆"}'}}]}
        return {"content": "已经记好了", "reasoning": "", "usage": None, "tool_calls": []}

    orig_model = Model_Function.Deepseek_messages
    orig_exec = Agent_tool.execute_tool
    Model_Function.Deepseek_messages = fake_messages                 # 换掉真模型入口
    Agent_tool.execute_tool = lambda name, args, approval="ask": "(假执行)已存入"  # 换掉真工具

    # 测试1:工具往返链路(契约1/2/3 + reasoning 回传)
    r = run_agent_turn("记住点东西", prompt="测试", verbose=True)
    assert r["content"] == "已经记好了" and r["steps"] == 1, "工具往返失败"
    assert any(m.get("role") == "tool" and m["tool_call_id"] == "call_test" for m in r["messages"]), "tool_call_id 没对上"
    assert any(m.get("role") == "assistant" and m.get("reasoning_content") for m in r["messages"]), "reasoning 没回传"
    print("[自测1] 工具往返链路: OK")

    # 测试2:保险丝——模型永远要调工具,应在 max_steps 熔断
    def loop_forever(messages, tools=None, show_thinking=False):
        return {"content": "", "reasoning": "", "usage": None,
                "tool_calls": [{"id": f"c{len(messages)}", "type": "function",
                                "function": {"name": "remember",
                                             "arguments": '{"content":"x"}'}}]}
    Model_Function.Deepseek_messages = loop_forever
    r2 = run_agent_turn("随便", max_steps=3, verbose=False)
    assert "已达到最大步数 3" in r2["content"] and r2["steps"] == 3, "保险丝没熔断"
    print("[自测2] max_steps 保险丝: OK")

    # 还原(进程内替换不影响其他文件;重开进程本来也会还原)
    Model_Function.Deepseek_messages = orig_model
    Agent_tool.execute_tool = orig_exec
    print("自测完成")
