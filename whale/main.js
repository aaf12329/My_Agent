// ============================================================================
// dsh-whale-widget 桌面版 —— Electron 主进程
// ----------------------------------------------------------------------------
// 一个透明、无边框、置顶的桌面小鲸鱼挂件窗口。
// 用户数据（userdata.json）存放在 EXE 同目录；API_KEY / 平台令牌经 AES-GCM
// 加密后写入（见 lib/core.js）。
// ----------------------------------------------------------------------------
// 【结构分析注释 · 非原作者所写，仅供阅读参考】
//
// 【本文件在全项目中的位置】三层架构的最上层：
//     renderer/widget.js（界面逻辑，无 Node 权限）
//         ↓ window.whaleAPI.*          （preload.js 用 contextBridge 暴露）
//         ↓ ipcRenderer.invoke(...)    （跨进程消息）
//         ↓ ipcMain.handle('whale:*')  ← 本文件
//         ↓ core.*                     （lib/core.js：数据 / 网络 / 加密）
//
// 【函数清单】
//   moveWindowTo(x, y)     移动窗口（用 setBounds 显式钉住宽高，防透明窗漂移）
//   applyPendingMove()     取出被合并的位移并真正执行移动（16ms 节流回调）
//   createWindow()         创建主窗口：透明/无边框/置顶/不占任务栏 + 位置恢复
//   animateWindowTo(tx,ty) 吸附动画：8 步三次缓出（ease-out cubic）
//   ── IPC handler 区（11 个）──
//   ── 应用生命周期区（单实例锁 → whenReady → window-all-closed）──
//
// 【IPC 通道对照表】渲染层方法 ←→ 本文件 handler ←→ core 函数
//   getConfig / saveConfig        ←→ whale:getConfig / whale:saveConfig      ←→ core.getConfig / saveConfig
//   setApiKey / setPlatformToken  ←→ whale:setApiKey / :setPlatformToken      ←→ core.setApiKey / setPlatformToken
//   fetchBalance                  ←→ whale:fetchBalance                        ←→ core.getBalance
//   fetchLastTurn                 ←→ whale:fetchLastTurn                       ←→ core.fetchLastTurn
//   moveWindow / dragEnd          ←→ whale:moveWindow / whale:dragEnd          （只操作窗口，不碰 core）
//   quit                          ←→ whale:quit
//   setIgnore（单向 send）        ←→ whale:setIgnore                           （鼠标穿透开关）
// ============================================================================
'use strict'

const { app, BrowserWindow, ipcMain, screen } = require('electron')
const path = require('node:path')
const { createWhaleCore } = require('./lib/core.js')

const isDev = !app.isPackaged
// portable 单文件版：PORTABLE_EXECUTABLE_DIR 指向便携 EXE 所在目录；
// 安装版 / 开发态回退到 exe 目录 / 项目目录。
const exeDir =
  process.env.PORTABLE_EXECUTABLE_DIR ||
  (isDev ? app.getAppPath() : path.dirname(app.getPath('exe')))

const core = createWhaleCore({ dataFile: path.join(exeDir, 'userdata.json') })

let win = null
let dragState = null
let pendingMove = null
let moveTimer = null

// ---------------------------------------------------------------------------
// 常量与窗口移动工具
// ---------------------------------------------------------------------------
const WINDOW_W = 560
const WINDOW_H = 840

function clamp(v, lo, hi) {
  return v < lo ? lo : v > hi ? hi : v
}

// Windows 透明（分层）窗口在 setPosition 时存在尺寸漂移的已知问题：
// 每次移动窗口都会“长大”几像素（连续拖动时肉眼可见地抽搐+放大）。
// 因此移动一律用 setBounds 显式钉住宽高；拖动位移用 16ms 帧合并节流。
function moveWindowTo(x, y) {
  if (!win) return
  try {
    win.setBounds({ x: Math.round(x), y: Math.round(y), width: WINDOW_W, height: WINDOW_H })
  } catch (err) {}
}

function applyPendingMove() {
  if (!pendingMove) return
  const dx = pendingMove.dx
  const dy = pendingMove.dy
  pendingMove = null
  if (!win || !dragState) return
  moveWindowTo(dragState.baseX + dx, dragState.baseY + dy)
}

