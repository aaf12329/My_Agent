// ============================================================================
// dsh-whale-widget 桌面版 —— preload（contextBridge）
// 渲染层只能通过 window.whaleAPI 与主进程通信，拿不到 Node / Electron 能力。
// ----------------------------------------------------------------------------
// 【结构分析注释 · 非原作者所写，仅供阅读参考】
//
// 【本文件的作用】安全边界本身。它是渲染层与主进程之间唯一的桥：
//   渲染层能做什么，完全由下面 exposeInMainWorld 里列出的方法决定——
//   没列出来的能力（fs / child_process / 任意 IPC 通道）渲染层一概拿不到。
//
// 【这是全项目最薄的文件，但它是安全模型的关键】
//   contextIsolation: true + nodeIntegration: false + sandbox: true（见 main.js）
//   三者配合，使得即使界面里被注入了恶意脚本，也拿不到 API_KEY。
//   密钥只存在于主进程内存中（core.js 的 secrets），渲染层只能"写入"不能"读取"。
//
// 【两种调用方式，注意区别】
//   invoke(...) —— 请求/响应，返回 Promise，可拿回结果（大部分方法）
//   send(...)   —— 单向通知，不等回复（setIgnore 鼠标穿透用它，属于高频操作）
//
// 【方法分组】
//   配置类： getConfig / saveConfig
//   凭据类： setApiKey / setPlatformToken   （只写不读，读不回来）
//   数据类： fetchBalance / fetchLastTurn
//   窗口类： moveWindow / dragEnd / setIgnore / quit
//   每个方法在 main.js 里都有一个同名语义的 ipcMain.handle 接收（对照表见 main.js 头部）
// ============================================================================
'use strict'

const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('whaleAPI', {
  getConfig: () => ipcRenderer.invoke('whale:getConfig'),
  saveConfig: (cfg) => ipcRenderer.invoke('whale:saveConfig', cfg),
  setApiKey: (key) => ipcRenderer.invoke('whale:setApiKey', key),
  setPlatformToken: (token) => ipcRenderer.invoke('whale:setPlatformToken', token),
  fetchBalance: () => ipcRenderer.invoke('whale:fetchBalance'),
  fetchLastTurn: () => ipcRenderer.invoke('whale:fetchLastTurn'),
  moveWindow: (dx, dy) => ipcRenderer.invoke('whale:moveWindow', dx, dy),
  dragEnd: () => ipcRenderer.invoke('whale:dragEnd'),
  quit: () => ipcRenderer.invoke('whale:quit'),
  setIgnore: (ignore) => ipcRenderer.send('whale:setIgnore', ignore),
})
