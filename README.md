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
├── main.py                 # 唯一入口：控制台对话循环
├── GUI.py                  # 图形界面（左右气泡聊天风：用户蓝底靠右/AI灰底靠左，后台线程调模型）
├── GUI_Engage.bat          # 双击启动图形版
├── agent_loop.py           # Agent 内层循环：执行→回灌→再决策（main/GUI 共用，/agent 切换）
├── tool/                   # 功能模块包
│   ├── __init__.py
│   ├── Store.py            # 路径注册表：全项目文件位置的唯一登记处（纯地址簿，不做读写）
│   ├── tools.py            # 启动自检 + Prompt/记忆/聊天 增删改查 + 通用I/O + 输入(Code_Send 文件投喂)
│   ├── Model_Function.py   # 模型调用层：DeepSeek / GLM / GPT 三家适配
│   ├── embedding.py        # 向量化 + 记忆语义检索（bge-small-zh, CPU 可跑）
│   ├── Compress_mudel.py   # 记忆压缩（超阈值自动摘要并按条目格式写回）
│   └── Agent_tool.py       # Agent 工具适配层：TOOLS 声明 + 路径沙箱 + 审批 + 分发执行
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
├── whale/                  # 小鲸鱼桌面挂件（Electron，独立子系统，与 tool/ 零耦合）
│   ├── Engage.bat          # 双击启动（自带便携 Node 的 PATH）
│   ├── main.js             # 主进程：窗口/拖拽吸附/IPC（含结构分析注释）
│   ├── preload.js          # IPC 桥（渲染层唯一能力出口）
│   ├── lib/core.js         # 核心：余额拉取/记账/峰谷定价/AES加密（含结构分析注释）
│   └── renderer/           # 界面（含结构分析注释）
├── Engage.bat              # 双击启动
└── myvenv/                 # Python 虚拟环境（Python 3.14）
```

> **whale/ 独立性说明**：第三方开源项目（MIT，源码来自
> [comreade-123/DeepSeek-Whale-widget-desktop](https://github.com/comreade-123/DeepSeek-Whale-widget-desktop)，
> 上游 MeteorNOX/DeepSeek-Balance-Whale-Widget）的原样副本，显示 DeepSeek API 余额与用量。
> 运行时为便携版 Node.js v24（装在 `C:\nodejs`，免管理员，不污染系统）+ Electron（在 whale/node_modules 内），
> 与 Python 主项目互不 import、互不影响；`node_modules/`、`userdata.json` 等已被其自带 .gitignore 挡在仓库外。
> 与主项目的集成（agent 状态桥接）为规划中的独立任务。

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
| tools | `chat_to_messages(last_n)` | 桥：聊天记录 → API 干净 messages（剥 time 字段） |
| tools | `context_build(domain, memory_hits)` | 总装：prompt + 相关记忆段 → 最终 system prompt（检索结果由 main 传入，保持解耦） |
| Model_Function | `Deepseek_Core / GLM_Core / GPT_Core` | 便捷层：`(user_input, prompt, history, tools)` 一问一答或工具调用 |
| Model_Function | `Deepseek_messages / GLM_messages / GPT_messages` | 低层：收完整 messages 列表 + tools 参数，流式 tool_calls 分片累积 |
| embedding | `text_to_vector(text)` | 单句 → 512 维归一化向量 |
| embedding | `embed_build() / embed_search(query, top_k)` | 全库建索引 / 语义检索（索引过期自动重建） |
| embedding | `classify_input(query)` | 领域路由：与各领域 .md 全文比相似度，低于阈值返回 None |
| Compress_mudel | `Memory_Scale_detect() / Compress_control()` | 超阈值检测 / 执行压缩 |
| Agent_tool | `TOOLS / execute_tool(name, args_json, approval)` | 模型工具声明（search_memory / find_memory / remember / read_file / compress_memory）/ 分发执行（路径沙箱 + 危险审批 + 异常转文本） |
| agent_loop | `run_agent_turn(user_input, prompt, history, provider, approval, max_steps)` | **Agent 主入口**：模型自主决定调哪个工具，执行→回灌→再决策，返回 `{content, steps, messages}` |

**模型层返回契约**：所有调用统一返回 dict
`{"content": 回答文本, "reasoning": 思考过程, "usage": token账单(含缓存命中率)}`

## 架构图：谁负责什么，谁调用谁

### 图 1 · 分层与职责

```
┌──────────────── 入口层(壳)：唯一有权横向调用的层 ────────────────┐
│  main.py 控制台版           GUI.py 气泡图形版                    │
│  职责:模式切换(/agent)、编排一轮对话、聊天记录落盘(只存主干)       │
└──────┬──────────────────────────────┬──────────────────────────┘
       │ Workflow(固定管线,你替它想)   │ Agent(自主决策,它自己想)
       ▼                              ▼
