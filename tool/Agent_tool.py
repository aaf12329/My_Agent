"""
Agent_tool.py —— Agent 工具适配层(全项目唯一特批的横向聚合文件)

职责:把兄弟模块的库函数包装成模型可调用的工具——
     TOOLS(JSON Schema 声明,发给 API 的 tools 参数) + 注册表 + 分发执行器

规范:
- 本文件是唯一的横向 import 层(tools/embedding/Compress_mudel),其余模块间仍然禁止互调
- 工具实现一律返回**给模型看的文本**:错误信息要写成"能指导模型修正"的话,不是给人看的报错
- 危险工具(risky)执行前走审批闸门:approval='ask' 弹终端确认 / 'auto' 全放行 / 'never' 全拒绝
  (GUI 接入时把 approval 传 'auto' 或换成回调,终端 input() 在后台线程里不能用)

函数结构:
├─ TOOLS                           模型可用的 JSON Schema 声明(常量)
├─ _tool_search_memory(query, top_k)  语义检索记忆      ← embedding.embed_search
├─ _tool_find_memory(keyword)         关键词精确查记忆   ← tools.memory_read
├─ _tool_remember(content)            存入长期记忆       ← tools.memory_add
├─ _safe_path(path)                   沙箱:路径限制在项目内 + 禁敏感文件
├─ _tool_read_file(path, max_chars)   读项目内文本文件   ← tools.file_read_write
├─ _tool_compress_memory()            压缩整库记忆(危险) ← Compress_mudel.Compress_control
├─ execute_tool(name, args_json, approval)  分发总闸:存在性→解析→审批→执行→异常转文本
└─ get_tools()                         取 TOOLS(将来的 Agent 循环发请求时带上)
"""
import os
import json

from .Store import Store
from . import tools, embedding, Compress_mudel


# ==================== 工具声明(发给模型的 JSON Schema) ====================
TOOLS = [
    {"type": "function", "function": {
        "name": "search_memory",
        "description": "在长期记忆中做语义检索(按意思匹配,不是字面关键词)。"
                       "当用户提到过去聊过的事、或你需要回忆之前的信息时使用;不要凭空假设自己记得。",
        "parameters": {"type": "object",
                       "properties": {
                           "query": {"type": "string", "description": "要找什么,用自然语言描述"},
                           "top_k": {"type": "integer", "description": "返回条数,默认5"}},
                       "required": ["query"]}}},

    {"type": "function", "function": {
        "name": "find_memory",
        "description": "按关键词在长期记忆里精确查找(字面匹配)。"
                       "当你确切知道要找的词时用它;意思相近但用词可能不同时,用 search_memory。",
        "parameters": {"type": "object",
                       "properties": {
                           "keyword": {"type": "string", "description": "关键词,如「四级」「串口」"}},
                       "required": ["keyword"]}}},

    {"type": "function", "function": {
        "name": "remember",
        "description": "把一条事实写入长期记忆,会持久化到磁盘。"
                       "仅当用户明确说「记住」「以后要用」,或提供了值得长期保存的重要事实时使用;闲聊不要调用。",
        "parameters": {"type": "object",
                       "properties": {
                           "content": {"type": "string", "description": "要记住的内容,建议200字内"}},
                       "required": ["content"]}}},

    {"type": "function", "function": {
        "name": "read_file",
        "description": "读取项目目录内的文本文件(禁止读取 .env 等敏感文件,禁止越出项目目录)。"
                       "仅当用户明确要求查看文件、或任务必须依赖文件内容时使用;不要猜测文件内容。",
        "parameters": {"type": "object",
                       "properties": {
                           "path": {"type": "string", "description": "相对项目根的路径,如 'Prompt/base.md'"},
                           "max_chars": {"type": "integer", "description": "最多返回字符数,默认5000"}},
                       "required": ["path"]}}},

    {"type": "function", "function": {
        "name": "compress_memory",
        "description": "把整库长期记忆压缩成约5000字摘要并写回磁盘。"
                       "危险操作:会重写记忆库。仅在记忆库过大或用户明确要求整理记忆时使用。",
        "parameters": {"type": "object", "properties": {}}}},
]


# ==================== 工具实现(返回给模型看的文本) ====================
def _tool_search_memory(query, top_k=5):
    hits = embedding.embed_search(query, top_k=top_k)
    if not hits:
        return "没有找到相关记忆"
    return "\n".join(f"[{i + 1}] (相似度{score:.2f} | {stamp}) {content}"
                     for i, (score, stamp, content) in enumerate(hits))


def _tool_find_memory(keyword):
    entries = tools.memory_read(keyword=keyword)
    if not entries:
        return f"没有包含「{keyword}」的记忆,可改用 search_memory 按意思检索"
    return "\n".join(f"[{idx}] ({stamp}) {content}" for idx, stamp, content in entries)


def _tool_remember(content):
    ok = tools.memory_add(content)
    return "已存入长期记忆" if ok else "存储失败:内容为空"


def _safe_path(path):
    """沙箱:路径必须落在项目根内(realpath 防符号链接绕过),敏感文件直接拒绝"""
    root = os.path.realpath(Store.BASE_DIR)
    full = os.path.realpath(os.path.join(root, path))
    if os.path.commonpath([root, full]) != root:
        raise PermissionError("路径超出项目范围,只能读项目内的文件")
    name = full.lower()
    if ".env" in name or "id_rsa" in name:
        raise PermissionError("该文件被禁止读取")
    return full


