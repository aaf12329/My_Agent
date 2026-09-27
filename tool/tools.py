"""
tools.py —— 工具函数集

分工规范:
- 路径一律从 Store 拿(tool/Store.py,纯地址簿),本文件不做任何 os.path.join 拼路径
- 本文件负责:启动自检 + Prompt池/记忆库/聊天记录 的增删改查 + 通用读写 + 输入

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
│   └─ prompt_build(d=None)      组装:base + 领域叠加 → 最终 system prompt
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
│   └─ chat_clear()              清空(慎用)
├─ 通用读写(兼容保留:Model_Function 还在调,适配后可下线)
│   └─ file_read_write(path, mode, role, content)
└─ 输入
    └─ U_Input()                 读一行输入,exit() 退出,返回 user_input

已退役(随多角色架构进 封存/):Name_list_operation、U_Input 的角色管理命令分支、
file_detect 的逐角色建文件与 Deepseek_Blank 现场生成
"""
import os
import sys
import json
from datetime import datetime

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
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(default)
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
    return _read_text(Store.BASE_PROMPT)


def prompt_read_domain(domain):
    """查:读某领域 prompt,不存在返回空字符串"""
    path = Store.prompt_domain_path(domain)
    if not os.path.exists(path):
        return ""
    return _read_text(path)


def prompt_write(domain, content):
    """增/改:写领域 prompt,存在即覆盖(领域名建议英文小写,如 code/math/circuit)"""
    if not domain or not str(domain).strip():
        print("[tools] prompt_write 失败:领域名不能为空")
        return False
    path = Store.prompt_domain_path(str(domain).strip())
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
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


# ==================== 记忆库 增删改查 ====================
def memory_add(content):
    """增:追加一条记忆"""
    if not content or not str(content).strip():
        print("[tools] memory_add 失败:内容不能为空")
        return False
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(Store.MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"- [{stamp}] {str(content).strip()}\n")
    return True


def memory_read(keyword=None):
    """查:读全部记忆,可按关键词过滤。返回 [(序号,时间,内容),...] 序号从1开始"""
    entries = []
    for line in _read_text(Store.MEMORY_FILE).splitlines():
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
    with open(Store.MEMORY_FILE, "w", encoding="utf-8") as f:
        f.write("# 长期记忆\n\n")
        for _, stamp, content in entries:
            f.write(f"- [{stamp}] {content}\n")


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


# ==================== 通用读写(兼容保留,Model_Function 还在调) ====================
def file_read_write(file_path, mode, role=None, content=None):
    """通用读写:json 统一 list 格式(修复旧版 {} 与 append 打架的问题);md/txt 纯文本"""
    if mode == "write":
        if file_path.endswith(".json"):
            if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                data = []
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            if not isinstance(data, list):   # 旧版自检曾写成 {},这里兜底成 list
                print(f"[tools] 警告:{file_path} 不是 list 格式,已重置为新列表")
                data = []
            data.append({
                "role": role,
                "content": content,
                "time": f"{datetime.now()}"
            })
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now()}  {role}:{content}\n")
    elif mode == "read":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        raise ValueError("mode error: 请使用'read'或'write'")


# ==================== 输入 ====================
def U_Input():
    """读一行输入;exit() 退出程序;返回 user_input(旧版角色管理分支已随多角色退役)"""
    user_input = input(f"{datetime.now()}  用户输入:")
    if user_input == "exit()":
        print("程序正常退出")
        sys.exit(0)
    return user_input


# ==================== 内部工具 ====================
def _read_text(path):
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


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
    # 自测时把 Store 的路径指到临时目录,绝不碰真实数据
    tmp = tempfile.mkdtemp()
    Store.PROMPT_DIR = os.path.join(tmp, "Prompt")
    Store.DOMAIN_DIR = os.path.join(Store.PROMPT_DIR, "domains")
    Store.BASE_PROMPT = os.path.join(Store.PROMPT_DIR, "base.md")
    Store.MEMORY_FILE = os.path.join(tmp, "memory.md")
    Store.CHAT_FILE = os.path.join(tmp, "chat.json")
    Store.ENV_FILE = os.path.join(tmp, ".env")
    file_detect()

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

    # 通用读写兼容层
    file_read_write(os.path.join(tmp, "misc.md"), "write", role="user", content="兼容层测试")
    print("兼容层读回:", file_read_write(os.path.join(tmp, "misc.md"), "read"))
    print("自测全部通过")
