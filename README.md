# Deepseek_port_new

一个纯 Python、不依赖任何 Agent 框架的自制 LLM 助手项目。
目标：从"聊天机器人"逐步进化为"Prompt 池 + 记忆池 + 工具循环"的个人 Agent。

## 这是什么

- 前身是一个单文件聊天机器人（`DeepSeek_port/ds.py`），后来做过一版多角色扮演（已封存）
- 现在的版本放弃了多角色路线，改为**一个大脑 + 按领域挂载模块**的架构：
  - **Prompt 池**：一个稳定的通用 prompt（`base.md`），叠加按需挂载的领域特化模块（代码 / 数学 / 电路等）
  - **记忆库**：长期记忆用 `.md` 存（一条记忆一行，人可直接改），配语义检索
  - **聊天记录**：用 `.json` 存，与记忆库**物理分开**（过程流水 ≠ 沉淀事实）
- 所有功能模块收进 `tool/` 包，根目录只留 `main.py` 一个入口

## 项目结构

```
Deepseek_port_new/
├── main.py                 # 唯一入口（对话循环待接）
├── tool/                   # 功能模块包
│   ├── __init__.py
│   ├── Store.py            # 路径注册表：全项目文件位置的唯一登记处（纯地址簿，不做读写）
│   ├── tools.py            # 启动自检 + Prompt/记忆/聊天 增删改查 + 通用I/O + 输入(Code_Send 文件投喂)
│   ├── Model_Function.py   # 模型调用层：DeepSeek / GLM / GPT 三家适配
│   ├── embedding.py        # 向量化 + 记忆语义检索（bge-small-zh, CPU 可跑）
│   └── Compress_mudel.py   # 记忆压缩（超阈值自动摘要并按条目格式写回）
├── Prompt/                 # Prompt 池（全 .md）
│   ├── base.md             # 通用 prompt：身份 / 硬规则 / 输出约定
│   └── domains/            # 特化池，按需叠加在 base 之后
│       ├── code.md
│       ├── math.md
│       └── circuit.md
├── Memories/               # 记忆库
│   ├── memory.md           # 真相源：一条记忆一行 "- [时间] 内容"，人可手改
│   ├── memory_vectors.npy  # 向量矩阵（embed_build 自动生成，可删，会自动重建）
│   └── memory_index.json   # 索引元数据（与 .npy 按行对齐）
├── ChatHistory/            # 聊天记录（.json，与记忆库分开）
│   └── chat_history.json
├── 封存/                   # 历史存档（多角色版、Transformer_test 等），不再维护
├── Engage.bat              # 双击启动
└── myvenv/                 # Python 虚拟环境（Python 3.14）
```

## 功能库 API 概览

| 模块 | 关键函数 | 说明 |
|---|---|---|
| Store | `Store.*` 路径常量 | 任何模块要文件位置都从这里拿，禁止自己拼路径 |
| tools | `file_detect()` | 启动自检：缺目录/文件自动补建 |
| tools | `prompt_build(domain)` | 组装最终 system prompt：base + 特化叠加 |
| tools | `memory_add / memory_read / memory_update / memory_delete` | 记忆增删改查（memory_read 支持关键词过滤） |
| tools | `chat_add / chat_read / chat_update / chat_delete` | 聊天记录增删改查 |
| tools | `file_read_write(path, mode, content)` | 磁盘 I/O 唯一入口，自带编码回退（utf-8→gbk→gb2312→latin-1） |
| tools | `U_Input()` | 读输入；`Code_Send:` 前缀触发文件投喂 |
| Model_Function | `Deepseek_Core / GLM_Core / GPT_Core` | 便捷层：`(user_input, prompt, history)` 一问一答 |
| Model_Function | `Deepseek_messages / GLM_messages / GPT_messages` | 低层：收完整 messages 列表，Agent 循环的地基 |
| embedding | `text_to_vector(text)` | 单句 → 512 维归一化向量 |
| embedding | `embed_build() / embed_search(query, top_k)` | 全库建索引 / 语义检索（索引过期自动重建） |
| Compress_mudel | `Memory_Scale_detect() / Compress_control()` | 超阈值检测 / 执行压缩 |

**模型层返回契约**：所有调用统一返回 dict
`{"content": 回答文本, "reasoning": 思考过程, "usage": token账单(含缓存命中率)}`

## 运行方式