// ---------------------------------------------------------------------------
// 窗口创建：透明 + 无边框 + 置顶 + 不占任务栏；恢复上次位置；挂关闭时保存
// ---------------------------------------------------------------------------
function createWindow() {
  win = new BrowserWindow({
    width: WINDOW_W,
    height: WINDOW_H,
    transparent: true,
    frame: false,
    resizable: false,
    movable: false,
    minimizable: false,
    maximizable: false,
    fullscreenable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    hasShadow: false,
    backgroundColor: '#00000000',
    webPreferences: {
      preload: path.join(app.getAppPath(), 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  win.setAlwaysOnTop(true, 'screen-saver')
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true })
  win.setSkipTaskbar(true)

  // 恢复上次窗口位置（限制在工作区内；用 setBounds 钉住尺寸防漂移）
  const pos = core.getWinPos()
  if (pos) {
    try {
      const wa = screen.getPrimaryDisplay().workArea
      const x = clamp(pos.x, wa.x, wa.x + wa.width - WINDOW_W)
      const y = clamp(pos.y, wa.y, wa.y + wa.height - WINDOW_H)
      moveWindowTo(x, y)
    } catch (err) {}
  }

  win.on('close', () => {
    try {
      const [x, y] = win.getPosition()
      core.setWinPos({ x, y })
    } catch (err) {}
  })

  win.loadFile(path.join(app.getAppPath(), 'renderer', 'index.html'))

  // 冒烟测试：node_modules/.bin/electron . --smoke —— 启动 5 秒后自动退出
  if (process.argv.includes('--smoke')) {
    win.webContents.on('console-message', (e, level, message) => {
      console.log('[renderer:' + level + ']', message)
    })
    setTimeout(async () => {
      try {
        const r = await win.webContents.executeJavaScript(
          '({ api: !!window.whaleAPI, widget: !!window.__dshWhaleWidget, root: !!document.querySelector(".dshwv-root"), img: !!document.querySelector(".dshwv-img"), apiKeyInput: !!document.querySelector(".dshwv-secret") })'
        )
        console.log('SMOKE RENDERER: ' + JSON.stringify(r))
      } catch (err) {
        console.log('SMOKE RENDERER ERROR: ' + err.message)
      }
      console.log('SMOKE OK: window created, size=' + JSON.stringify(win.getSize()) + ' pos=' + JSON.stringify(win.getPosition()))
      app.quit()
    }, 5000)
  }
}

function animateWindowTo(tx, ty) {
  if (!win) return
  const [x, y] = win.getPosition()
  const steps = 8
  let i = 0
  const timer = setInterval(() => {
    i++
    const t = i / steps
    const ease = 1 - Math.pow(1 - t, 3)
    moveWindowTo(x + (tx - x) * ease, y + (ty - y) * ease)
    if (i >= steps) clearInterval(timer)
  }, 18)
}

// ---------------------------------------------------------------------------
// IPC
// ---------------------------------------------------------------------------
ipcMain.handle('whale:getConfig', () => core.getConfig())
ipcMain.handle('whale:saveConfig', (e, cfg) => core.saveConfig(cfg))
ipcMain.handle('whale:setApiKey', (e, key) => core.setApiKey(String(key || '')))
ipcMain.handle('whale:setPlatformToken', (e, token) => core.setPlatformToken(String(token || '')))
ipcMain.handle('whale:fetchBalance', () => core.getBalance())
ipcMain.handle('whale:fetchLastTurn', () => core.fetchLastTurn())
ipcMain.handle('whale:quit', () => app.quit())

// 鼠标穿透：透明区域忽略鼠标事件（forward 保留 mousemove 供渲染层检测悬停）
ipcMain.on('whale:setIgnore', (e, ignore) => {
  if (win) {
    try {
      win.setIgnoreMouseEvents(!!ignore, { forward: true })
    } catch (err) {}
  }
})

// 拖拽窗口：渲染层上报相对起点位移，主进程按 16ms 帧合并节流移动窗口
ipcMain.handle('whale:moveWindow', (e, dx, dy) => {
  if (!win) return null
  const px = Number(dx)
  const py = Number(dy)
  if (!isFinite(px) || !isFinite(py)) return null
  pendingMove = { dx: px, dy: py }
  if (!dragState) {
    try {
      const [wx, wy] = win.getPosition()
      dragState = { baseX: wx, baseY: wy }
    } catch (err) {
      return null
    }
  }
  if (!moveTimer) {
    moveTimer = setInterval(applyPendingMove, 16)
  }
  return null
})

// 拖拽结束：四分之一屏边缘吸附 + 限制在工作区内
ipcMain.handle('whale:dragEnd', () => {
  if (!win) return { h: null, v: null }
  if (moveTimer) {
    clearInterval(moveTimer)
    moveTimer = null
  }
  applyPendingMove() // 应用最后一次位移，保证吸附计算基于最终位置
  dragState = null
  try {
    const [wx, wy] = win.getPosition()
    const [ww, wh] = win.getSize()
    const bounds = win.getBounds()
    const disp = screen.getDisplayMatching(bounds)
    const wa = disp.workArea
    const centerX = wx + ww / 2
    const centerY = wy + wh / 2
    let hSnap = null
    let vSnap = null
    if (centerX < wa.x + wa.width / 4) hSnap = 'left'
    else if (centerX > wa.x + (wa.width * 3) / 4) hSnap = 'right'
    if (centerY < wa.y + wa.height / 4) vSnap = 'top'
    else if (centerY > wa.y + (wa.height * 3) / 4) vSnap = 'bottom'
    let tx = clamp(wx, wa.x, wa.x + wa.width - ww)
    let ty = clamp(wy, wa.y, wa.y + wa.height - wh)
    if (hSnap === 'left') tx = wa.x
    else if (hSnap === 'right') tx = wa.x + wa.width - ww
    if (vSnap === 'top') ty = wa.y
    else if (vSnap === 'bottom') ty = wa.y + wa.height - wh
    animateWindowTo(tx, ty)
    core.setWinPos({ x: tx, y: ty })
    return { h: hSnap, v: vSnap }
  } catch (err) {
    return { h: null, v: null }
  }
})

// ---------------------------------------------------------------------------
// 应用生命周期
// ---------------------------------------------------------------------------
const gotLock = app.requestSingleInstanceLock()
if (!gotLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (win) {
      if (win.isMinimized()) win.restore()
      win.focus()
    }
  })

  app.whenReady().then(() => {
    createWindow()
    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow()
    })
  })

  app.on('window-all-closed', () => {
    app.quit()
  })
}
