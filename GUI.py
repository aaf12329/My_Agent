"""
GUI.py —— 图形界面入口(暗色聊天风:左右气泡消息框,布局参考旧版 DeepSeek_port/GUI.py)

流程与 main.py 的 Control 完全一致,只换了交互外壳:
    classify_input → embed_search → context_build → chat_to_messages
    → Deepseek_Core → chat_add → Memory_Scale_detect

说明:
- 消息区 = Canvas + 内部 Frame,每条消息一个气泡:用户靠右蓝底,AI 靠左灰底,系统提示居中灰字
- 模型调用放后台线程,生成期间窗口不卡死;回显一律 root.after 回主线程(tkinter 线程规矩)
- "正在思考…"占位气泡在回复到达时销毁
- 用 python.exe 启动(带控制台,模型的流式输出打到那里);别用 pythonw,print 会报错
- Code_Send 文件投喂是控制台版 U_Input 的功能,图形版暂未带
- 默认走 DeepSeek;想换 GLM/GPT,把 _worker 里的 Core 函数名换掉即可
"""
import threading
import tkinter as tk
from tkinter import Entry, Button

from tool import tools, embedding, Model_Function, Compress_mudel

BG      = "#1a1a1a"   # 窗口底色(沿用旧版)
CANVAS  = "#111111"   # 消息区底色
USER_BG = "#0078ff"   # 用户气泡(蓝,沿用旧版发送钮的蓝)
AI_BG   = "#2a2a2a"   # AI 气泡(深灰)
FONT    = ("Microsoft YaHei UI", 11)
WRAP    = 420         # 气泡文字换行宽度(窗口 620 固定,不可拉伸)

root = tk.Tk()
root.title("DeepSeek 端口")
root.geometry("620x720")
root.configure(bg=BG)
root.resizable(False, False)

# ==================== 消息区:Canvas + 内部 Frame,气泡可滚动 ====================
scrollbar = tk.Scrollbar(root, bg=BG)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(10, 5), padx=(0, 2))

canvas = tk.Canvas(root, bg=CANVAS, highlightthickness=0, yscrollcommand=scrollbar.set)
canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=(10, 5))
scrollbar.configure(command=canvas.yview)

inner = tk.Frame(canvas, bg=CANVAS)
inner_window = canvas.create_window((0, 0), window=inner, anchor="nw")

inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))


def _scroll_bottom():
    """吸底:新消息到达后滚到最下"""
    canvas.update_idletasks()
    canvas.yview_moveto(1.0)


def _add_bubble(text, is_user):
    """加一条消息气泡:用户靠右蓝底,AI 靠左灰底。返回该行控件(便于删除占位)"""
    row = tk.Frame(inner, bg=CANVAS)
    bubble = tk.Frame(row, bg=USER_BG if is_user else AI_BG, padx=10, pady=6)
    tk.Label(bubble, text=text,
             bg=USER_BG if is_user else AI_BG,
             fg="#ffffff" if is_user else "#e0e0e0",
             font=FONT, justify=tk.LEFT, wraplength=WRAP).pack()
    bubble.pack(anchor=tk.E if is_user else tk.W, padx=6, pady=4)
    row.pack(fill=tk.X)
    _scroll_bottom()
    return row


def _add_system(text):
    """系统提示:居中灰字,无气泡"""
    row = tk.Frame(inner, bg=CANVAS)
    tk.Label(row, text=text, bg=CANVAS, fg="#888888",
             font=("Microsoft YaHei UI", 9)).pack(pady=2)
    row.pack(fill=tk.X)
    _scroll_bottom()
    return row


def _remove_row(row):
    if row is not None and row.winfo_exists():
        row.destroy()
    _scroll_bottom()


# ==================== 底部输入区(沿用旧版布局) ====================
bottom_frame = tk.Frame(root, bg=BG, height=100)
bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(5, 10))
bottom_frame.pack_propagate(False)

entry = Entry(bottom_frame, bg="#2a2a2a", fg="#ffffff", font=("Consolas", 13),
              insertbackground="#ffffff")
entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=10)

btn = Button(bottom_frame, text="发送", command=lambda: GUI_Control(), bg="#0078ff",
             fg="white", font=("Consolas", 12, "bold"))
btn.pack(side=tk.RIGHT, ipadx=6, ipady=4)

thinking_row = None   # "正在思考…"占位行


def _remove_thinking():
    global thinking_row
    if thinking_row is not None:
        _remove_row(thinking_row)
        thinking_row = None


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

        text = f"[领域:{domain}]\n{reply}" if domain else reply

        def _done():
            _remove_thinking()
            _add_bubble(text, is_user=False)
            btn.config(state=tk.NORMAL)
        root.after(0, _done)
    except Exception as e:
        def _fail():
            _remove_thinking()
            _add_system(f"[出错] {type(e).__name__}: {e}")
            btn.config(state=tk.NORMAL)
        root.after(0, _fail)


def GUI_Control():
    """发送按钮/回车:取输入 → 上屏 → 起后台线程"""
    global thinking_row
    user_input = entry.get().strip()
    if not user_input:
        return
    _add_bubble(user_input, is_user=True)
    entry.delete(0, tk.END)
    btn.config(state=tk.DISABLED)
    thinking_row = _add_bubble("正在思考…", is_user=False)
    threading.Thread(target=_worker, args=(user_input,), daemon=True).start()


entry.bind("<Return>", lambda e: GUI_Control())

tools.file_detect()
_add_system("输入内容开始对话;Code_Send: 投喂是控制台版功能")

root.mainloop()