```cmd
:: 1. 安装依赖
myvenv\Scripts\python.exe -m pip install openai python-dotenv python-docx openpyxl pandas sentence-transformers

:: 2. 配置密钥：项目根目录建 .env 文件（用到哪家配哪家）
::    DEEPSEEK_API_KEY=sk-xxxx
::    ZHIPU_API_KEY=xxx
::    OPENAI_API_KEY=sk-xxxx

:: 3. 启动
Engage.bat
:: 或
myvenv\Scripts\python.exe main.py

:: 4. 各模块自测（全部自带临时目录测试，不碰真实数据）
myvenv\Scripts\python.exe -m tool.tools             :: 功能库全量自测
myvenv\Scripts\python.exe -m tool.embedding         :: 语义检索自测
myvenv\Scripts\python.exe -m tool.Model_Function    :: 三家连通自测（需 .env）
myvenv\Scripts\python.exe -m tool.Compress_mudel    :: 压缩链路自测
```

## 设计要点

- **解耦规矩**：tool/ 内模块之间**不互相调用**，只有 main 指挥；Store 只是地址簿（路径常量）。记忆条目格式在 tools 和 embedding 两处同步维护
- **Prompt 是叠加不是替换**：`base.md` 放身份和硬规则，永远稳定（吃满 prompt cache 的前缀命中）；领域模块只放领域知识
- **记忆三层结构**：`memory.md` 是唯一真相源（人可手改），`.npy + .json` 是派生缓存（可随时删，检索时自动重建）
- **检索不用硬阈值**：bge 的相似度分布偏窄，判断相关靠排序和差值，取 top-k 而不是卡绝对分数
- **过程与沉淀分离**：聊天记录（过程流水）和长期记忆（沉淀事实）分开存；工具调用往返、思考过程不进聊天记录
- **只有暂时性错误才重试**：429/超时/5xx 指数退避带抖动；401/400 直接炸出来暴露问题

## Roadmap

- [x] 目录结构重组（prompt 池 / 记忆库 / 聊天记录三分离，tool 包化）
- [x] 功能库：自检 / 三类增删改查 / 通用 I/O / Code_Send 文件投喂
- [x] 三家模型适配（双层入口 + 重试退避 + reasoning/usage 三路收集）
- [x] 记忆语义检索（建库 + 检索 + 索引自动重建）
- [x] 记忆压缩模块重构（走 Store、签名修复、去多角色）
- [ ] `chat_to_messages()` + main.py 对话循环（多轮对话上线）
- [ ] `context_build()` 总装：prompt + 检索记忆 + 历史 → 最终上下文
- [ ] Agent 化三件套：TOOLS 声明 / tool_calls 解析 / 工具执行循环（含审批与路径沙箱）
- [ ] `classify_input()` 领域自动路由（本地分类，自动挂载特化 prompt）

---

# Deepseek_port_new (English)

A pure-Python personal LLM assistant built from scratch — no agent frameworks.
Goal: evolve from a "chatbot" into a personal Agent with a **prompt pool + memory pool + tool loop**.

## What is this

- Started as a single-file chatbot (`DeepSeek_port/ds.py`), then a multi-role roleplay edition (now archived)
- This version drops the multi-role design in favor of **one brain + pluggable domain modules**:
  - **Prompt pool**: one stable general prompt (`base.md`) plus domain modules (code / math / circuit) stacked on demand
  - **Memory library**: long-term memory as `.md` (one entry per line, human-editable), with semantic retrieval
  - **Chat history**: stored as `.json`, **physically separated** from memory (process log ≠ distilled facts)
- All modules live in the `tool/` package; `main.py` at the root is the single entry point

## Project structure

```
Deepseek_port_new/
├── main.py                 # Single entry point (conversation loop pending)
├── tool/                   # Feature package
│   ├── __init__.py
│   ├── Store.py            # Path registry: the only place that knows where files live (constants only)
│   ├── tools.py            # Self-check + CRUD for prompts/memory/chat + generic I/O + input (Code_Send file feeding)
│   ├── Model_Function.py   # Model layer: DeepSeek / GLM / GPT adapters
│   ├── embedding.py        # Vectorization + semantic memory retrieval (bge-small-zh, CPU-only)
│   └── Compress_mudel.py   # Memory compression (auto-summarize past threshold, written back as entries)
├── Prompt/                 # Prompt pool (all .md)
│   ├── base.md             # General prompt: identity / hard rules / output conventions
│   └── domains/            # Specialized modules, stacked after base on demand
│       ├── code.md
│       ├── math.md
│       └── circuit.md
├── Memories/               # Memory library
│   ├── memory.md           # Source of truth: one entry per line "- [time] content"
│   ├── memory_vectors.npy  # Vector matrix (generated by embed_build, safe to delete, auto-rebuilt)
│   └── memory_index.json   # Index metadata (row-aligned with the .npy)
├── ChatHistory/            # Chat history (.json, kept apart from memory)
│   └── chat_history.json
├── 封存/                   # Legacy archive (multi-role edition, Transformer_test, etc.)
├── Engage.bat              # Double-click launcher
└── myvenv/                 # Python virtual environment (Python 3.14)
```