def _tool_read_file(path, max_chars=5000):
    full = _safe_path(path)
    if not os.path.isfile(full):
        return f"错误:文件不存在 {path}"
    if os.path.getsize(full) > 5 * 1024 * 1024:
        return "错误:文件超过 5MB"
    text = tools.file_read_write(full, "read")
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n…[已截断,原文件共{len(text)}字符,可用 max_chars 调整]"
    return text


def _tool_compress_memory():
    ok = Compress_mudel.Compress_control()
    return "压缩完成" if ok else "记忆库为空,无需压缩"


# ==================== 注册表与分发 ====================
_REGISTRY = {
    "search_memory":   {"run": _tool_search_memory, "risky": False},
    "find_memory":     {"run": _tool_find_memory,   "risky": False},
    "remember":        {"run": _tool_remember,      "risky": False},
    "read_file":       {"run": _tool_read_file,     "risky": False},
    "compress_memory": {"run": _tool_compress_memory, "risky": True},
}


def execute_tool(name, args_json="", approval="ask"):
    """分发总闸:工具存在性 → 参数解析 → 危险审批 → 执行 → 任何异常都转成给模型看的文本

    args_json: API 返回的 arguments 是 JSON 字符串;传 dict 也行
    approval:  'ask'=危险工具弹终端确认 / 'auto'=全放行 / 'never'=全拒绝
    """
    tool = _REGISTRY.get(name)
    if tool is None:
        return f"错误:不存在名为「{name}」的工具。可用工具:{list(_REGISTRY)}"

    # 参数解析(arguments 是 JSON 字符串,不是 dict)
    if isinstance(args_json, dict):
        args = args_json
    else:
        try:
            args = json.loads(args_json or "{}")
        except json.JSONDecodeError as e:
            return f"错误:参数不是合法 JSON({e}),请重新生成参数"

    # 危险工具审批闸门
    if tool["risky"]:
        if approval == "never":
            return "错误:该操作被禁止,请换一种方式或直接询问用户"
        if approval == "ask":
            try:
                ok = input(f"批准执行 {name}({json.dumps(args, ensure_ascii=True)})? [y/N] ").strip().lower()
            except (EOFError, OSError):
                ok = "n"
            if ok not in ("y", "yes"):
                return "用户拒绝了这次操作,请换一种方式或询问用户"

    # 执行:任何异常都转成给模型看的文本,绝不让程序崩
    try:
        return str(tool["run"](**args))
    except TypeError as e:
        return f"错误:参数名或参数类型不匹配({e})。工具声明:{json.dumps(TOOLS_REGISTRY_HINT.get(name, ''), ensure_ascii=False)}"
    except Exception as e:
        return f"错误:{type(e).__name__}: {e}"


# TypeError 时的提示素材:从 TOOLS 里抽出该工具的 schema
TOOLS_REGISTRY_HINT = {t["function"]["name"]: t["function"]["parameters"] for t in TOOLS}


def get_tools():
    """把工具声明交给调用方(将来的 Agent 循环发请求时带 tools=get_tools())"""
    return TOOLS


# ==================== 自测(直接运行本文件才会执行) ====================
if __name__ == "__main__":
    import tempfile
    import builtins
    # 自测时把 Store 的路径指到临时目录,绝不碰真实数据
    tmp = tempfile.mkdtemp()
    Store.BASE_DIR = tmp
    Store.MEMORY_FILE = os.path.join(tmp, "memory.md")
    Store.MEMORY_VECTOR_FILE = os.path.join(tmp, "memory_vectors.npy")
    Store.MEMORY_INDEX_FILE = os.path.join(tmp, "memory_index.json")
    Store.DOMAIN_DIR = os.path.join(tmp, "domains")
    os.makedirs(Store.DOMAIN_DIR, exist_ok=True)
    with open(Store.MEMORY_FILE, "w", encoding="utf-8") as f:
        f.write("# 长期记忆\n\n")

    # remember → search_memory(语义) → find_memory(关键词)
    print(execute_tool("remember", {"content": "用户的板子串口坏了"}))
    print("语义检索:", execute_tool("search_memory", {"query": "电脑坏了", "top_k": 3}))
    print("关键词检索:", execute_tool("find_memory", {"keyword": "串口"}))

    # read_file:正常 / 敏感文件 / 越界
    print("读文件:", execute_tool("read_file", {"path": "memory.md"})[:30], "…")
    with open(os.path.join(tmp, ".env"), "w", encoding="utf-8") as f:
        f.write("DEEPSEEK_API_KEY=secret")
    print("禁读.env:", execute_tool("read_file", {"path": ".env"}))
    print("禁越界:", execute_tool("read_file", {"path": "../../setup.py"}))

    # 审批闸门:先用假压缩替换注册表里的真函数(注册表持有函数引用,必须改 run 本体),不花钱
    _REGISTRY["compress_memory"]["run"] = lambda: "假压缩完成"
    builtins.input = lambda prompt="": "y"
    print("审批y:", execute_tool("compress_memory", approval="ask"))
    builtins.input = lambda prompt="": "n"
    print("审批n:", execute_tool("compress_memory", approval="ask"))
    print("审批never:", execute_tool("compress_memory", approval="never"))

    # 未知工具 / 坏参数
    print("未知工具:", execute_tool("fly_to_moon", "{}"))
    print("坏JSON:", execute_tool("remember", "{bad"))
    print("自测完成")
