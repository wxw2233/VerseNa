const { app, BrowserWindow, Tray, Menu, nativeImage, dialog, ipcMain } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const fs = require('fs')

let mainWindow = null
let petWindow = null
let tray = null
let backendProcess = null
let isQuitting = false
let latestPetState = { state: 'idle', theme: '' }
const PET_BASE_SIZE = { width: 190, height: 230 }

const hasSingleInstanceLock = app.requestSingleInstanceLock()
if (!hasSingleInstanceLock) {
  app.quit()
}

// ========== 后端管理 ==========

function getBackendDir() {
  // 打包后: resources/backend，开发模式: ../backend
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'backend')
  }
  return path.join(__dirname, '..', 'backend')
}

function getPythonPath() {
  if (app.isPackaged) {
    const embeddedPython = path.join(process.resourcesPath, 'python', 'python.exe')
    return fs.existsSync(embeddedPython) ? embeddedPython : null
  }

  // 优先使用虚拟环境
  const venvPython = path.join(__dirname, '..', 'backend', '.venv', 'Scripts', 'python.exe')
  if (fs.existsSync(venvPython)) return venvPython

  // 尝试 python3 / python
  const candidates = ['python3', 'python', 'py']
  for (const cmd of candidates) {
    try {
      const { execSync } = require('child_process')
      execSync(`${cmd} --version`, { stdio: 'ignore' })
      return cmd
    } catch {}
  }
  return null
}

function copyMissingContent(source, target) {
  if (!fs.existsSync(source)) return
  const stat = fs.statSync(source)
  if (stat.isDirectory()) {
    fs.mkdirSync(target, { recursive: true })
    for (const entry of fs.readdirSync(source)) {
      copyMissingContent(path.join(source, entry), path.join(target, entry))
    }
    return
  }
  if (!fs.existsSync(target)) {
    fs.mkdirSync(path.dirname(target), { recursive: true })
    fs.copyFileSync(source, target)
  }
}

function initializePackagedContent() {
  if (!app.isPackaged) return
  const contentDir = path.join(app.getPath('userData'), 'content')
  for (const directory of ['personas', 'themes', 'themepacks']) {
    copyMissingContent(
      path.join(process.resourcesPath, directory),
      path.join(contentDir, directory),
    )
  }
  fs.mkdirSync(path.join(contentDir, 'plugins'), { recursive: true })
}

function startBackend() {
  const python = getPythonPath()
  if (!python) {
    const message = app.isPackaged
      ? '安装包中的 Python 运行时缺失，请重新安装 VerseNa。'
      : '请安装 Python 3.10+ 并确保已加入 PATH 环境变量。'
    dialog.showErrorBox('Python 未找到', message)
    return false
  }

  const backendDir = getBackendDir()
  const mainPy = path.join(backendDir, 'main.py')

  if (!fs.existsSync(mainPy)) {
    dialog.showErrorBox('后端文件缺失', `找不到 ${mainPy}`)
    return false
  }

  console.log('[Electron] 启动后端...')
  const backendEnv = { ...process.env, VERSENA_HOST: '127.0.0.1' }
  if (app.isPackaged) {
    const userDataDir = app.getPath('userData')
    const pythonDir = path.dirname(python)
    const existingPath = backendEnv.PATH || backendEnv.Path || ''
    backendEnv.VERSENA_DATA_DIR = path.join(userDataDir, 'data')
    backendEnv.VERSENA_CONTENT_DIR = path.join(userDataDir, 'content')
    backendEnv.VERSENA_SKILLS_DATA_DIR = path.join(userDataDir, 'skills')
    backendEnv.VERSENA_FRONTEND_DIST = path.join(process.resourcesPath, 'frontend', 'dist')
    backendEnv.PYTHONUTF8 = '1'
    backendEnv.PYTHONIOENCODING = 'utf-8'
    delete backendEnv.PATH
    delete backendEnv.Path
    backendEnv.Path = [pythonDir, path.join(pythonDir, 'Scripts'), existingPath]
      .filter(Boolean)
      .join(path.delimiter)
  }
  backendProcess = spawn(python, [mainPy], {
    cwd: backendDir,
    env: backendEnv,
    stdio: ['pipe', 'pipe', 'pipe'],
    windowsHide: true,
  })

  backendProcess.stdout.on('data', (data) => {
    console.log(`[Backend] ${data.toString().trim()}`)
  })

  backendProcess.stderr.on('data', (data) => {
    console.error(`[Backend] ${data.toString().trim()}`)
  })

  backendProcess.on('error', (err) => {
    console.error('[Electron] 后端启动失败:', err)
    dialog.showErrorBox('后端启动失败', err.message)
  })

  backendProcess.on('exit', (code) => {
    console.log(`[Electron] 后端退出，代码: ${code}`)
    backendProcess = null
    if (!isQuitting && code !== 0) {
      // 非正常退出，尝试重启
      setTimeout(() => {
        if (!isQuitting) {
          console.log('[Electron] 尝试重启后端...')
          startBackend()
        }
      }, 3000)
    }
  })

  return true
}