┌──────────────────┐      ┌─────────────────────────┐
│ tool/embedding   │      │ agent_loop.py           │
│   语义检索+路由   │      │ 职责:内层循环+保险丝     │
│ tool/tools       │      │ 每轮:调模型(带工具清单)  │
│   记忆CRUD+I/O   │      │  ├─ 无工具调用→最终答案  │
│ tool/Model_Fn    │      │  └─ 有→执行→回灌→再决策  │
│   三家模型适配    │      └───────────┬─────────────┘
└──────────────────┘                  ▼
                          ┌──────────────────────────┐
                          │ tool/Agent_tool.py        │
                          │ 职责:工具声明/沙箱/审批/分发│
                          └──┬─────────┬─────────┬───┘
                             ▼         ▼         ▼
                        tools.py  embedding.py  Compress_mudel.py
                             └─────────┴─────────┘
                                      ▼
                          tool/Store.py(纯路径地址簿：人人读它,它不调用任何人)
```

### 图 2 · 依赖方向（箭头 = 调用）

```
main.py / GUI.py ──► agent_loop.py ──► Model_Function.py ──► DeepSeek/GLM/GPT(网络)
       │                  │
       │                  └──► Agent_tool.py(工具适配层,全项目唯一特批的横向 import)
       ├──► tools.py ────────────────┘(五个工具的真正实现就在这些模块里)
       ├──► embedding.py ────────────┘
       ├──► Compress_mudel.py ───────┘
       └──► Store.py

  解耦铁律:除 Agent_tool.py(工具适配层)外,tool/ 内各模块之间零 import;
  所有模块都只读 Store(路径),Store 不调用任何人
```

### 图 3 · Agent 工具调用结构（一轮自主决策的时序）

```
用户输入
   │
   ▼
agent_loop.run_agent_turn
   │  messages = [system(base 规则), 最近历史..., user]
   ▼
Model_Function.Deepseek_messages(messages, tools=Agent_tool.get_tools())
   │
   │   发给模型的请求里带 5 个工具的 JSON Schema 声明
   ▼
模型决策
   ├── 不需要工具 ──► content = 最终回答 ──► chat_add 落盘(user+assistant 主干) ──► 结束
   │
   └── 需要工具 ──► 返回 tool_calls[{name, arguments}]   (content 通常为空)
          │
          ▼
   Agent_tool.execute_tool(name, args, approval)
          │  ① 工具存在性检查 → ② JSON 参数解析 → ③ risky 审批(ask/auto/never)
          │  → ④ 执行 → ⑤ 任何异常都转成"给模型看的修正提示"(不是抛给人看的报错)
          ├── search_memory   ──► embedding.embed_search     (语义检索记忆)
          ├── find_memory     ──► tools.memory_read          (关键词精确查)
          ├── remember        ──► tools.memory_add           (存事实入记忆库)
          ├── read_file       ──► file_read_write + 路径沙箱  (禁 .env / 禁越界)
          └── compress_memory ──► Compress_control  [危险,需审批] (重写记忆库)
          │
          ▼
   每个结果包成 {"role":"tool","tool_call_id":id,"content":文本} 回灌 messages
          │
          └──► 回到顶部让模型看着结果再决策(循环;最多 max_steps=8 轮,超限熔断)
```

## 运行方式

```cmd
:: 1. 安装依赖
myvenv\Scripts\python.exe -m pip install openai python-dotenv python-docx openpyxl pandas sentence-transformers

:: 2. 配置密钥：项目根目录建 .env 文件（用到哪家配哪家）
::    DEEPSEEK_API_KEY=sk-xxxx
::    ZHIPU_API_KEY=xxx
::    OPENAI_API_KEY=sk-xxxx

:: 3. 启动
Engage.bat              :: 控制台版
GUI_Engage.bat          :: 图形版
:: 或
myvenv\Scripts\python.exe main.py
myvenv\Scripts\python.exe GUI.py

:: 3b. 小鲸鱼挂件（独立子系统；便携 Node 已装于 C:\nodejs，Engage.bat 自带 PATH）
whale\Engage.bat        :: 余额挂件（Electron）

