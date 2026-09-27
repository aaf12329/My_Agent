# Deepseek_port_new

一个纯 Python、不依赖任何 Agent 框架的自制 LLM 助手项目，直接调用 DeepSeek API。
目标：从"聊天机器人"逐步进化为"Prompt 池 + 记忆池 + 工具循环"的个人 Agent。

## 这是什么

- 前身是一个单文件聊天机器人（`DeepSeek_port/ds.py`），后来做过一版多角色扮演（已封存）
- 现在的版本放弃了多角色路线，改为**一个大脑 + 按领域挂载模块**的架构：
  - **Prompt 池**：一个稳定的通用 prompt（`base.md`），叠加按需挂载的领域特化模块（代码 / 数学 / 电路等）
  - **记忆库**：长期记忆用 `.md` 存储，人可以直接看、直接改
  - **聊天记录**：用 `.json` 存储，与记忆库**物理分离**
- 所有功能模块收进 `tool/` 包，根目录只留 `main.py` 一个入口

## 项目结构

```
Deepseek_port_new/
├── main.py                 # 唯一入口
├── tool/                   # 功能模块包
│   ├── __init__.py
│   ├── tools.py            # 文件读写、输入处理、自检
│   ├── Model_Function.py   # DeepSeek API 调用
│   ├── Compress_mudel.py   # 记忆压缩（超阈值自动摘要）
│   └── Transformer_test.py # 实验脚本
├── Prompt/                 # Prompt 池（全 .md）
│   ├── base.md             # 通用 prompt：身份 / 硬规则 / 输出约定
│   └── domains/            # 特化池，按需叠加在 base 之后
│       ├── code.md
│       ├── math.md
│       └── circuit.md
├── Memories/               # 记忆库（.md）
│   └── memory.md           # 长期记忆
├── ChatHistory/            # 聊天记录（.json，与记忆库分开）
│   └── chat_history.json
├── 封存/                   # 历史版本存档（多角色版），不再维护
├── Engage.bat              # 双击启动
└── myvenv/                 # Python 虚拟环境（Python 3.14）
```

## 运行方式

```cmd
:: 1. 安装依赖
myvenv\Scripts\python.exe -m pip install openai python-dotenv python-docx openpyxl pandas

:: 2. 配置密钥：项目根目录建 .env 文件，内容一行
::    DEEPSEEK_API_KEY=sk-xxxx

:: 3. 启动
Engage.bat
:: 或
myvenv\Scripts\python.exe main.py
```

## 设计要点

- **Prompt 是叠加不是替换**：`base.md` 放身份和硬规则，永远稳定（也为了吃满 prompt cache 的前缀命中）；领域模块只放领域知识
- **记忆软路由**：记忆不按领域物理分池，检索时全库搜 + 同域加权，避免跨域信息丢失
- **过程与沉淀分离**：聊天记录（过程）和长期记忆（沉淀下来的事实）分开存，各自用最合适的格式

## Roadmap

- [x] 目录结构重组（prompt 池 / 记忆库 / 聊天记录三分离）
- [ ] 代码路径适配新结构（进行中）
- [ ] 记忆向量化检索（bge-small-zh + 余弦相似度）
- [ ] Agent 化三件套：结构化 messages / 工具声明（TOOLS）/ 工具执行循环
- [ ] 输入分类路由（本地小模型，自动挂载领域模块）

---

# Deepseek_port_new (English)

A pure-Python personal LLM assistant built from scratch — no agent frameworks, just direct DeepSeek API calls.
Goal: evolve from a "chatbot" into a personal Agent with a **prompt pool + memory pool + tool loop**.

## What is this

- Started as a single-file chatbot (`DeepSeek_port/ds.py`), then a multi-role roleplay edition (now archived)
- This version drops the multi-role design in favor of **one brain + pluggable domain modules**:
  - **Prompt pool**: one stable general prompt (`base.md`) plus domain-specific modules (code / math / circuit) stacked on demand
  - **Memory library**: long-term memory stored as `.md` — human-readable and hand-editable
  - **Chat history**: stored as `.json`, **physically separated** from the memory library
- All functional modules live in the `tool/` package; `main.py` at the root is the single entry point

## Project structure

```
Deepseek_port_new/
├── main.py                 # Single entry point
├── tool/                   # Feature package
│   ├── __init__.py
│   ├── tools.py            # File I/O, input handling, self-check
│   ├── Model_Function.py   # DeepSeek API calls
│   ├── Compress_mudel.py   # Memory compression (auto-summarize past threshold)
│   └── Transformer_test.py # Experiment script
├── Prompt/                 # Prompt pool (all .md)
│   ├── base.md             # General prompt: identity / hard rules / output conventions
│   └── domains/            # Specialized modules, stacked after base on demand
│       ├── code.md
│       ├── math.md
│       └── circuit.md
├── Memories/               # Memory library (.md)
│   └── memory.md           # Long-term memory
├── ChatHistory/            # Chat history (.json, kept apart from memory)
│   └── chat_history.json
├── 封存/                   # Legacy archive (multi-role edition), unmaintained
├── Engage.bat              # Double-click launcher
└── myvenv/                 # Python virtual environment (Python 3.14)
```

## How to run

```cmd
:: 1. Install dependencies
myvenv\Scripts\python.exe -m pip install openai python-dotenv python-docx openpyxl pandas

:: 2. Set your key: create a .env file in the project root with one line:
::    DEEPSEEK_API_KEY=sk-xxxx

:: 3. Launch
Engage.bat
:: or
myvenv\Scripts\python.exe main.py
```

## Design notes

- **Prompts stack, they don't replace**: `base.md` holds identity and hard rules and stays stable (also to maximize prompt-cache prefix hits); domain modules only carry domain knowledge
- **Soft routing for memory**: memory is not physically split by domain; retrieval searches the whole library with a same-domain boost, so cross-domain context is never lost
- **Process vs. distillation**: chat history (the process) and long-term memory (distilled facts) are stored separately, each in its most suitable format

## Roadmap

- [x] Directory restructure (prompt pool / memory / chat history separation)
- [ ] Adapt code paths to the new structure (in progress)
- [ ] Vector-based memory retrieval (bge-small-zh + cosine similarity)
- [ ] Agent trio: structured messages / tool declarations (TOOLS) / tool-execution loop
- [ ] Input classification routing (local small model, auto-mount domain modules)
