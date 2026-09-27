"""
main.py —— 唯一入口(控制台版对话循环)

每轮流程:
    U_Input(输入 / Code_Send: 文件投喂) → classify_input(领域路由)
    → embed_search(语义检索记忆) → context_build(总装上下文)
    → chat_to_messages(最近历史) → Deepseek_Core(调用)
    → chat_add(双向落盘) → Memory_Scale_detect(压缩检查)

函数结构:
├─ Control()      一轮完整对话,返回 AI 回复文本
└─ __main__       自检 → 死循环(单轮失败不退程序,打印后继续)
"""
from tool import tools, embedding, Model_Function, Compress_mudel


def Control():
    """一轮完整对话,返回 AI 回复文本"""
    user_input = tools.U_Input()                       # exit() 在里面处理

    route = embedding.classify_input(user_input)       # 领域路由,没把握返回 None
    domain = route[0] if route else None
    if domain:
        print(f"[路由] 挂载领域:{domain}(相似度 {route[1]:.2f})")

    hits = embedding.embed_search(user_input, top_k=5) # 语义检索相关记忆(首次会建库)
    prompt = tools.context_build(domain=domain, memory_hits=hits)
    history = tools.chat_to_messages(last_n=10)        # 最近 10 条当上下文

    result = Model_Function.Deepseek_Core(user_input, prompt=prompt, history=history)

    tools.chat_add("user", user_input)                 # 双向落盘(过程流水)
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