:: 4. 各模块自测（全部自带临时目录测试，不碰真实数据）
myvenv\Scripts\python.exe -m tool.tools             :: 功能库全量自测
myvenv\Scripts\python.exe -m tool.embedding         :: 语义检索自测
myvenv\Scripts\python.exe -m tool.Model_Function    :: 三家连通自测（需 .env）
myvenv\Scripts\python.exe -m tool.Compress_mudel    :: 压缩链路自测
myvenv\Scripts\python.exe -m tool.Agent_tool        :: 工具层自测(沙箱/审批/分发)
```

## 日常使用

**加一条记忆**：用记事本打开 `Memories/memory.md`，新起一行写 `- [2026-09-27 21:00] 事实内容`（一条一行，格式错了程序会自动跳过）；或在代码里调 `tools.memory_add("事实")`。模型自主存记忆属于 Agent 化阶段的工具。

**加一个新领域**：在 `Prompt/domains/` 下新建 `xxx.md`，把对该领域的描述写进去——**文件全文就是它的语义身份**，路由按内容匹配，存档即生效，无需改代码。

**投喂文件**（仅控制台版）：输入以 `Code_Send:` 开头，回车后按提示输路径。支持 19 种格式：文本（带编码回退）/ xlsx / docx / 二进制转 base64；单文件 5MB、拼接后 1.5MB 双重限制。

**切换模型**：把 `main.py` 的 `Control()` 或 `GUI.py` 的 `_worker()` 里的 `Deepseek_Core(...)` 换成 `GLM_Core(...)` 或 `GPT_Core(...)` 即可，返回契约完全一致。

**切到 Agent 模式**：控制台输入 `/agent` 回车（再敲一次切回 Workflow）；图形版勾选 Agent 框。Agent 模式下**查不查记忆、存不存东西、读不读文件由模型自己决定**，每轮工具调用实时打印，`max_steps=8` 保险丝防跑飞。

**看 token 账单**：每轮对话结束打印 `[usage] 输入N(缓存命中M,百分比) 输出N 共N`——缓存命中率就是你"前缀稳定"设计的成绩单，一直接近 0% 就该回头查上下文拼装。

**压缩**：全自动，无需手动——`memory.md` 超 1.5MB 时下一轮对话触发摘要并按条目格式写回。

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
- [x] `chat_to_messages()` / `context_build()`（多轮与总装的库层就绪）
- [x] `classify_input()` 领域自动路由（本地分类，自动挂载特化 prompt）
- [x] main.py 对话循环 + GUI 图形界面（多轮对话上线）
- [x] Agent 工具适配层：TOOLS 声明 / 路径沙箱 / 危险操作审批 / 分发执行（tool/Agent_tool.py，5 个工具）
- [x] Agent 循环：tool_calls 解析 + 执行→回灌→再决策（max_steps 保险丝；控制台 `/agent` 切换、GUI 勾选框）——**Agent 化完成**
- [ ] ~~`classify_input()` 领域自动路由~~（已完成，见 embedding.py）

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
├── main.py                 # Single entry: console conversation loop
├── GUI.py                  # Chat-bubble GUI (user blue right / AI gray left, model in a background thread)
├── GUI_Engage.bat          # Double-click launcher for the GUI
├── agent_loop.py           # Agent inner loop: execute→feed-back→re-decide (shared by main/GUI, /agent to switch)
├── tool/                   # Feature package
│   ├── __init__.py
│   ├── Store.py            # Path registry: the only place that knows where files live (constants only)
│   ├── tools.py            # Self-check + CRUD for prompts/memory/chat + generic I/O + input (Code_Send file feeding)
│   ├── Model_Function.py   # Model layer: DeepSeek / GLM / GPT adapters
│   ├── embedding.py        # Vectorization + semantic memory retrieval (bge-small-zh, CPU-only)
│   └── Compress_mudel.py   # Memory compression (auto-summarize past threshold, written back as entries)
│   └── Agent_tool.py       # Agent tool adapter: TOOLS declarations + path sandbox + approval + dispatcher
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
├── whale/                  # Whale desktop widget (Electron, independent subsystem, zero coupling with tool/)
│   ├── Engage.bat          # Double-click launcher (bundles portable Node in PATH)
│   ├── main.js             # Main process: window/drag-snap/IPC (with structure-analysis comments)
│   ├── preload.js          # IPC bridge (the renderer's only capability outlet)
│   ├── lib/core.js         # Core: balance fetching/ledger/peak-valley pricing/AES (with structure-analysis comments)
│   └── renderer/           # UI (with structure-analysis comments)
├── Engage.bat              # Double-click launcher
└── myvenv/                 # Python virtual environment (Python 3.14)
```

