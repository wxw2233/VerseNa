import { ref, onUnmounted } from 'vue'

export function useWebSocket(url = `ws://${location.host}/ws/chat`) {
  const ws = ref(null)
  const connected = ref(false)
  const onMessage = ref(null)

  function connect() {
    ws.value = new WebSocket(url)
    ws.value.onopen = () => { connected.value = true }
    ws.value.onclose = () => { connected.value = false }
    ws.value.onmessage = (e) => {
      if (onMessage.value) onMessage.value(JSON.parse(e.data))
    }
  }

  function send(data) {
    if (ws.value && connected.value) {
      ws.value.send(JSON.stringify(data))
    }
  }

  function disconnect() {
    if (ws.value) ws.value.close()
  }

  onUnmounted(disconnect)

  return { ws, connected, connect, send, disconnect, onMessage }
}
