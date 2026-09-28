// ============================================================================
// dsh-whale-widget 桌面版核心逻辑（无 Electron 依赖，可独立单元测试）
// ----------------------------------------------------------------------------
// 职责：
//  1. userdata.json 读写（与 EXE 同目录；settings / pos 明文，
//     apiKey / platformToken 用 AES-256-GCM 加密存储）
//  2. DeepSeek 余额拉取（Bearer API_KEY）+ 今日已用（记账 / 令牌两种模式）
//  3. 峰谷定价换算（与 DSH 插件版同表）
//
// 加密说明：密钥由「内置 pepper + 本机标识（hostname|user|MAC）」经
// PBKDF2-SHA256 派生。属于「防明文直读」级别的混淆保护——拿到 EXE 与本机
// 访问权限的攻击者仍可逆向，但不至于把 API_KEY 明文躺在 userdata.json 里。
// ----------------------------------------------------------------------------
// 【结构分析注释 · 非原作者所写，仅供阅读参考】
//
// 【本文件的设计：无 Electron 依赖 → 可独立单测】
//   只 require node 内置模块（fs / path / os / crypto），不碰 electron。
//   所以这一层能在纯 Node 环境里跑测试，也是三层架构里唯一"可测"的一层。
//
// 【两种函数，职责分明 —— 这是本文件最重要的结构特征】
//   ① 模块级纯函数（无状态，可直接调）：价格换算 / 加解密 / 数据结构
//        priceFor(model)          查模型单价（命中/未命中/输出 × 峰谷）
//        isPeakTime(timeSec)      是否处于高峰时段（9-12 点、14-18 点）
//        machineFingerprint()     本机指纹（hostname|user|MAC）
//        machineKey()             指纹 + pepper → PBKDF2 → AES 密钥
//        encryptSecret(plain)     明文 → {iv, tag, data} 加密对象
//        decryptSecret(obj)       加密对象 → 明文（失败返回 null）
//        defaultData()            userdata.json 的默认结构
//        todayKey()               今天的日期串（跨天归零的判据）
//   ② 工厂函数 createWhaleCore() 返回的对象方法（有状态，状态藏在闭包里）
//        磁盘 I/O : readData / writeData / save
//        配置读写 : getConfig / saveConfig / normalizeUsageMode
//        凭据写入 : setApiKey / setPlatformToken   （只写，没有对应的读接口）
//        窗口位置 : getWinPos / setWinPos
//        余额相关 : fetchBalance      —— 唯一发 HTTP 请求的地方（Bearer KEY）
//                  pickBalanceInfo   —— 从多币种余额里挑一个
//                  fetchUsage        —— 令牌模式：查平台用量接口
//                  computeTodayUsage —— 从账本算今日已用
//                  recordLedgerUsage —— 记账模式核心：用余额差值累加
//                  getBalance        —— 对外主入口，带 25 秒 TTL 缓存
//                  fetchLastTurn     —— 桌面版无数据源，返回空
//
// 【调用关系（自顶向下）】
//   main.js 的 ipcMain handler
//        └→ core.getConfig / saveConfig / setApiKey / setPlatformToken
//           core.getBalance ──→ 缓存未过期？直接返回
//                            └→ 过期 → fetchBalance（网络）
//                                     └→ recordLedgerUsage（记账）→ save（落盘）
//           core.fetchLastTurn（桌面版恒空）
//
// 【数据流一句话】网络拿余额 → 与上次余额作差 → 差值累加进当天账本 → 写 userdata.json
// ============================================================================
'use strict'

const fs = require('node:fs')
const path = require('node:path')
const os = require('node:os')
const crypto = require('node:crypto')

// ---------------------------------------------------------------------------
// 常量区：接口地址 / 缓存时长 / 价格表
// ---------------------------------------------------------------------------
const BALANCE_URL = 'https://api.deepseek.com/user/balance'
const BALANCE_TTL_MS = 25000

