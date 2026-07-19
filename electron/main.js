const { app, BrowserWindow, Tray, Menu, nativeImage, dialog, ipcMain } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const fs = require('fs')

let mainWindow = null
let tray = null
let backendProcess = null
let isQuitting = false

// ========== 后端管理 ==========

function getBackendDir() {
  // 打包后: resources/backend，开发模式: ../backend
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'backend')
  }
  return path.join(__dirname, '..', 'backend')
}

function getPythonPath() {
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

function startBackend() {
  const python = getPythonPath()
  if (!python) {
    dialog.showErrorBox('Python 未找到', '请安装 Python 3.8+ 并确保已加入 PATH 环境变量。')
    return false
  }

  const backendDir = getBackendDir()
  const mainPy = path.join(backendDir, 'main.py')

  if (!fs.existsSync(mainPy)) {
    dialog.showErrorBox('后端文件缺失', `找不到 ${mainPy}`)
    return false
  }

  console.log('[Electron] 启动后端...')
  backendProcess = spawn(python, [mainPy], {
    cwd: backendDir,
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
        const resp = await fetch('http://127.0.0.1:8001/health')
        if (resp.ok) { resolve(true); return }
      } catch {}
      if (Date.now() - start > maxWait) { resolve(false); return }
      setTimeout(check, 500)
    }
    check()
  })
}

// ========== 窗口管理 ==========

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 900,
    minHeight: 600,
    title: '次元人格',
    icon: path.join(__dirname, 'icon.png'),
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
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    const indexPath = app.isPackaged
      ? path.join(process.resourcesPath, 'frontend', 'dist', 'index.html')
      : path.join(__dirname, '..', 'frontend', 'dist', 'index.html')
    mainWindow.loadFile(indexPath)
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
  tray.setToolTip('次元人格')

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

// ========== 应用生命周期 ==========

app.whenReady().then(async () => {
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
  stopBackend()
})

app.on('activate', () => {
  // macOS: 点击 dock 图标重新打开窗口
  if (mainWindow) {
    mainWindow.show()
  }
})