## Library API overview

| Module | Key functions | Notes |
|---|---|---|
| Store | `Store.*` path constants | Every module gets file locations here; never join paths yourself |
| tools | `file_detect()` | Startup self-check: auto-creates missing dirs/files |
| tools | `prompt_build(domain)` | Assembles the final system prompt: base + domain stacked |
| tools | `memory_add / memory_read / memory_update / memory_delete` | Memory CRUD (read supports keyword filter) |
| tools | `chat_add / chat_read / chat_update / chat_delete` | Chat history CRUD |
| tools | `file_read_write(path, mode, content)` | The single disk-I/O gate, with encoding fallback (utf-8→gbk→gb2312→latin-1) |
| tools | `U_Input()` | Reads input; `Code_Send:` prefix triggers file feeding |
| Model_Function | `Deepseek_Core / GLM_Core / GPT_Core` | Convenience layer: `(user_input, prompt, history)` single exchange |
| Model_Function | `Deepseek_messages / GLM_messages / GPT_messages` | Low level: takes a full messages list — the foundation for the agent loop |
| embedding | `text_to_vector(text)` | One sentence → 512-dim normalized vector |
| embedding | `embed_build() / embed_search(query, top_k)` | Build index / semantic retrieval (stale index auto-rebuilt) |
| Compress_mudel | `Memory_Scale_detect() / Compress_control()` | Threshold check / run compression |

**Model layer return contract**: every call returns a dict —
`{"content": reply text, "reasoning": thinking process, "usage": token bill (incl. cache hit rate)}`

## How to run

```cmd
:: 1. Install dependencies
myvenv\Scripts\python.exe -m pip install openai python-dotenv python-docx openpyxl pandas sentence-transformers

:: 2. Set keys: create a .env file in the project root (only the providers you use)
::    DEEPSEEK_API_KEY=sk-xxxx
::    ZHIPU_API_KEY=xxx
::    OPENAI_API_KEY=sk-xxxx

:: 3. Launch
Engage.bat
:: or
myvenv\Scripts\python.exe main.py

:: 4. Module self-tests (all run in temp dirs, never touch real data)
myvenv\Scripts\python.exe -m tool.tools
myvenv\Scripts\python.exe -m tool.embedding
myvenv\Scripts\python.exe -m tool.Model_Function    :: requires .env
myvenv\Scripts\python.exe -m tool.Compress_mudel
```

## Design notes

- **Decoupling rule**: modules inside tool/ **never call each other**; only main orchestrates. Store is just an address book (path constants). The memory entry format is maintained in sync between tools and embedding
- **Prompts stack, they don't replace**: `base.md` holds identity and hard rules and stays stable (to maximize prompt-cache prefix hits); domain modules only carry domain knowledge
- **Three-layer memory**: `memory.md` is the single source of truth (human-editable); `.npy + .json` are derived caches (deletable, auto-rebuilt on retrieval)
- **No hard thresholds for retrieval**: bge similarity scores live in a narrow band — judge relevance by ranking and gaps, take top-k instead of absolute cutoffs
- **Process vs. distillation**: chat history (process) and long-term memory (distilled facts) are stored separately; tool round-trips and reasoning content never enter the chat log
- **Only transient errors get retried**: 429/timeout/5xx → exponential backoff with jitter; 401/400 fail loudly

## Roadmap

- [x] Directory restructure (prompt pool / memory / chat history separation, tool package)
- [x] Function library: self-check / CRUD × 3 / generic I/O / Code_Send file feeding
- [x] Three-provider adapters (dual-layer entries + retry/backoff + reasoning/usage collection)
- [x] Semantic memory retrieval (build + search + automatic index rebuild)
- [x] Compression module refactor (via Store, signature fixed, multi-role removed)
- [ ] `chat_to_messages()` + main.py conversation loop (multi-turn)
- [ ] `context_build()` assembly: prompt + retrieved memory + history → final context
- [ ] Agent trio: TOOLS declarations / tool_calls parsing / tool-execution loop (with approval & path sandbox)
- [ ] `classify_input()` domain routing (local classifier, auto-mount domain modules)
