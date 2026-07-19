import { ref, onUnmounted } from 'vue'
import { useToast } from './useToast'

export function useWebSocket(url = `ws://${location.host}/ws/chat`) {
  const ws = ref(null)
  const connected = ref(false)
  const onMessage = ref(null)
  const toast = useToast()
  let reconnectTimer = null
  let reconnectAttempts = 0
  let connectionId = 0      // 每次 connect 递增，防止旧连接的 onclose 误触发
  let manualClose = false   // 手动断开时不重连

  function connect() {
    if (ws.value && ws.value.readyState <= 1) return

    manualClose = false
    const myId = ++connectionId

    ws.value = new WebSocket(url)

    ws.value.onopen = () => {
      if (myId !== connectionId) return
      connected.value = true
      if (reconnectAttempts > 0) {
        toast.success('连接已恢复')
      }
      reconnectAttempts = 0
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
    }

    ws.value.onclose = (e) => {
      if (myId !== connectionId) return  // 旧连接的回调，忽略
      connected.value = false

      if (!manualClose && e.code !== 1000 && reconnectAttempts < 5) {
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000)
        reconnectTimer = setTimeout(() => {
          reconnectAttempts++
          toast.warning(`连接断开，正在重连 (${reconnectAttempts}/5)...`)
          connect()
        }, delay)
      }
    }

    ws.value.onerror = () => {}

    ws.value.onmessage = (e) => {
      if (myId !== connectionId) return
      if (onMessage.value) {
        try {
          onMessage.value(JSON.parse(e.data))
        } catch (err) {
          console.error('WebSocket message parse error:', err)
        }
      }
    }
  }

  function send(data) {
    if (ws.value && connected.value) {
      ws.value.send(JSON.stringify(data))
    }
  }

  function disconnect() {
    manualClose = true
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws.value) ws.value.close(1000)
  }

  onUnmounted(disconnect)

  return { ws, connected, connect, send, disconnect, onMessage }
}
