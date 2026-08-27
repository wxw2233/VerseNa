import { ref, onMounted, onUnmounted } from 'vue'
import { useToast } from './useToast.js'
import { notifyAuthenticationRequired } from '../utils/auth.js'

const MAX_RECONNECT_ATTEMPTS = 5
const ACK_TIMEOUT_MS = 10000
const HEARTBEAT_INTERVAL_MS = 15000
const HEARTBEAT_TIMEOUT_MS = 35000
const CONNECTION_TIMEOUT_MS = 10000

function defaultWebSocketUrl() {
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${protocol}://${location.host}/ws/chat`
}

export function useWebSocket(url = defaultWebSocketUrl()) {
  const ws = ref(null)
  const connected = ref(false)
  const status = ref('idle')
  const reconnectAttempts = ref(0)
  const reconnectVersion = ref(0)
  const onMessage = ref(null)
  const toast = useToast()
  let reconnectTimer = null
  let connectionId = 0
  let manualClose = false
  let heartbeatTimer = null
  let connectionTimer = null
  let lastPongAt = 0
  const pendingAcknowledgements = new Map()

  function rejectPendingAcknowledgements(message) {
    for (const pending of pendingAcknowledgements.values()) {
      clearTimeout(pending.timer)
      pending.reject(new Error(message))
    }
    pendingAcknowledgements.clear()
  }

  function clearReconnectTimer() {
    if (!reconnectTimer) return
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }

  function stopHeartbeat() {
    if (heartbeatTimer) clearInterval(heartbeatTimer)
    heartbeatTimer = null
    lastPongAt = 0
  }

  function clearConnectionTimer() {
    if (!connectionTimer) return
    clearTimeout(connectionTimer)
    connectionTimer = null
  }

  function startHeartbeat(socket, id) {
    stopHeartbeat()
    lastPongAt = Date.now()
    heartbeatTimer = setInterval(() => {
      if (id !== connectionId || socket.readyState !== WebSocket.OPEN) return
      if (Date.now() - lastPongAt > HEARTBEAT_TIMEOUT_MS) {
        connected.value = false
        status.value = 'reconnecting'
        try { socket.close(4000, 'Heartbeat timeout') } catch {}
        return
      }
      try {
        socket.send(JSON.stringify({ type: 'ping' }))
      } catch {
        connected.value = false
        status.value = 'reconnecting'
        try { socket.close(4000, 'Heartbeat send failed') } catch {}
      }
    }, HEARTBEAT_INTERVAL_MS)
  }

  function scheduleReconnect() {
    if (manualClose) return

    if (reconnectAttempts.value >= MAX_RECONNECT_ATTEMPTS) {
      status.value = 'disconnected'
      toast.error('连接已断开，请手动重试')
      return
    }

    status.value = 'reconnecting'
    const delay = Math.min(1000 * (2 ** reconnectAttempts.value), 10000)
    clearReconnectTimer()
    reconnectTimer = setTimeout(() => {
      reconnectAttempts.value += 1
      connect(true)
    }, delay)
  }

  function connect(isReconnect = false) {
    if (ws.value && ws.value.readyState <= WebSocket.OPEN) return

    manualClose = false
    clearReconnectTimer()
    status.value = isReconnect || reconnectAttempts.value > 0 ? 'reconnecting' : 'connecting'
    const myId = ++connectionId
    const socket = new WebSocket(url)
    ws.value = socket
    connectionTimer = setTimeout(() => {
      if (myId !== connectionId || socket.readyState !== WebSocket.CONNECTING) return
      status.value = 'reconnecting'
      try { socket.close(4000, 'Connection timeout') } catch {}
    }, CONNECTION_TIMEOUT_MS)

    socket.onopen = () => {
      if (myId !== connectionId) return
      clearConnectionTimer()
      const recovered = reconnectAttempts.value > 0
      connected.value = true
      status.value = 'connected'
      reconnectAttempts.value = 0
      clearReconnectTimer()
      startHeartbeat(socket, myId)
      if (recovered) {
        reconnectVersion.value += 1
        toast.success('连接已恢复')
      }
    }

    socket.onclose = (event) => {
      if (myId !== connectionId) return
      clearConnectionTimer()
      connected.value = false
      ws.value = null
      stopHeartbeat()
      rejectPendingAcknowledgements('连接已中断，服务端未确认消息')

      if (event.code === 4401) {
        manualClose = true
        status.value = 'unauthorized'
        notifyAuthenticationRequired()
        return
      }

      if (manualClose) {
        status.value = 'disconnected'
        return
      }

      scheduleReconnect()
    }

    socket.onerror = () => {
      if (myId !== connectionId) return
      connected.value = false
      if (!manualClose) {
        status.value = 'reconnecting'
        scheduleReconnect()
      }
    }

    socket.onmessage = (event) => {
      if (myId !== connectionId) return
      try {
        const message = JSON.parse(event.data)
        if (message.type === 'pong') {
          lastPongAt = Date.now()
          return
        }
        if (message.type === 'auth_required') {
          manualClose = true
          status.value = 'unauthorized'
          notifyAuthenticationRequired()
          socket.close(4401)
          return
        }
        if (message.type === 'accepted' && message.client_message_id) {
          const pending = pendingAcknowledgements.get(message.client_message_id)
          if (!pending) return
          clearTimeout(pending.timer)
          pendingAcknowledgements.delete(message.client_message_id)
          if (message.accepted === false) {
            pending.reject(new Error(message.error || '服务端拒绝了消息'))
          } else {
            pending.resolve(message)
          }
          return
        }
        if (onMessage.value) onMessage.value(message)
      } catch (err) {
        console.error('WebSocket message parse error:', err)
      }
    }
  }

  function send(data) {
    const socket = ws.value
    if (!socket || socket.readyState !== WebSocket.OPEN) return false

    try {
      socket.send(JSON.stringify(data))
      return true
    } catch (err) {
      console.error('WebSocket send error:', err)
      return false
    }
  }

  function sendWithAck(data, timeoutMs = ACK_TIMEOUT_MS) {
    const clientMessageId = data?.client_message_id
    if (!clientMessageId) return Promise.reject(new Error('消息缺少 client_message_id'))

    const existing = pendingAcknowledgements.get(clientMessageId)
    if (existing) return existing.promise

    let resolvePromise
    let rejectPromise
    const promise = new Promise((resolve, reject) => {
      resolvePromise = resolve
      rejectPromise = reject
    })
    const timer = setTimeout(() => {
      pendingAcknowledgements.delete(clientMessageId)
      rejectPromise(new Error('服务端确认超时，消息已保留'))
    }, timeoutMs)

    pendingAcknowledgements.set(clientMessageId, {
      promise,
      resolve: resolvePromise,
      reject: rejectPromise,
      timer,
    })

    if (!send(data)) {
      clearTimeout(timer)
      pendingAcknowledgements.delete(clientMessageId)
      rejectPromise(new Error('连接不可用，消息已保留'))
    }
    return promise
  }

  function reconnect() {
    manualClose = false
    clearReconnectTimer()
    reconnectAttempts.value = 0
    connected.value = false
    rejectPendingAcknowledgements('正在重新连接，服务端未确认消息')

    const socket = ws.value
    ws.value = null
    connectionId += 1
    if (socket && socket.readyState < WebSocket.CLOSING) socket.close()
    connect()
  }

  function disconnect() {
    manualClose = true
    clearReconnectTimer()
    stopHeartbeat()
    clearConnectionTimer()
    connected.value = false
    status.value = 'disconnected'
    rejectPendingAcknowledgements('连接已关闭，服务端未确认消息')
    connectionId += 1

    const socket = ws.value
    ws.value = null
    if (socket && socket.readyState < WebSocket.CLOSING) socket.close(1000)
  }

  function handleOnline() {
    if (!connected.value) reconnect()
  }

  onMounted(() => window.addEventListener('online', handleOnline))
  onUnmounted(() => {
    window.removeEventListener('online', handleOnline)
    disconnect()
  })

  return {
    ws,
    connected,
    status,
    reconnectAttempts,
    reconnectVersion,
    maxReconnectAttempts: MAX_RECONNECT_ATTEMPTS,
    connect,
    reconnect,
    send,
    sendWithAck,
    disconnect,
    onMessage,
  }
}