// DeepSeek CNY prices per million tokens: [空闲时段价, 高峰时段价].
// 高峰时段：每日 9:00–12:00 和 14:00–18:00（北京时间）。
const PEAK_HOURS = [
  [9, 12],
  [14, 18],
]
const BASE_PRICE = { hit: [0.05, 0.1], miss: [1.5, 3.0], out: [4.5, 9.0] }
// deepseek-v4-pro 为 flash 的 3 倍价（官方 2026-08-17 生效）；vision-exp 与 flash 同价
const PRO_PRICE = { hit: [0.15, 0.3], miss: [4.5, 9.0], out: [13.5, 27.0] }
const PRICING = {
  'deepseek-v4-flash-vision-exp': BASE_PRICE,
  'deepseek-v4-flash': BASE_PRICE,
  'deepseek-v4-pro': PRO_PRICE,
  'deepseek-chat': BASE_PRICE,
  'deepseek-reasoner': BASE_PRICE,
  _default: BASE_PRICE,
}

function priceFor(model) {
  const m = String(model || '').toLowerCase()
  for (const key of Object.keys(PRICING)) {
    if (key === '_default') continue
    if (m.indexOf(key) !== -1) return PRICING[key]
  }
  return PRICING._default
}

// bucket time is an epoch second; derive the Beijing local hour to pick peak vs off-peak price.
function isPeakTime(timeSec) {
  if (!isFinite(Number(timeSec))) return false;
  const date = new Date(Number(timeSec) * 1000 + 8 * 3600 * 1000);
  const day = date.getUTCDay(); // 0=周日, 6=周六
  // 🆕 周末全天谷价（不判定为高峰）
  if (day === 0 || day === 6) return false;
  const hour = date.getUTCHours();
  for (const [start, end] of PEAK_HOURS) {
    if (hour >= start && hour < end) return true;
  }
  return false;
}

// ---------------------------------------------------------------------------
// 加密存储
// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// 加密区：pepper + 本机指纹 → PBKDF2 → AES-256-GCM
//   注意：密钥绑定本机标识，所以 userdata.json 换机器后解不开（需重填 KEY）
// ---------------------------------------------------------------------------
const PEPPER = 'dsh-whale-widget::desktop::v1'

function machineFingerprint() {
  let mac = 'unknown'
  try {
    const ifaces = os.networkInterfaces()
    for (const name of Object.keys(ifaces)) {
      const list = ifaces[name] || []
      for (const item of list) {
        if (item && !item.internal && item.mac && item.mac !== '00:00:00:00:00:00') {
          mac = item.mac
          break
        }
      }
      if (mac !== 'unknown') break
    }
  } catch (err) {}
  return [os.hostname(), os.userInfo().username, mac].join('|')
}

function machineKey() {
  return crypto.createHash('sha256').update(PEPPER + '::' + machineFingerprint()).digest()
}

function encryptSecret(plain) {
  const salt = crypto.randomBytes(16)
  const key = crypto.pbkdf2Sync(machineKey(), salt, 100000, 32, 'sha256')
  const iv = crypto.randomBytes(12)
  const cipher = crypto.createCipheriv('aes-256-gcm', key, iv)
  const enc = Buffer.concat([cipher.update(String(plain), 'utf8'), cipher.final()])
  const tag = cipher.getAuthTag()
  return {
    v: 1,
    salt: salt.toString('base64'),
    iv: iv.toString('base64'),
    tag: tag.toString('base64'),
    data: enc.toString('base64'),
  }
}

function decryptSecret(obj) {
  try {
    if (!obj || obj.v !== 1) return null
    const key = crypto.pbkdf2Sync(machineKey(), Buffer.from(obj.salt, 'base64'), 100000, 32, 'sha256')
    const decipher = crypto.createDecipheriv('aes-256-gcm', key, Buffer.from(obj.iv, 'base64'))
    decipher.setAuthTag(Buffer.from(obj.tag, 'base64'))
    return Buffer.concat([decipher.update(Buffer.from(obj.data, 'base64')), decipher.final()]).toString('utf8')
  } catch (err) {
    return null
  }
}

