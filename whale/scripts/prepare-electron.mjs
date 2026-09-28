// ============================================================================
// prepare-electron.mjs —— 构建前准备带应用图标/版本信息的 Electron dist
// ----------------------------------------------------------------------------
// 背景：electron-builder 通过 app-builder 的 unpack-electron 从 electron 缓存
// zip 重新解压，忽略 node_modules/electron/dist；且解压 winCodeSign 工具链在
// 无管理员/未开开发者模式的 Windows 上会因符号链接权限失败。因此：
//   1. 首次运行：把 node_modules/electron/dist 整体复制到 build/electron-dist
//      （electron-builder 通过 build.electronDist 使用这个目录，见 package.json）
//   2. 用 rcedit 给 build/electron-dist/electron.exe 打补丁（图标 + 版本信息）
//   3. 之后每次打包都基于这份已打补丁的 dist，产物 EXE 与任务栏图标均正确
//
// rcedit 来源：electron-builder-binaries 仓库 winCodeSign-2.6.0 包内
// （https://github.com/electron-userland/electron-builder-binaries），
// 本仓库已复制到 build/tools/rcedit-x64.exe 以支持离线/非管理员构建。
// ============================================================================
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const desktopRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const pkg = JSON.parse(fs.readFileSync(path.join(desktopRoot, 'package.json'), 'utf8'))

const rcedit = path.join(desktopRoot, 'build', 'tools', 'rcedit-x64.exe')
const icon = path.join(desktopRoot, 'build', 'icon.ico')
const electronDistDir = path.join(desktopRoot, 'build', 'electron-dist')
const electronExe = path.join(electronDistDir, 'electron.exe')
const version = pkg.version || '0.0.0'

if (!fs.existsSync(rcedit)) {
  console.error('缺少 rcedit: ' + rcedit + '（可从 electron-builder-binaries winCodeSign-2.6.0 中获取）')
  process.exit(1)
}
if (!fs.existsSync(icon)) {
  console.error('缺少图标: ' + icon)
  process.exit(1)
}

// 首次运行：从 npm 安装的 electron 包复制一份 dist（之后可离线复用）
if (!fs.existsSync(electronExe)) {
  const srcDist = path.join(desktopRoot, 'node_modules', 'electron', 'dist')
  if (!fs.existsSync(path.join(srcDist, 'electron.exe'))) {
    console.error('缺少 electron dist（请先 npm install）：' + srcDist)
    process.exit(1)
  }
  console.log('复制 electron dist -> ' + electronDistDir)
  fs.cpSync(srcDist, electronDistDir, { recursive: true })
}

const args = [
  electronExe,
  '--set-icon', icon,
  '--set-version-string', 'FileDescription', pkg.description || 'DeepSeek 余额小鲸鱼桌面挂件',
  '--set-version-string', 'ProductName', 'DeepSeekWhaleWidget',
  '--set-version-string', 'CompanyName', 'MeteorNOX',
  '--set-version-string', 'LegalCopyright', 'Copyright (c) 2026 MeteorNOX, EthanMaven',
  '--set-file-version', version + '.0',
  '--set-product-version', version + '.0',
]

const r = spawnSync(rcedit, args, { stdio: 'inherit' })
if (r.error || r.status !== 0) {
  console.error('rcedit 失败: ' + (r.error ? r.error.message : 'exit ' + r.status))
  process.exit(1)
}
console.log('electron dist 已打补丁（图标 + 版本 ' + version + '）')
