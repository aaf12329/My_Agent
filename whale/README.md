# DeepSeek 余额小鲸鱼桌面版（Whale Widget Desktop）

![DeepSeek 余额小鲸鱼](assets/DSH2.png)

DeepSeek 余额小鲸鱼 —— **脱离 DSH 的独立桌面挂件**：小鲸鱼气泡图常驻桌面右下角，实时显示 DeepSeek API 余额、今日已用、峰谷定价换算，支持拖拽/边缘吸附/按压音效/随机台词。打包为**单文件 EXE**，用户数据（含加密的 API_KEY）存于 **EXE 同目录 `userdata.json`**。

> **来源**：本仓库由 GitHub 仓库 [MeteorNOX/DeepSeek-Balance-Whale-Widget](https://github.com/MeteorNOX/DeepSeek-Balance-Whale-Widget) 的 DSH 插件版改造而来——在原插件的基础上新增了脱离 DSH 的**桌面版**。本项目沿用 **MIT License**，版权归原作者所有（见 [LICENSE](LICENSE)）：
>
> ```
> Copyright (c) 2026 MeteorNOX
> Copyright (c) 2026 EthanMaven
> ```

> 桌面版不支持「每轮对话消耗统计」（该功能依赖 DSH 会话事件，桌面环境无数据源）。

## 特性

- 🐋 **独立桌面应用**：Electron 透明置顶窗口，不依赖 DSH / 浏览器；开机即用
- 💰 **余额**：60 秒自动刷新 + 点击鲸鱼手动刷新；余额变化数字**滚动动画**；网络抖动自动沿用最近余额不报错
- 📊 **今日已用**：两种模式任选
  - **小鲸鱼记账（推荐，免令牌）**：鲸鱼娘每次观测余额后用余额差值自动记账（存 `userdata.json`，跨天自动归零归档）
  - **实时·令牌**：填入平台会话令牌后直接调用平台用量接口，按**峰谷定价**（空闲 9:00–12:00 与 14:00–18:00 之外 / 高峰 9–12 与 14–18 点）实时换算今日已用
- 🎚️ **汉堡菜单内置 API_KEY / 平台令牌**（悬停鲸鱼右上角三点打开）：
  - `API_KEY`（必填）：拉取余额；**AES-256-GCM 加密后写入 `userdata.json`**，明文永不落盘、渲染层拿不到
  - `平台令牌`（可选）：实时用量模式用，同样加密存储
  - 大小滑块（0.6–2.5 倍）、音效切换（小黄鸭 / 音效1）、音量调节、用量模式、峰谷提示文案（默认 / 梁文峰谷 / !?强强?!）、气泡开关
- 🖱️ **拖拽 + 四分之一屏边缘吸附**（左/右/上/下，角落可组合），窗口位置记忆
- 🔄 左吸附时整体**水平镜像翻转**（文字同步反向、带动画）
- 🧸 **按压 Q 弹**玩偶效果（按压时底部坐标不变）+ 按压/松手音效（内置 mp3，缺失时静默降级）
- 💬 **随机台词**：点击气泡切换随机台词段（加权随机，含峰谷提示/今日已用/gif 动图/卖萌吐槽），再点一次关闭；气泡总显示 5 秒自动收起
- 🚪 菜单底部「退出小鲸鱼」按钮（无边框窗口没有系统关闭按钮）

## 快速开始（使用打包好的 EXE）

1. 下载 Release 里的 `DeepSeekWhaleWidget_<version>_windows_x86.exe`（或按下方「构建」自行打包），放到任意目录双击运行
2. 桌面右下角出现小鲸鱼 → 鼠标悬停鲸鱼右上角出现**三点菜单** → 在 **API_KEY** 行粘贴你的 DeepSeek API Key（`sk-` 开头），点「保存」
3. 余额 60 秒内自动显示；点击鲸鱼可立即刷新并弹气泡
4. 首次运行后，EXE 同目录自动生成 `userdata.json`（设置 + 加密的密钥 + 记账数据）

> 托盘/开机自启：当前版本未做系统托盘，最小化为「直接退出」；如需开机自启，把 EXE 快捷方式放入 `shell:startup` 即可。

## 构建 EXE（从源码）

环境要求：Windows 10/11 x64、Node.js ≥ 18（开发机）。

```powershell
# 安装依赖（electron 31.7.7 + electron-builder）
npm install

# 国内网络请先设置 electron-builder 二进制镜像（NSIS 等工具链默认从 GitHub 下载）
$env:ELECTRON_BUILDER_BINARIES_MIRROR = "https://npmmirror.com/mirrors/electron-builder-binaries/"

# 打包单文件便携 EXE（输出到 dist/）
npm run dist
```

产物：`dist/DeepSeekWhaleWidget_<version>_windows_x86.exe`（当前版本 1.0.1）。

构建说明：

- `npm run dist` = `node scripts/prepare-electron.mjs` + `electron-builder --win portable`
- **无需管理员权限**：electron-builder 的 winCodeSign 工具链解压需要符号链接权限（非管理员 Windows 会报 `Cannot create symbolic link`），因此配置了 `win.signAndEditExecutable: false`，改由 `prepare-electron.mjs` 在打包前用 rcedit 给 `build/electron-dist/electron.exe` 打好图标与版本信息（`electronDist` 指向该目录），产物 EXE 与运行时的任务栏图标均正确
- 首次运行 `npm run dist` 会把 `node_modules/electron/dist` 复制到 `build/electron-dist/`（约 300MB，已 gitignore），之后可离线复用
- 若提示 `winCodeSign` 解压失败：说明未开启 Windows「开发者模式」，属正常现象——上面的流程已绕开该工具链；也可开启开发者模式后把 `signAndEditExecutable` 改回默认值让 electron-builder 自行处理

其他命令：

```powershell
npm start          # 开发模式直接运行（数据同样写到项目目录 userdata.json）
npm run dist:dir   # 仅生成免安装目录（dist/win-unpacked/），不做单文件打包
npx electron . --smoke   # 冒烟测试：启动 5 秒自动退出并打印渲染层状态
```

## 数据存储与安全

- 数据文件：**`userdata.json` 与 EXE 同目录**（便携版即 EXE 所在目录；开发模式为项目目录；若目录只读则回退到用户主目录）
- 结构：`settings`（大小/音量/模式等，明文）、`pos`（吸附状态）、`secrets`（**加密**的 `apiKey` / `platformToken`）、`usage`（记账账本 + 30 天历史）、`winPos`（窗口位置）
- 加密方案：AES-256-GCM；密钥由「内置 pepper + 本机标识（hostname|user|MAC）」经 PBKDF2-SHA256（10 万次迭代）派生
- 说明：这是**防明文直读**级别的保护（`userdata.json` 里看不到密钥原文），并非军规级保险柜——拿到 EXE 与本机访问权限的攻击者仍可逆向。密钥明文只出现在主进程内存中，渲染层通过 IPC 只能写入、不能读取
- 迁移：把 EXE 与 `userdata.json` 一起复制即可整体迁移（注意加密绑定本机标识，换机器后需重新填写 API_KEY）

## 目录结构

```text
DeepSeek-Whale-widget-desktop/
├── LICENSE                 # MIT（含两位作者版权行）
├── README.md               # 本文件
├── whale-widget-prompt.md  # 完整规格 / 维护提示词（含桌面版附录）
├── assets/DSH2.png         # README 顶部展示图
├── package.json            # Electron + electron-builder 配置
├── main.js                 # 主进程：窗口 / IPC / 拖拽吸附 / 生命周期
├── preload.js              # contextBridge：window.whaleAPI
├── lib/core.js             # 核心逻辑：userdata.json + 加密 + 余额/账本（纯 Node 可单测）
├── renderer/
│   ├── index.html          # 挂件页面
│   ├── widget.js           # 页面挂件逻辑
│   └── assets/             # 鲸鱼图 / gif / 音效
├── scripts/prepare-electron.mjs  # 打包前给 electron 打图标/版本补丁
└── build/
    ├── icon.ico            # 应用图标
    └── tools/rcedit-x64.exe      # 第三方工具（MIT，来源 electron-builder-binaries）
```

## 使用说明

### 汉堡菜单（悬停鲸鱼右上角三点）

| 行 | 说明 |
|---|---|
| **API_KEY** | 必填。粘贴 `sk-` 开头的 DeepSeek API Key 后点「保存」；输入框仅显示占位状态（未配置 / 已配置），不会回显密钥 |
| **平台令牌** | 可选。实时·令牌模式用（获取方法见下）；同样加密存储 |
| 大小 | 0.6–2.5 倍滑块 + 数字框（1–20） |
| 音效 / 音量 | 小黄鸭（Ya1/Ya2）/ 音效1（D1/D2） |
| 用量 | 小鲸鱼记账（默认）/ 实时·令牌 |
| 峰谷 | 提示文案风格：默认 / 梁文峰谷 / !?强强?! |
| 气泡 | 开关思考气泡 |
| 退出小鲸鱼 | 退出应用 |

### 两种用量模式

**① 小鲸鱼记账（推荐，默认）**——只需 API_KEY。鲸鱼娘用余额差值记账，跨天自动归零归档（保留 30 天）。依赖「观测到的余额下降」累计，若应用关闭期间有消耗会漏记。

**② 实时·令牌**——额外需要平台会话令牌：
1. 浏览器登录 **https://platform.deepseek.com** → 按 **F12** → **Network** 标签
2. 在平台页面点「用量」/刷新，找到 `usage/by_api_key/amount` 请求
3. 复制其 **Request Headers → Authorization** 的值（形如 `Bearer eyJ...`，含 `Bearer` 前缀即可）
4. 粘贴到菜单「平台令牌」行保存，用量模式切到「实时·令牌」

> 该令牌是平台网页会话令牌（非 `sk-` API key），重新登录平台后可能需要重新获取。接口不返回金额，挂件按内置峰谷定价表换算；定价表在 `lib/core.js` 顶部 `PEAK_HOURS` / `BASE_PRICE` / `PRICING` 常量，DeepSeek 调价时可自行修改。

## 常见问题

- **余额显示「未配置 API_KEY」**：打开三点菜单，在 API_KEY 行填写并保存。
- **今日已用显示 --**：记账模式需要先有一次余额观测（60 秒内自动完成）；令牌模式需配置平台令牌。
- **窗口拖不动**：按住鲸鱼本体（蓝色鲸鱼像素内）拖动；透明区域是穿透的，点击会落到下层窗口。
- **点不到鲸鱼**：首次启动鼠标穿透已开启，鼠标移入鲸鱼区域即恢复交互。
- **如何退出**：悬停鲸鱼 → 三点菜单 → 底部「退出小鲸鱼」。
- **没有声音**：确认 `renderer/assets/*.mp3` 在包内；缺失时静默降级为无声音。
- **userdata.json 写不进去**：EXE 所在目录只读时自动回退到用户主目录（`~/.dsh-whale-widget-userdata.json`），建议把 EXE 放到可写目录。
- **打包后杀软报毒**：Electron 应用常见误报（未签名）；可自行用 `signtool` 签名后分发。
- **自定义图片**：替换 `renderer/assets/DSniang1.png`（需透明背景 cut-out）；气泡由代码绘制。

## 开发与维护

- 完整规格、视觉参数、架构结论见 `whale-widget-prompt.md`（文末含桌面版附录）。
- **核心逻辑单测**：`lib/core.js` 无 Electron 依赖，可 `node -e "require('./lib/core.js')"` 直接验证加密/账本逻辑。
- **冒烟测试**：`npx electron . --smoke`（5 秒自动退出，打印渲染层初始化状态）。

## 许可证

本项目基于 **MIT License** 开源，详见 [LICENSE](LICENSE)。

```
Copyright (c) 2026 MeteorNOX
Copyright (c) 2026 EthanMaven
```