// ---------------------------------------------------------------------------
// 数据存储
// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// 数据结构区：userdata.json 的完整形状
//   settings 明文 / pos 明文 / secrets 加密 / usage 账本 / winPos 窗口位置
// ---------------------------------------------------------------------------
function defaultData() {
  return {
    version: 2,
    settings: {
      scale: 1.5,
      sound: true,
      vol: 0.9,
      soundSet: 'duck',
      usageMode: 'ledger',
      peakMode: 'default',
      bubbleOn: true,
      scrollGapOn: false,
      scrollGapPx: 17,
    },
    pos: { hAnchor: 'right', vAnchor: 'bottom' },
    secrets: {},
    usage: {
      date: todayKey(),
      lastBalance: null,
      todayUsage: 0,
      history: {},
      currency: null,   // 🆕 币种字段
    },
    winPos: null,
  }
}

function todayKey() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate())
}

// ---------------------------------------------------------------------------
// 工厂函数：全部有状态逻辑在这里，状态（data 缓存）藏在闭包内，外部只能访问
// 返回对象上的方法。main.js 启动时 createWhaleCore 一次，之后全程复用。
// ---------------------------------------------------------------------------
function createWhaleCore({ dataFile }) {
  const file = path.resolve(dataFile)

  function readData() {
    try {
      const parsed = JSON.parse(fs.readFileSync(file, 'utf8'))
      return parsed && typeof parsed === 'object' ? parsed : null
    } catch (err) {
      return null
    }
  }

  function writeData(obj) {
    try {
      fs.mkdirSync(path.dirname(file), { recursive: true })
      fs.writeFileSync(file, JSON.stringify(obj, null, 2), 'utf8')
      return true
    } catch (err) {
      return false
    }
  }

  let data = Object.assign(defaultData(), readData() || {})
  if (!data.settings) data.settings = defaultData().settings
  if (!data.secrets) data.secrets = {}
  if (!data.usage) data.usage = defaultData().usage
  if (!data.pos) data.pos = defaultData().pos

  function save() {
    if (!writeData(data)) {
      // 写失败（例如 EXE 目录只读）时回退到用户目录，保证功能可用
      try {
        const fallback = path.join(os.homedir(), '.dsh-whale-widget-userdata.json')
        fs.writeFileSync(fallback, JSON.stringify(data, null, 2), 'utf8')
      } catch (err) {}
    }
  }

  // ------------------------- settings -------------------------
  function normalizeUsageMode(m) {
    return m === 'token' ? 'token' : 'ledger'
  }

  function getConfig() {
    const s = data.settings
    return {
      scale: typeof s.scale === 'number' ? s.scale : 1.5,
      sound: s.sound !== false,
      vol: typeof s.vol === 'number' ? s.vol : 0.9,
      soundSet: s.soundSet === 'fx1' ? 'fx1' : 'duck',
      usageMode: normalizeUsageMode(s.usageMode),
      peakMode: s.peakMode === 'liangwen' || s.peakMode === 'qiangqiang' ? s.peakMode : 'default',
      bubbleOn: s.bubbleOn !== false,
      scrollGapOn: s.scrollGapOn === true,
      scrollGapPx: typeof s.scrollGapPx === 'number' ? Math.round(s.scrollGapPx) : 17,
      pos: {
        hAnchor: data.pos && (data.pos.hAnchor === 'left' || data.pos.hAnchor === 'right') ? data.pos.hAnchor : 'right',
        vAnchor: data.pos && (data.pos.vAnchor === 'top' || data.pos.vAnchor === 'bottom') ? data.pos.vAnchor : 'bottom',
      },
      hasApiKey: !!data.secrets.apiKey,
      hasPlatformToken: !!data.secrets.platformToken,
    }
  }

  function saveConfig(cfg) {
    if (!cfg || typeof cfg !== 'object') return { ok: false, error: 'bad config' }
    const s = data.settings
    if (typeof cfg.scale === 'number' && isFinite(cfg.scale)) s.scale = cfg.scale
    if (typeof cfg.sound === 'boolean') s.sound = cfg.sound
    if (typeof cfg.vol === 'number' && isFinite(cfg.vol)) s.vol = cfg.vol
    if (typeof cfg.soundSet === 'string') s.soundSet = cfg.soundSet === 'fx1' ? 'fx1' : 'duck'
    if (typeof cfg.usageMode === 'string') {
      const old = normalizeUsageMode(s.usageMode)
      s.usageMode = normalizeUsageMode(cfg.usageMode)
      if (old !== s.usageMode) balanceCache = null
    }
    if (typeof cfg.peakMode === 'string') s.peakMode = cfg.peakMode === 'liangwen' || cfg.peakMode === 'qiangqiang' ? cfg.peakMode : 'default'
    if (typeof cfg.bubbleOn === 'boolean') s.bubbleOn = cfg.bubbleOn
    if (typeof cfg.scrollGapOn === 'boolean') s.scrollGapOn = cfg.scrollGapOn
    if (typeof cfg.scrollGapPx === 'number') s.scrollGapPx = Math.round(cfg.scrollGapPx) > 0 ? Math.round(cfg.scrollGapPx) : 0
    if (cfg.pos && typeof cfg.pos === 'object') {
      const h = cfg.pos.hAnchor
      const v = cfg.pos.vAnchor
      if (h === 'left' || h === 'right' || h === null) data.pos.hAnchor = h === null ? 'right' : h
      if (v === 'top' || v === 'bottom') data.pos.vAnchor = v
    }
    save()
    return { ok: true }
  }

  function setApiKey(key) {
    const k = String(key || '').trim()
    if (!k) {
      delete data.secrets.apiKey
    } else {
      data.secrets.apiKey = encryptSecret(k)
    }
    balanceCache = null
    save()
    return { ok: true, hasApiKey: !!data.secrets.apiKey }
  }

  function setPlatformToken(token) {
    const t = String(token || '').trim()
    if (!t) {
      delete data.secrets.platformToken
    } else {
      data.secrets.platformToken = encryptSecret(t)
    }
    balanceCache = null
    save()
    return { ok: true, hasPlatformToken: !!data.secrets.platformToken }
  }

  // ------------------------- window pos -------------------------
  function getWinPos() {
    return data.winPos && typeof data.winPos.x === 'number' && typeof data.winPos.y === 'number'
      ? { x: data.winPos.x, y: data.winPos.y }
      : null
  }
  function setWinPos(pos) {
    if (pos && typeof pos.x === 'number' && typeof pos.y === 'number') {
      data.winPos = { x: Math.round(pos.x), y: Math.round(pos.y) }
      save()
    }
  }

  // ------------------------- balance -------------------------
  let balanceCache = null
  let balanceInFlight = null

  function pickBalanceInfo(infos) {
    if (!Array.isArray(infos) || infos.length === 0) return null
    const num = (x) => (x && x.total_balance !== undefined ? Number(x.total_balance) : NaN)
    return (
      infos.find((x) => x && x.currency === 'CNY' && num(x) > 0) ||
      infos.find((x) => num(x) > 0) ||
      infos.find((x) => x && x.currency === 'CNY') ||
      infos[0]
    )
  }

  async function fetchBalance() {
    const key = data.secrets.apiKey ? decryptSecret(data.secrets.apiKey) : null
    if (!key) {
      return { ok: false, code: 'NO_KEY', error: '未配置 API_KEY（菜单 → API_KEY 填写）' }
    }
    let lastErr = null
    for (let attempt = 0; attempt < 2; attempt++) {
      let res
      try {
        res = await fetch(BALANCE_URL, {
          headers: { Authorization: 'Bearer ' + key },
          signal: AbortSignal.timeout(20000),
        })
      } catch (err) {
        lastErr = err
        if (attempt === 0) await new Promise((r) => setTimeout(r, 500))
        continue
      }
      if (!res.ok) {
        lastErr = new Error('HTTP ' + res.status)
        if (res.status < 500) break
        if (attempt === 0) await new Promise((r) => setTimeout(r, 500))
        continue
      }
      let data
      try {
        data = await res.json()
      } catch (err) {
        return { ok: false, code: 'PARSE', error: '余额接口返回不是合法 JSON' }
      }
      const info = pickBalanceInfo(data && data.balance_infos)
      if (!info || info.total_balance === undefined) {
        return { ok: false, code: 'SHAPE', error: '余额接口返回结构异常' }
      }
      return {
        ok: true,
        totalBalance: Number(info.total_balance),
        currency: String(info.currency || 'CNY'),
        updatedAt: new Date().toISOString(),
      }
    }
    const transient = !(lastErr && /^HTTP 4\d\d/.test(lastErr.message))
    return {
      ok: false,
      code: 'HTTP',
      transient: transient,
      error: '余额接口请求失败: ' + String((lastErr && lastErr.message) || lastErr).slice(0, 200),
    }
  }

  async function fetchUsage() {
    const token = data.secrets.platformToken ? decryptSecret(data.secrets.platformToken) : null
    if (!token) return { error: 'no platform token' }
    try {
      const now = new Date()
      const tz = -now.getTimezoneOffset() * 60
      const start = Math.floor(new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime() / 1000)
      const end = start + 86400
      const url = 'https://platform.deepseek.com/api/v0/usage/by_api_key/amount?start=' + start + '&end=' + end + '&tz=' + tz
      const res = await fetch(url, {
        headers: { Authorization: 'Bearer ' + String(token).replace(/^Bearer\s+/i, '') },
        signal: AbortSignal.timeout(15000),
      })
      if (!res.ok) return { error: 'http ' + res.status }
      const json = await res.json()
      const u = computeTodayUsage(json)
      if (u && isFinite(u.amount)) return { amount: u.amount, tokens: u.tokens }
      return { error: 'no usage' }
    } catch (err) {
      return { error: String((err && err.message) || err) }
    }
  }

  function computeTodayUsage(d) {
    let dd = d
    if (dd && dd.data && dd.data.biz_data && Array.isArray(dd.data.biz_data.series)) dd = dd.data.biz_data
    else if (dd && dd.data && Array.isArray(dd.data.series)) dd = dd.data
    const series = Array.isArray(dd.series) ? dd.series : null
    if (!series || series.length === 0) return null
    let cost = 0
    let tokens = 0
    let found = false
    for (const s of series) {
      if (!s || typeof s !== 'object') continue
      const p = priceFor(s.model)
      const buckets = Array.isArray(s.buckets) ? s.buckets : []
      for (const b of buckets) {
        const u = b && b.usage
        if (!u || typeof u !== 'object') continue
        const hit = Number(u.PROMPT_CACHE_HIT_TOKEN) || 0
        const miss = Number(u.PROMPT_CACHE_MISS_TOKEN) || 0
        const out = Number(u.RESPONSE_TOKEN) || 0
        if (hit + miss + out === 0) continue
        found = true
        tokens += hit + miss + out
        const pi = isPeakTime(b.time) ? 1 : 0
        cost += (hit / 1e6) * p.hit[pi] + (miss / 1e6) * p.miss[pi] + (out / 1e6) * p.out[pi]
      }
    }
    return found ? { amount: cost, tokens: tokens } : null
  }

  // ================================================================
  // 🆕 记账模式（v0.2.9 同步：支持币种感知）
  // 每次观测到余额后，用余额正差值累计当天用量（跨天自动归零并归档）
  // 当检测到币种变化时，自动重置 todayUsage 并归档旧币种数据
  // ================================================================
  function recordLedgerUsage(currentBalance, currency) {
    const t = todayKey()
    const u = data.usage

    // 如果币种发生了变化，把当前今日已用按旧币种归档，然后重置
    if (u.currency && u.currency !== currency) {
      if (typeof u.todayUsage === 'number' && u.todayUsage > 0) {
        u.history = u.history || {}
        const key = u.date + '_' + u.currency
        u.history[key] = (u.history[key] || 0) + u.todayUsage
      }
      u.todayUsage = 0
      u.lastBalance = currentBalance
      u.currency = currency
      save()
      return u
    }

    // 跨天逻辑（币种不变）
    if (u.date !== t) {
      if (u.date && typeof u.todayUsage === 'number') {
        u.history = u.history || {}
        const key = u.date + (u.currency ? '_' + u.currency : '')
        u.history[key] = (u.history[key] || 0) + u.todayUsage
      }
      u.date = t
      u.lastBalance = currentBalance
      u.todayUsage = 0
      u.currency = currency
    } else {
      // 同一天，正常累加差值
      const prev = typeof u.lastBalance === 'number' ? u.lastBalance : currentBalance
      if (typeof prev === 'number' && typeof currentBalance === 'number' && currentBalance < prev) {
        u.todayUsage = (typeof u.todayUsage === 'number' ? u.todayUsage : 0) + (prev - currentBalance)
      }
      u.lastBalance = currentBalance
      // 确保币种已设置（首次写入）
      if (!u.currency) u.currency = currency
    }

    // 清理历史记录（最多保留 30 条）
    const keys = Object.keys(u.history || {}).sort()
    while (keys.length > 30) {
      delete u.history[keys.shift()]
    }

    save()
    return u
  }

  async function getBalancePayload() {
    const payload = await fetchBalance()
    if (!payload.ok) return payload
    // 🆕 传入币种参数
    const led = recordLedgerUsage(Number(payload.totalBalance), String(payload.currency || 'CNY'))
    const mode = normalizeUsageMode(data.settings.usageMode)
    const full = { ...payload }
    full.isPeak = isPeakTime(Math.floor(Date.now() / 1000))
    if (mode === 'token') {
      const u = await fetchUsage()
      if (u && u.amount !== undefined) {
        full.todayUsage = u.amount
        full.usageMode = 'token'
        return full
      }
    }
    full.todayUsage = led.todayUsage
    full.usageMode = 'ledger'
    return full
  }

  function getBalance() {
    const now = Date.now()
    if (balanceCache && now - balanceCache.at < BALANCE_TTL_MS) {
      return Promise.resolve(balanceCache.payload)
    }
    if (balanceInFlight) return balanceInFlight
    balanceInFlight = getBalancePayload()
      .then((payload) => {
        if (payload.ok) {
          balanceCache = { at: now, payload }
          return payload
        }
        if (payload.transient && balanceCache) {
          return { ...balanceCache.payload, stale: true, error: payload.error }
        }
        return payload
      })
      .catch((err) => ({
        ok: false,
        code: 'ERROR',
        error: '余额服务异常: ' + String((err && err.message) || err).slice(0, 200),
      }))
      .finally(() => {
        balanceInFlight = null
      })
    return balanceInFlight
  }

  function fetchLastTurn() {
    // 桌面版没有 DSH 会话事件，永远返回空轮次
    return Promise.resolve({ ok: true, seq: 0, turn: null, amount: null, tokens: null, ts: null })
  }

  return {
    getConfig,
    saveConfig,
    setApiKey,
    setPlatformToken,
    getWinPos,
    setWinPos,
    getBalance,
    fetchLastTurn,
    // 测试/调试用
    _data: () => data,
    _machineFingerprint: machineFingerprint,
  }
}

module.exports = { createWhaleCore, priceFor, isPeakTime, encryptSecret, decryptSecret, machineFingerprint }