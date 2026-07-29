import { onMounted, onUnmounted } from 'vue'

/**
 * 键盘快捷键组合式函数
 * @param {Object} shortcuts - 快捷键映射 { 'ctrl+k': () => {}, 'escape': () => {} }
 */
export function useKeyboard(shortcuts = {}) {
  function handleKeyDown(e) {
    const key = []

    if (e.ctrlKey || e.metaKey) key.push('ctrl')
    if (e.shiftKey) key.push('shift')
    if (e.altKey) key.push('alt')

    // 特殊键映射
    const keyMap = {
      'Escape': 'escape',
      'Enter': 'enter',
      'Backspace': 'backspace',
      'Delete': 'delete',
      'ArrowUp': 'up',
      'ArrowDown': 'down',
      'ArrowLeft': 'left',
      'ArrowRight': 'right',
      'Tab': 'tab',
      ' ': 'space',
    }

    const mainKey = keyMap[e.key] || e.key.toLowerCase()
    key.push(mainKey)

    const combo = key.join('+')

    if (shortcuts[combo]) {
      e.preventDefault()
      shortcuts[combo](e)
    }
  }

  onMounted(() => {
    document.addEventListener('keydown', handleKeyDown)
  })

  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeyDown)
  })
}

/**
 * 常用快捷键配置
 */
export const commonShortcuts = {
  // Ctrl+Enter: 发送消息
  'ctrl+enter': 'send',

  // Ctrl+N: 新建对话
  'ctrl+n': 'newChat',

  // Ctrl+/: 切换侧边栏
  'ctrl+/': 'toggleSidebar',

  // Ctrl+,: 打开设置
  'ctrl+,': 'settings',

  // Escape: 关闭弹窗/取消
  'escape': 'close',

  // Ctrl+K: 搜索
  'ctrl+k': 'search',

  // Ctrl+Shift+T: 切换主题
  'ctrl+shift+t': 'toggleTheme',
}