> **whale/ independence note**: a verbatim copy of a third-party MIT project (source from
> [comreade-123/DeepSeek-Whale-widget-desktop](https://github.com/comreade-123/DeepSeek-Whale-widget-desktop),
> upstream MeteorNOX/DeepSeek-Balance-Whale-Widget) that shows your DeepSeek API balance and usage.
> Its runtime is portable Node.js v24 (installed at `C:\nodejs`, admin-free, no system pollution) plus
> Electron (inside whale/node_modules). It never imports the Python project and vice versa;
> `node_modules/`, `userdata.json` etc. are kept out of the repo by its own .gitignore.
> Integration with the main project (agent status bridge) is a planned separate task.

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
| tools | `chat_to_messages(last_n)` | Bridge: chat log → clean API messages (strips time) |
| tools | `context_build(domain, memory_hits)` | Assembly: prompt + relevant-memory section → final system prompt (retrieval results passed in from main, keeping decoupling) |
| Model_Function | `Deepseek_Core / GLM_Core / GPT_Core` | Convenience layer: `(user_input, prompt, history, tools)` — single exchange or tool calling |
| Model_Function | `Deepseek_messages / GLM_messages / GPT_messages` | Low level: full messages list + tools param, streaming tool_calls fragment accumulation |
| embedding | `text_to_vector(text)` | One sentence → 512-dim normalized vector |
| embedding | `embed_build() / embed_search(query, top_k)` | Build index / semantic retrieval (stale index auto-rebuilt) |
| embedding | `classify_input(query)` | Domain routing: similarity against each domain .md body; returns None below threshold |
| Compress_mudel | `Memory_Scale_detect() / Compress_control()` | Threshold check / run compression |
| Agent_tool | `TOOLS / execute_tool(name, args_json, approval)` | Tool declarations for the model (search_memory / find_memory / remember / read_file / compress_memory) / dispatcher (path sandbox + risky approval + errors-as-guidance) |
| agent_loop | `run_agent_turn(user_input, prompt, history, provider, approval, max_steps)` | **Agent main entry**: the model decides which tools to call; execute→feed-back→re-decide; returns `{content, steps, messages}` |

**Model layer return contract**: every call returns a dict —
`{"content": reply text, "reasoning": thinking process, "usage": token bill (incl. cache hit rate)}`

## Architecture: who does what, who calls whom

### Diagram 1 · Layers & responsibilities

```
┌────────────── Entry layer (the shell): the ONLY layer allowed to call sideways ────────────┐
│  main.py (console)            GUI.py (bubble GUI)                                          │
│  Duties: mode switch (/agent), orchestrating a turn, persisting chat trunk                  │
└──────┬──────────────────────────────┬──────────────────────────────────────────────────────┘
       │ Workflow (fixed pipeline)     │ Agent (autonomous decisions)
       ▼                              ▼
┌──────────────────┐      ┌─────────────────────────┐
│ tool/embedding   │      │ agent_loop.py           │
│   semantic+route │      │ duty: inner loop + fuse │
│ tool/tools       │      │ each round: call model  │
│   memory CRUD+I/O│      │  ├─ no tool_calls→answer│
│ tool/Model_Fn    │      │  └─ yes→execute→feed    │
│   3 providers    │      │     back→re-decide      │
└──────────────────┘      └───────────┬─────────────┘
                          ┌──────────────────────────┐
                          │ tool/Agent_tool.py        │
                          │ duty: schemas/sandbox/    │
                          │       approval/dispatch   │
                          └──┬─────────┬─────────┬───┘
                             ▼         ▼         ▼
                        tools.py  embedding.py  Compress_mudel.py
                             └─────────┴─────────┘
                                      ▼
                          tool/Store.py (path registry: read by all, calls nobody)
```

### Diagram 2 · Dependency directions (arrow = calls)

```
main.py / GUI.py ──► agent_loop.py ──► Model_Function.py ──► DeepSeek/GLM/GPT (network)
       │                  │
       │                  └──► Agent_tool.py (tool adapter: the ONLY sanctioned sideways import)
       ├──► tools.py ────────────────┘ (the five tools' real implementations live here)
       ├──► embedding.py ─────────────┘
       ├──► Compress_mudel.py ────────┘
       └──► Store.py

  Decoupling rule: except Agent_tool.py (the tool adapter), modules inside tool/
  never import each other; every module only reads Store (paths), and Store calls nobody
```

### Diagram 3 · Agent tool-calling structure (one autonomous turn, in sequence)

```
user input
   │
   ▼
agent_loop.run_agent_turn
   │  messages = [system(base rules), recent history..., user]
   ▼
Model_Function.Deepseek_messages(messages, tools=Agent_tool.get_tools())
   │
   │   the request carries JSON Schema declarations of 5 tools
   ▼
model decides
   ├── no tool needed ──► content = final answer ──► chat_add (user+assistant trunk) ──► done
   │
   └── needs a tool ──► returns tool_calls[{name, arguments}]   (content usually empty)
          │
          ▼
   Agent_tool.execute_tool(name, args, approval)
          │  ① existence check → ② JSON arg parsing → ③ risky approval (ask/auto/never)
          │  → ④ execute → ⑤ any exception becomes model-readable guidance (not a crash)
          ├── search_memory   ──► embedding.embed_search     (semantic memory search)
          ├── find_memory     ──► tools.memory_read          (keyword lookup)
          ├── remember        ──► tools.memory_add           (persist a fact)
          ├── read_file       ──► file_read_write + path sandbox (no .env / no escape)
          └── compress_memory ──► Compress_control  [risky, needs approval] (rewrites memory)
          │
          ▼
   each result is wrapped as {"role":"tool","tool_call_id":id,"content":text} and fed back
          │
          └──► back to the top for re-decision (loop; at most max_steps=8 rounds, then fuse)
```

## How to run

```cmd
:: 1. Install dependencies
myvenv\Scripts\python.exe -m pip install openai python-dotenv python-docx openpyxl pandas sentence-transformers

:: 2. Set keys: create a .env file in the project root (only the providers you use)
::    DEEPSEEK_API_KEY=sk-xxxx
::    ZHIPU_API_KEY=xxx
::    OPENAI_API_KEY=sk-xxxx

:: 3. Launch
Engage.bat              :: console edition
GUI_Engage.bat          :: GUI edition
:: or
myvenv\Scripts\python.exe main.py
myvenv\Scripts\python.exe GUI.py

:: 3b. Whale widget (independent subsystem; portable Node installed at C:\nodejs, Engage.bat bundles PATH)
whale\Engage.bat        :: balance widget (Electron)

:: 4. Module self-tests (all run in temp dirs, never touch real data)
myvenv\Scripts\python.exe -m tool.tools
myvenv\Scripts\python.exe -m tool.embedding
myvenv\Scripts\python.exe -m tool.Model_Function    :: requires .env
myvenv\Scripts\python.exe -m tool.Compress_mudel
myvenv\Scripts\python.exe -m tool.Agent_tool        :: tool-layer self-test (sandbox / approval / dispatch)
```

## Daily usage

**Add a memory**: open `Memories/memory.md` in any editor and add a line `- [2026-09-27 21:00] some fact` (one per line; malformed lines are skipped automatically); or call `tools.memory_add("fact")` in code. Model-driven memory saving belongs to the agent phase.

**Add a new domain**: create `Prompt/domains/xxx.md` and write your description of the domain in it — **the file body IS its semantic identity**; routing matches on the content, effective on save, zero code changes.

**Feed a file** (console only): start your input with `Code_Send:`, press Enter, follow the path prompt. 19 formats supported: text (with encoding fallback) / xlsx / docx / binary as base64; dual limits of 5MB per file and 1.5MB after concatenation.

**Switch models**: replace `Deepseek_Core(...)` with `GLM_Core(...)` or `GPT_Core(...)` in `main.py`'s `Control()` or `GUI.py`'s `_worker()` — the return contract is identical.

**Switch to Agent mode**: type `/agent` in the console (again to switch back to Workflow); or tick the Agent checkbox in the GUI. In Agent mode **the model decides on its own** whether to search memory, save facts, or read files; every tool step prints live, guarded by a `max_steps=8` fuse.

**Read the token bill**: every turn prints `[usage] in:N(cached:M,pct) out:N total:N` — the cache hit percentage is the report card of the "stable prefix" design; if it stays near 0%, audit the context assembly.

**Compression**: fully automatic — when `memory.md` exceeds 1.5MB, the next turn summarizes it and writes it back as entries.

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
- [x] `chat_to_messages()` / `context_build()` (library layer ready for multi-turn and assembly)
- [x] `classify_input()` domain routing (local classifier, auto-mount domain modules)
- [x] main.py conversation loop + GUI (multi-turn chat is live)
- [x] Agent tool adapter: TOOLS declarations / path sandbox / risky-operation approval / dispatcher (tool/Agent_tool.py, 5 tools)
- [x] Agent loop: tool_calls parsing + execute→feed-back→re-decide (max_steps fuse; `/agent` switch, GUI checkbox) — **agent transformation complete**
