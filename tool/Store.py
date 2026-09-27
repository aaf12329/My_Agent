"""
Store.py —— 项目路径注册表(只记录路径,不做任何读写)

规范:
1. 任何 .py 需要文件位置,统一来这里拿,严禁自己 os.path.join 拼路径
2. 文件的读写/增删改查/自检 全部在 tools.py,本文件只当地址簿
"""
import os


class Store:

    # __file__ = tool/Store.py → 往上两级就是项目根目录
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    TOOL_DIR = os.path.join(BASE_DIR, "tool")

    # Prompt 池
    PROMPT_DIR = os.path.join(BASE_DIR, "Prompt")
    BASE_PROMPT = os.path.join(PROMPT_DIR, "base.md")          # 通用prompt,保持稳定
    DOMAIN_DIR = os.path.join(PROMPT_DIR, "domains")           # 特化池目录

    # 记忆库与聊天记录(物理分开)
    MEMORY_DIR = os.path.join(BASE_DIR, "Memories")
    MEMORY_FILE = os.path.join(MEMORY_DIR, "memory.md")        # 记忆库,.md

    CHAT_DIR = os.path.join(BASE_DIR, "ChatHistory")
    CHAT_FILE = os.path.join(CHAT_DIR, "chat_history.json")    # 聊天记录,.json

    # 配置
    ENV_FILE = os.path.join(BASE_DIR, ".env")

    @classmethod
    def prompt_domain_path(cls, domain):
        """领域名 → 特化prompt路径(路径映射也属于'记录路径'的范畴)"""
        return os.path.join(cls.DOMAIN_DIR, f"{domain}.md")
