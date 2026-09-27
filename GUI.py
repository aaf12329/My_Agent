"""
GUI.py —— 图形界面入口(布局与配色参考旧版 DeepSeek_port/GUI.py,逻辑全部走新库)

流程与 main.py 的 Control 完全一致,只换了交互外壳:
    classify_input → embed_search → context_build → chat_to_messages
    → Deepseek_Core → chat_add → Memory_Scale_detect

说明:
- 模型调用放后台线程,生成期间窗口不卡死;回显一律 root.after 回主线程(tkinter 线程规矩)
- 用 python.exe 启动(带控制台,模型的流式输出打到那里);别用 pythonw,print 会报错
- Code_Send 文件投喂是控制台版 U_Input 的功能,图形版暂未带
- 默认走 DeepSeek;想换 GLM/GPT,把 _worker 里的 Core 函数名换掉即可
"""
import threading
import tkinter as tk
from tkinter import scrolledtext, Entry, Button

from tool import tools, embedding, Model_Function, Compress_mudel

root = tk.Tk()
root.title("DeepSeek 端口")
root.geometry("600x700")
root.configure(bg="#1a1a1a")
root.resizable(False, False)

# 显示区
display = scrolledtext.ScrolledText(root, bg="#0d0d0d", fg="#e0e0e0", font=("Consolas", 12))
display.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))
display.config(state=tk.DISABLED)

# 底部容器
bottom_frame = tk.Frame(root, bg="#1a1a1a", height=100)
bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(5, 10))
bottom_frame.pack_propagate(False)

# 输入框
entry = Entry(bottom_frame, bg="#2a2a2a", fg="#ffffff", font=("Consolas", 13))
entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=10)


def _show(text):
    """主线程安全回显"""
    display.config(state=tk.NORMAL)
    display.insert(tk.END, text)
    display.see(tk.END)
    display.config(state=tk.DISABLED)


def _worker(user_input):
    """后台线程:一轮完整对话(流程与 main.Control 一致)"""
    try:
        route = embedding.classify_input(user_input)
        domain = route[0] if route else None

        hits = embedding.embed_search(user_input, top_k=5)
        prompt = tools.context_build(domain=domain, memory_hits=hits)
        history = tools.chat_to_messages(last_n=10)

        result = Model_Function.Deepseek_Core(user_input, prompt=prompt, history=history)
        reply = result["content"]

        tools.chat_add("user", user_input)
        tools.chat_add("assistant", reply)
        Compress_mudel.Memory_Scale_detect()

        tag = f"(领域:{domain})\n" if domain else ""
        root.after(0, _show, f"AI: {tag}{reply}\n")
    except Exception as e:
        root.after(0, _show, f"[出错] {type(e).__name__}: {e}\n")
    finally:
        root.after(0, lambda: btn.config(state=tk.NORMAL))


def GUI_Control():
    """发送按钮/回车:取输入 → 显示 → 起后台线程"""
    user_input = entry.get().strip()
    if not user_input:
        return
    _show(f"\nuser: {user_input}\n")
    entry.delete(0, tk.END)
    btn.config(state=tk.DISABLED)
    threading.Thread(target=_worker, args=(user_input,), daemon=True).start()


# 发送按钮
btn = Button(bottom_frame, text="发送", command=GUI_Control, bg="#0078ff", fg="white",
             font=("Consolas", 12, "bold"))
btn.pack(side=tk.RIGHT)
entry.bind("<Return>", lambda e: GUI_Control())

tools.file_detect()
_show("输入 exit() 退出; Code_Send: 投喂文件是控制台版功能\n" + "=" * 40 + "\n")

root.mainloop()