function stopBackend() {
  if (backendProcess) {
    console.log('[Electron] 停止后端...')
    backendProcess.kill('SIGTERM')
    // 给 3 秒优雅退出，否则强制杀死
    setTimeout(() => {
      if (backendProcess) {
        backendProcess.kill('SIGKILL')
        backendProcess = null
      }
    }, 3000)
  }
}

// 等待后端就绪
function waitForBackend(maxWait = 15000) {
  return new Promise((resolve) => {
    const start = Date.now()
    const check = async () => {
      try {
        const resp = await fetch('http://127.0.0.1:8002/health')
        if (resp.ok) { resolve(true); return }
      } catch {}
      if (Date.now() - start > maxWait) { resolve(false); return }
      setTimeout(check, 500)
    }
    check()
  })
}

// ========== 窗口管理 ==========

function getFrontendUrl(route = '/') {
  const baseUrl = app.isPackaged ? 'http://127.0.0.1:8002' : 'http://localhost:5173'
  return `${baseUrl}${route}`
}

function createWindow() {
  const iconPath = path.join(__dirname, 'icon.png')
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 900,
    minHeight: 600,
    title: 'VerseNa',
    icon: fs.existsSync(iconPath) ? iconPath : undefined,
    show: false, // 等后端就绪后再显示
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  })

  // 开发模式
  const isDev = !app.isPackaged

  if (isDev) {
    mainWindow.loadURL(getFrontendUrl('/'))
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadURL(getFrontendUrl('/'))
  }

  // 窗口准备好后显示
  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
  })

  // 关闭时最小化到托盘（而不是退出）
  mainWindow.on('close', (e) => {
    if (!isQuitting) {
      e.preventDefault()
      mainWindow.hide()
      return false
    }
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

function createPetWindow() {
  if (petWindow && !petWindow.isDestroyed()) {
    petWindow.showInactive()
    return petWindow
  }

  petWindow = new BrowserWindow({
    width: PET_BASE_SIZE.width,
    height: PET_BASE_SIZE.height,
    minWidth: Math.round(PET_BASE_SIZE.width * 0.6),
    minHeight: Math.round(PET_BASE_SIZE.height * 0.6),
    maxWidth: 420,
    maxHeight: 500,
    title: 'VerseNa 桌宠',
    transparent: true,
    frame: false,
    resizable: true,
    movable: true,
    minimizable: false,
    maximizable: false,
    closable: true,
    skipTaskbar: true,
    hasShadow: false,
    alwaysOnTop: true,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  })

  petWindow.setAlwaysOnTop(true, 'floating')

  petWindow.setMenu(null)
  petWindow.loadURL(getFrontendUrl('/pet'))
  petWindow.once('ready-to-show', () => {
    if (!petWindow || petWindow.isDestroyed()) return
    petWindow.showInactive()
    petWindow.webContents.send('pet-state', latestPetState)
  })
  petWindow.webContents.on('context-menu', (event) => {
    event.preventDefault()
    const menu = Menu.buildFromTemplate([
      {
        label: '显示 VerseNa',
        click: () => {
          if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.show()
            mainWindow.focus()
          }
        },
      },
      { type: 'separator' },
      {
        label: '关闭桌宠',
        click: () => petWindow?.hide(),
      },
    ])
    menu.popup({ window: petWindow })
  })
  petWindow.on('closed', () => {
    petWindow = null
  })

  return petWindow
}

// ========== 系统托盘 ==========

function createTray() {
  const iconPath = path.join(__dirname, 'icon.png')
  let icon
  if (fs.existsSync(iconPath)) {
    icon = nativeImage.createFromPath(iconPath)
  } else {
    // 默认图标
    icon = nativeImage.createEmpty()
  }

  tray = new Tray(icon)
  tray.setToolTip('VerseNa')

  const contextMenu = Menu.buildFromTemplate([
    {
      label: '显示窗口',
      click: () => {
        if (mainWindow) {
          mainWindow.show()
          mainWindow.focus()
        }
      },
    },
    {
      label: '显示桌宠',
      click: () => createPetWindow(),
    },
    { type: 'separator' },
    {
      label: '重启后端',
      click: () => {
        stopBackend()
        setTimeout(() => {
          startBackend()
          waitForBackend().then((ok) => {
            if (ok && mainWindow) mainWindow.reload()
          })
        }, 1000)
      },
    },
    { type: 'separator' },
    {
      label: '退出',
      click: () => {
        isQuitting = true
        app.quit()
      },
    },
  ])

  tray.setContextMenu(contextMenu)

  tray.on('double-click', () => {
    if (mainWindow) {
      mainWindow.show()
      mainWindow.focus()
    }
  })
}

// ========== IPC ==========

ipcMain.handle('get-platform', () => process.platform)
ipcMain.handle('get-version', () => app.getVersion())
ipcMain.handle('show-main', () => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.show()
    mainWindow.focus()
  }
  return true
})
ipcMain.handle('open-pet', () => {
  createPetWindow()
  return true
})
ipcMain.handle('close-pet', () => {
  if (petWindow && !petWindow.isDestroyed()) petWindow.hide()
  return true
})
ipcMain.handle('resize-pet', (_event, scale) => {
  if (!petWindow || petWindow.isDestroyed()) return false
  const numericScale = Number(scale)
  if (!Number.isFinite(numericScale)) return false
  const clamped = Math.min(1.8, Math.max(0.6, numericScale))
  petWindow.setSize(
    Math.round(PET_BASE_SIZE.width * clamped),
    Math.round(PET_BASE_SIZE.height * clamped),
  )
  if (!petWindow.webContents.isLoading()) {
    petWindow.webContents.send('pet-scale', clamped)
  }
  return true
})
ipcMain.on('pet-state', (_event, state) => {
  if (!state || typeof state !== 'object') return
  latestPetState = {
    state: typeof state.state === 'string' ? state.state : 'idle',
    theme: typeof state.theme === 'string' ? state.theme : '',
  }
  if (petWindow && !petWindow.isDestroyed() && !petWindow.webContents.isLoading()) {
    petWindow.webContents.send('pet-state', latestPetState)
  }
})
ipcMain.on('pet-config', (_event, config) => {
  if (!config || typeof config !== 'object') return
  if (petWindow && !petWindow.isDestroyed() && !petWindow.webContents.isLoading()) {
    petWindow.webContents.send('pet-config', config)
  }
})

// ========== 应用生命周期 ==========

app.whenReady().then(async () => {
  initializePackagedContent()

  // 启动后端
  const started = startBackend()
  if (!started) {
    app.quit()
    return
  }

  // 等待后端就绪
  const ready = await waitForBackend()
  if (!ready) {
    console.warn('[Electron] 后端启动超时，继续加载前端...')
  }

  // 创建窗口和托盘
  createWindow()
  createTray()
})

app.on('window-all-closed', () => {
  // Windows: 不退出，保持托盘运行
  if (process.platform === 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  isQuitting = true
  if (petWindow && !petWindow.isDestroyed()) petWindow.destroy()
  stopBackend()
})

app.on('activate', () => {
  // macOS: 点击 dock 图标重新打开窗口
  if (mainWindow) {
    mainWindow.show()
  }
})

app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore()
    mainWindow.show()
    mainWindow.focus()
  }
})
