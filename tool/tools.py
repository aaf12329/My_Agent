"""
tools.py —— 工具函数集

分工规范:
- 路径一律从 Store 拿(tool/Store.py,纯地址簿),项目内文件不做 os.path.join 拼路径
- 本文件负责:启动自检 + Prompt池/记忆库/聊天记录 的增删改查 + 通用读写 + 输入
- 磁盘 I/O 统一走 file_read_write(文本)和 _read_json/_write_json(结构化),不开第三个口子

数据格式约定:
- 记忆库 memory.md:每条一行 "- [时间] 内容",人可直接手改,程序只认这种行
- 聊天记录 chat_history.json:[{"role":..,"content":..,"time":..}, ...] 统一 list
- 增删改查的序号一律从 1 开始(第1条),人机一致

函数结构:
├─ 启动自检
│   └─ file_detect()             缺目录补目录,缺文件补空文件,.env 缺失给警告
├─ Prompt 池 增删改查
│   ├─ prompt_list_domains()     查:列出所有已有领域
│   ├─ prompt_read_base()        查:读通用 prompt
│   ├─ prompt_read_domain(d)     查:读某领域,不存在返回 ""
│   ├─ prompt_write(d, text)     增/改:写领域 prompt,存在即覆盖
│   ├─ prompt_delete(d)          删:删除领域 prompt
│   ├─ prompt_build(d=None)      组装:base + 领域叠加 → 最终 system prompt
│   └─ context_build(domain, memory_hits)  总装:再叠加相关记忆段(检索结果由 main 传入)
├─ 记忆库 增删改查
│   ├─ memory_add(text)          增:追加一条
│   ├─ memory_read(keyword)      查:返回 [(序号,时间,内容)],可按关键词过滤
│   ├─ memory_update(i, text)    改:按序号
│   └─ memory_delete(i)          删:按序号
├─ 聊天记录 增删改查
│   ├─ chat_add(role, text)      增:role 只应是 'user' / 'assistant'
│   ├─ chat_read(last_n)         查:last_n=3 只读最后3条,不传读全部
│   ├─ chat_update(i, text)      改:按序号
│   ├─ chat_delete(i)            删:按序号
│   ├─ chat_clear()              清空(慎用)
│   └─ chat_to_messages(last_n)  桥:聊天记录 → API 干净 messages(剥掉 time)
├─ 通用读写
│   └─ file_read_write(path, mode, content)   磁盘I/O唯一入口:文本/二进制读写,自带编码回退
├─ 输入
│   ├─ U_Input()                 读输入,exit() 退出,Code_Send: 触发文件投喂,返回 user_input
│   └─ _Code_Send(user_input)    内部:文件投喂分支(白名单/5MB/类型分发/1.5MB 拦截)
└─ 内部工具
    ├─ _write_memory_entries / _read_json / _write_json / _check_index

已退役(随多角色架构进 封存/):Name_list_operation、U_Input 的角色管理命令分支、
file_detect 的逐角色建文件与 Deepseek_Blank 现场生成
"""
import os
import sys
import json
import base64                 #Code_Send 二进制文件转 base64
from datetime import datetime

import pandas as pd                 #Code_Send 读 xlsx
from docx import Document           #Code_Send 读 docx

from .Store import Store


# ==================== 启动自检 ====================
def file_detect():
    """启动自检:缺目录建目录,缺文件建空文件,路径全部来自 Store"""
    print("文件完整性自检开始")
    for dir_path in (Store.PROMPT_DIR, Store.DOMAIN_DIR, Store.MEMORY_DIR, Store.CHAT_DIR):
        if os.path.exists(dir_path):
            print(f" 目录 {dir_path} 存在")
        else:
            os.makedirs(dir_path)
            print(f" 目录 {dir_path} 不存在,已建立")

    for file_path, default in (
        (Store.BASE_PROMPT, "# Base Prompt\n\n"),
        (Store.MEMORY_FILE, "# 长期记忆\n\n"),
        (Store.CHAT_FILE, "[]"),
    ):
        if os.path.exists(file_path):
            print(f" {file_path} 存在")
        else:
            file_read_write(file_path, "write", content=default)
            print(f" {file_path} 不存在,已建立")

    if not os.path.exists(Store.ENV_FILE):
        print(f" 警告:{Store.ENV_FILE} 不存在,请创建并写入一行 DEEPSEEK_API_KEY=sk-xxx")
    print("自检完成")


# ==================== Prompt 池 增删改查 ====================
def prompt_list_domains():
    """查:列出所有已有领域"""
    return sorted(name[:-3] for name in os.listdir(Store.DOMAIN_DIR) if name.endswith(".md"))


def prompt_read_base():
    """查:读通用 prompt"""
    return file_read_write(Store.BASE_PROMPT, "read")


