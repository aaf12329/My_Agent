"""
Compress_mudel.py —— 记忆压缩模块(重构版)

职责:长期记忆 memory.md 超过阈值(1.5MB)时,调 DeepSeek 把整库摘要压缩并写回

与 tools.py 的格式约定(同步维护,本模块不 import tools):
- memory.md 每条记忆占一行 "- [时间] 内容"
- 压缩写回:压缩结果按行拆成条目,时间戳统一为压缩时刻

函数结构:
├─ Liberary_Read_Or_Write(model, path, content)   文本读写(保留原名)
├─ Ai_compress(content, model)                    调 DeepSeek 执行压缩,model 走参数
├─ Compress_control()                             读整库 → 压缩 → 按条目格式写回(无参,对象固定)
├─ Memory_Scale_detect()                          超 THRESHOLD_MB 触发压缩,返回是否触发
└─ Compress_mudel_link_test()                     连通性自检

设计说明:
- 自带一份非流式 DeepSeek 调用,不 import Model_Function:压缩是后台活,不该往终端刷流,
  也不引入横向依赖
- 待接入:目前包内无调用方;main 立循环后建议每轮对话末尾调一次 Memory_Scale_detect()
"""
import os
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

from .Store import Store

THRESHOLD_MB = 1.5   # 压缩触发阈值,单位 MB


def Liberary_Read_Or_Write(model, path, content=None):
    """文本读写:model='read' 返回内容;model='write' 覆盖写(无效 model 静默返回 None)"""
    if model == "read":
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    if model == "write":
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"{content}")


def Ai_compress(content, model="deepseek-v4-pro"):
    """调 DeepSeek 把整库记忆压缩到约5000字(角色视角已随多角色退役)"""
    print("Compress_mudel link Ok,start Compress")
    client = OpenAI(
        api_key=os.environ.get('DEEPSEEK_API_KEY'),
        base_url="https://api.deepseek.com")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system",
             "content": "你是记忆整理员。把下面的长期记忆压缩到5000字左右:"
                        "保留所有事实,合并重复项,按主题分段,每段一行"},
            {"role": "user", "content": content},
        ],
        stream=False,
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}}
    )
    result = response.choices[0].message.content
    print("Compress_finish")
    return result


def Compress_control():
    """读整库记忆 → Ai_compress → 按条目格式写回。返回是否执行了压缩"""
    load_dotenv()
    print("Compress_mudel Engage")
    text = Liberary_Read_Or_Write(model="read", path=Store.MEMORY_FILE)
    if not text or not text.strip():
        print("[Compress] 记忆库为空,无事可压")
        return False
    result = Ai_compress(text)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [line.strip() for line in result.splitlines() if line.strip()]
    body = "# 长期记忆\n\n" + "".join(f"- [{stamp}] {line}\n" for line in lines)
    Liberary_Read_Or_Write(model="write", path=Store.MEMORY_FILE, content=body)
    print(f"[Compress] 压缩完成:{len(lines)} 条写回 {Store.MEMORY_FILE}")
    return True


def Memory_Scale_detect():
    """检测记忆库大小,超过 THRESHOLD_MB 触发压缩。返回是否触发了压缩"""
    if not os.path.exists(Store.MEMORY_FILE):
        return False
    size_bytes = os.path.getsize(Store.MEMORY_FILE)
    if size_bytes / (1024 * 1024) >= THRESHOLD_MB:
        print(f"[Compress] 记忆库 {size_bytes / 1024 / 1024:.2f}MB ≥ {THRESHOLD_MB}MB,触发压缩")
        return Compress_control()
    return False


def Compress_mudel_link_test():
    """连通性自检"""
    print("可以接入Compress模块")


# ==================== 自测(直接运行本文件才会执行) ====================
if __name__ == "__main__":
    import tempfile
    # 自测时把 Store 的路径指到临时目录,绝不碰真实记忆
    tmp = tempfile.mkdtemp()
    Store.MEMORY_FILE = os.path.join(tmp, "memory.md")

    # 读写回环
    Liberary_Read_Or_Write(model="write", path=Store.MEMORY_FILE, content="# 长期记忆\n\n- [t] 测试条目\n")
    print("读回:", repr(Liberary_Read_Or_Write(model="read", path=Store.MEMORY_FILE)))

    # 未超阈值:不应触发
    print("未超阈值触发?", Memory_Scale_detect(), "(期望 False)")

    # 用假 Ai_compress 走通 检测→压缩→写回 全链(不发真请求、不花钱)
    # 造一个超过 1.5MB 的记忆库
    with open(Store.MEMORY_FILE, "w", encoding="utf-8") as f:
        f.write("# 长期记忆\n\n")
        f.write(f"- [2026-09-27 10:00] {'占位内容' * 150000}\n")   # 约 1.8MB
    globals()["Ai_compress"] = lambda content, model="x": "压缩结果第一行\n压缩结果第二行"
    triggered = Memory_Scale_detect()
    print("超阈值触发?", triggered, "(期望 True)")
    with open(Store.MEMORY_FILE, "r", encoding="utf-8") as f:
        written = f.read()
    print("写回格式正确:", "- [2026-" in written and "压缩结果第二行" in written and len(written) < 500)
    print("自测完成")
