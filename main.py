"""
main.py —— 唯一入口(控制台版对话循环)

每轮流程:
    U_Input(输入 / Code_Send: 文件投喂) → classify_input(领域路由)
    → embed_search(语义检索记忆) → context_build(总装上下文)
    → chat_to_messages(最近历史) → Deepseek_Core(调用)
    → chat_add(双向落盘) → Memory_Scale_detect(压缩检查)

函数结构:
├─ Control()      一轮完整对话(/agent 切换 Workflow/Agent 两种模式)
└─ __main__       自检 → 死循环(单轮失败不退程序,打印后继续)
"""
from tool import tools, embedding, Model_Function, Compress_mudel
import agent_loop                             # Agent 内层循环(根目录,与 main 同级)

AGENT_MODE = False   # False=Workflow(固定管线,你替它想) / True=Agent(模型自主调工具)


def Control():
    """一轮完整对话。/agent 命令切换模式;返回 AI 回复文本(命令轮返回 None)"""
    global AGENT_MODE
    user_input = tools.U_Input()                       # exit() 在里面处理

    if user_input == "/agent":                         # 模式开关:Workflow <-> Agent
        AGENT_MODE = not AGENT_MODE
        print(f"[模式] 已切换 -> {'Agent(模型自主调工具)' if AGENT_MODE else 'Workflow(固定管线)'}")
        return None

    history = tools.chat_to_messages(last_n=10)        # 最近 10 条当上下文(两模式共用)

    if AGENT_MODE:
        # Agent 模式:决策权交给模型——查不查记忆/读不读文件由它调工具决定,
        # 这里只给 base 规则当 system;终端可以 'ask' 审批危险工具
        result = agent_loop.run_agent_turn(
            user_input, prompt=tools.prompt_build(), history=history)
    else:
        # Workflow 模式:固定管线,每轮必查必装(你替它想)
        route = embedding.classify_input(user_input)   # 领域路由,没把握返回 None
        domain = route[0] if route else None
        if domain:
            print(f"[路由] 挂载领域:{domain}(相似度 {route[1]:.2f})")

        hits = embedding.embed_search(user_input, top_k=5)  # 语义检索相关记忆(首次会建库)
        prompt = tools.context_build(domain=domain, memory_hits=hits)
        result = Model_Function.Deepseek_Core(user_input, prompt=prompt, history=history)

    tools.chat_add("user", user_input)                 # 双向落盘(只存主干,工具往返不进聊天记录)
    tools.chat_add("assistant", result["content"])
    Compress_mudel.Memory_Scale_detect()               # 顺手查一次要不要压缩
    return result["content"]


if __name__ == "__main__":
    tools.file_detect()
    print("输入 exit() 退出,Code_Send: 投喂文件\n" + "=" * 40)
    while True:
        try:
            Control()
        except Exception as e:
            # 单轮失败(断网/欠费/key错)不退程序,回到输入继续
            print(f"\n[错误] {type(e).__name__}: {e}\n(已回到输入,可直接重试或 exit() 退出)")