def prompt_read_domain(domain):
    """查:读某领域 prompt,不存在返回空字符串"""
    path = Store.prompt_domain_path(domain)
    if not os.path.exists(path):
        return ""
    return file_read_write(path, "read")


def prompt_write(domain, content):
    """增/改:写领域 prompt,存在即覆盖(领域名建议英文小写,如 code/math/circuit)"""
    if not domain or not str(domain).strip():
        print("[tools] prompt_write 失败:领域名不能为空")
        return False
    path = Store.prompt_domain_path(str(domain).strip())
    file_read_write(path, "write", content=content)
    print(f"[tools] 已写入 prompt: {path}")
    return True


def prompt_delete(domain):
    """删:删除领域 prompt"""
    path = Store.prompt_domain_path(domain)
    if not os.path.exists(path):
        print(f"[tools] 删除失败,{path} 不存在")
        return False
    os.remove(path)
    print(f"[tools] 已删除 prompt: {path}")
    return True


def prompt_build(domain=None):
    """组装最终 system prompt:base + 特化叠加(设计核心:叠加不是替换)"""
    parts = [prompt_read_base()]
    if domain:
        domain_text = prompt_read_domain(domain)
        if domain_text:
            parts.append(domain_text)
        else:
            print(f"[tools] 注意:领域「{domain}」没有 prompt,只用 base")
    return "\n\n".join(parts)


def context_build(domain=None, memory_hits=None):
    """总装最终 system prompt:prompt_build 的结果 + 相关记忆段

    memory_hits: embedding.embed_search 的返回值 [(相似度,时间,内容),...],由 main 传入
    解耦说明:本函数不调用 embedding,检索在 main 完成,这里只负责拼装
    """
    prompt = prompt_build(domain)
    if memory_hits:
        lines = [f"- {content}" for _, _, content in memory_hits]
        prompt += "\n\n## 相关记忆\n" + "\n".join(lines)
    return prompt


# ==================== 记忆库 增删改查 ====================
def memory_add(content):
    """增:追加一条记忆"""
    if not content or not str(content).strip():
        print("[tools] memory_add 失败:内容不能为空")
        return False
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_read_write(Store.MEMORY_FILE, "append", content=f"- [{stamp}] {str(content).strip()}\n")
    return True


def memory_read(keyword=None):
    """查:读全部记忆,可按关键词过滤。返回 [(序号,时间,内容),...] 序号从1开始"""
    entries = []
    for line in file_read_write(Store.MEMORY_FILE, "read").splitlines():
        line = line.strip()
        if not line.startswith("- [") or "]" not in line:
            continue  # 跳过标题/空行/人手写的其他内容
        body = line[3:]                      # 去掉 "- ["
        stamp, content = body.split("]", 1)
        entries.append((len(entries) + 1, stamp.strip(), content.strip()))
    if keyword:
        entries = [e for e in entries if keyword in e[2]]
    return entries


def memory_update(index, new_content):
    """改:按序号修改一条记忆"""
    entries = memory_read()
    if not _check_index(index, len(entries), "记忆"):
        return False
    _, stamp, _ = entries[index - 1]
    entries[index - 1] = (index, stamp, str(new_content).strip())
    _write_memory_entries(entries)
    print(f"[tools] 已修改第 {index} 条记忆")
    return True


def memory_delete(index):
    """删:按序号删除一条记忆"""
    entries = memory_read()
    if not _check_index(index, len(entries), "记忆"):
        return False
    removed = entries.pop(index - 1)
    _write_memory_entries(entries)
    print(f"[tools] 已删除第 {index} 条记忆:{removed[2][:50]}")
    return True


def _write_memory_entries(entries):
    """内部:把条目列表写回 memory.md(保留文件头)"""
    text = "# 长期记忆\n\n" + "".join(f"- [{stamp}] {content}\n" for _, stamp, content in entries)
    file_read_write(Store.MEMORY_FILE, "write", content=text)


# ==================== 聊天记录 增删改查 ====================
def chat_add(role, content):
    """增:追加一条消息,role 只应是 'user' / 'assistant'"""
    data = _read_json()
    data.append({
        "role": role,
        "content": content,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    _write_json(data)
    return True


def chat_read(last_n=None):
    """查:读聊天记录,last_n=3 表示只读最后3条,不传读全部"""
    data = _read_json()
    if last_n:
        data = data[-last_n:]
    return data


def chat_update(index, new_content):
    """改:按序号修改某条消息内容"""
    data = _read_json()
    if not _check_index(index, len(data), "聊天记录"):
        return False
    data[index - 1]["content"] = new_content
    _write_json(data)
    print(f"[tools] 已修改第 {index} 条聊天记录")
    return True


def chat_delete(index):
    """删:按序号删除某条消息"""
    data = _read_json()
    if not _check_index(index, len(data), "聊天记录"):
        return False
    removed = data.pop(index - 1)
    _write_json(data)
    print(f"[tools] 已删除第 {index} 条聊天记录:{str(removed['content'])[:50]}")
    return True


def chat_clear():
    """删:清空全部聊天记录(慎用)"""
    _write_json([])
    print("[tools] 聊天记录已清空")
    return True


def chat_to_messages(last_n=None):
    """桥:把聊天记录转成 API 要的干净 messages(剥掉 time 字段)

    返回 [{"role","content"},...],直接喂给 *_Core 的 history 参数
    将来有 tool_calls 类记录时这里要跟着扩展,现阶段只有 user/assistant
    """
    return [{"role": item["role"], "content": item["content"]}
            for item in chat_read(last_n=last_n)]


# ==================== 通用读写 ====================
def file_read_write(file_path, mode, content=None):
    """磁盘 I/O 唯一入口(重构版):文本读写,自带编码回退

    mode='read'   读文本,编码自动回退 utf-8 → gbk → gb2312 → latin-1
    mode='read_bin' 读二进制,返回 bytes(Code_Send 的图片/压缩包走这里)
    mode='write'  覆盖写
    mode='append' 追加写
    注意:json 结构化数据(聊天记录)不走这里,走 _read_json/_write_json
    """
    if mode == "read_bin":
        with open(file_path, "rb") as f:
            return f.read()
    if mode == "read":
        for enc in ("utf-8", "gbk", "gb2312", "latin-1"):
            try:
                with open(file_path, "r", encoding=enc) as f:
                    text = f.read()
                if enc != "utf-8":
                    print(f"[tools] 文件 {file_path} 不是 utf-8,已用 {enc} 解码")
                return text
            except UnicodeDecodeError:
                continue
        print(f"[tools] 无法解码文件 {file_path}")
        return ""
    if mode in ("write", "append"):
        with open(file_path, "w" if mode == "write" else "a", encoding="utf-8") as f:
            f.write(f"{content}")
        return True
    raise ValueError("mode error: 请使用'read'/'write'/'append'")


# ==================== 输入 ====================
def U_Input():
    """读一行输入;exit() 退出;Code_Send: 前缀触发文件投喂;返回最终 user_input"""
    user_input = input(f"{datetime.now()}  用户输入:")
    if user_input == "exit()":
        print("程序正常退出")
        sys.exit(0)
    if user_input.startswith("Code_Send:"):
        user_input = _Code_Send(user_input)
    return user_input


def _Code_Send(user_input):
    """内部:Code_Send 文件投喂(实现参考旧版 ds.py 的 U_Input,变量名保留)

    流程:输路径 → 存在性 → 白名单 → 5MB 限制 → 按类型读取(文本/Office/二进制) → 拼接 → 1.5MB 拦截
    """
    local = input("\n文件路径(带后缀):")
    # 1. 文件存在性
    if not os.path.isfile(local):
        print("文件不存在")
        return user_input
    # 2. 扩展名白名单
    ALLOWED_EXTENSIONS = (".txt", ".md", ".csv", ".py", ".html", ".xml", ".log", ".yaml",
                          ".json", ".jpg", ".png", ".gif", ".mp4", ".mp3", ".pdf", ".zip",
                          ".exe", ".xlsx", ".docx")
    if not local.endswith(ALLOWED_EXTENSIONS):
        print("不支持的文件类型")
        return user_input
    # 3. 文件大小(防内存爆炸)
    file_size = os.path.getsize(local)
    if file_size > 5 * 1024 * 1024:   # 5MB
        print("文件超过 5MB")
        return "Send_oversize"
    # 4. 按类型读取
    data = None
    if local.endswith((".txt", ".md", ".csv", ".py", ".html", ".xml", ".log", ".yaml", ".json")):
        data = file_read_write(local, "read")      # 编码回退在 file_read_write 里
        print(f"\n已读取文本文件,共 {len(data)} 字符")
    elif local.endswith((".xlsx", ".docx")):
        try:
            if local.endswith(".docx"):
                doc = Document(local)
                data = "\n".join([p.text for p in doc.paragraphs])
            elif local.endswith(".xlsx"):
                df = pd.read_excel(local)
                data = df.to_string()
            print(f"成功读取Office文档,共 {len(data)} 字符")
        except ImportError as e:
            print(f"缺少依赖包: {e}")
            return user_input
        except Exception as e:
            print(f"读取Office文档失败: {e}")
            return user_input
    elif local.endswith((".jpg", ".png", ".gif", ".mp4", ".mp3", ".pdf", ".zip", ".exe")):
        # 注意:文本模型看不了图/二进制,base64 只会白白占上下文(旧版行为,原样保留)
        data = base64.b64encode(file_read_write(local, "read_bin")).decode()
        print("\n成功读取二进制文件,转为base64编码")
    # 5. 拼接到输入
    if data is not None:
        user_input = user_input + "\n" + data
    else:
        print("文件读取失败")
        return user_input
    # 6. 最终输入大小拦截
    if len(user_input.encode('utf-8')) / (1024 * 1024) >= 1.5:
        print("输入过大，被拦截请重新输入")
        return "Send_oversize"
    return user_input


# ==================== 内部工具 ====================
def _read_json():
    if not os.path.exists(Store.CHAT_FILE) or os.path.getsize(Store.CHAT_FILE) == 0:
        return []
    try:
        with open(Store.CHAT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        print("[tools] 警告:聊天记录 json 损坏,已按空处理(原文件未覆盖,请手动检查)")
        return []


def _write_json(data):
    with open(Store.CHAT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _check_index(index, total, name):
    """内部:校验序号合法(序号从1开始)"""
    if not isinstance(index, int) or index < 1 or index > total:
        print(f"[tools] 序号 {index} 不合法,{name}当前共 {total} 条")
        return False
    return True


# ==================== 自测(直接运行本文件才会执行,不影响被 import) ====================
if __name__ == "__main__":
    import tempfile
    import builtins
    # 自测时把 Store 的路径指到临时目录,绝不碰真实数据
    tmp = tempfile.mkdtemp()
    Store.PROMPT_DIR = os.path.join(tmp, "Prompt")
    Store.DOMAIN_DIR = os.path.join(Store.PROMPT_DIR, "domains")
    Store.BASE_PROMPT = os.path.join(Store.PROMPT_DIR, "base.md")
    Store.MEMORY_FILE = os.path.join(tmp, "memory.md")
    Store.CHAT_FILE = os.path.join(tmp, "chat.json")
    Store.ENV_FILE = os.path.join(tmp, ".env")
    file_detect()

    # file_read_write 重构版:写 / 读 / 追加 / 编码回退
    p_md = os.path.join(tmp, "misc.md")
    file_read_write(p_md, "write", content="第一行")
    file_read_write(p_md, "append", content="\n第二行")
    print("读回:", repr(file_read_write(p_md, "read")))
    p_gbk = os.path.join(tmp, "gbk.txt")
    with open(p_gbk, "w", encoding="gbk") as f:
        f.write("我是GBK编码的中文")
    print("GBK回退:", file_read_write(p_gbk, "read"))

    # prompt 增删改查
    prompt_write("code", "代码领域专用规则")
    print("领域列表:", prompt_list_domains())
    print("组装结果:", repr(prompt_build("code")[-20:]))
    prompt_write("code", "改过的规则")            # 改
    prompt_delete("code")                       # 删
    print("删除后列表:", prompt_list_domains())

    # 记忆增删改查
    memory_add("用户在准备四级英语")
    memory_add("用户主板串口坏了")
    print("记忆列表:", memory_read())
    memory_update(1, "用户在备考 2026 年 12 月四级")
    print("按关键词查:", memory_read(keyword="四级"))
    memory_delete(2)
    print("删除后:", memory_read())

    # 聊天增删改查
    chat_add("user", "你好")
    chat_add("assistant", "你好,有什么可以帮你?")
    print("聊天:", chat_read())
    chat_update(1, "你好(修正版)")
    chat_delete(2)
    print("最后1条:", chat_read(last_n=1))

    # chat_to_messages 桥
    msgs = chat_to_messages(last_n=1)
    print("桥输出:", msgs, "(应无 time 字段)")

    # context_build 总装
    hits = [(0.66, "2026-09-27 10:00", "用户主板串口坏了")]
    final_prompt = context_build(domain="code", memory_hits=hits)
    print("总装含记忆段:", "相关记忆" in final_prompt and "串口" in final_prompt)

    # read_bin
    p_bin = os.path.join(tmp, "b.zip")   # 用白名单内的扩展名,否则会被 Code_Send 拒收
    with open(p_bin, "wb") as f:
        f.write(b"\x00\x01binary")
    print("read_bin:", file_read_write(p_bin, "read_bin") == b"\x00\x01binary")

    # Code_Send 全流程(用假的 input 走一遍,不用手动敲)
    inputs = iter(["Code_Send:", p_md])
    builtins.input = lambda prompt="": next(inputs)
    result = U_Input()
    print("Code_Send 结果含文件内容:", "第二行" in result)

    # Code_Send 二进制分支
    inputs2 = iter(["Code_Send:", p_bin])
    builtins.input = lambda prompt="": next(inputs2)
    r2 = U_Input()
    print("Code_Send 二进制:", base64.b64encode(b"\x00\x01binary").decode() in r2)

    print("自测全部通过")
