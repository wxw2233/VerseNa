<template>
  <div class="chat-view">
    <SessionList />
    <div class="chat-main">
      <div class="bg-layer" :style="bgStyle"></div>
      <div class="chat-header">
        <span class="chat-persona-name">🎭 {{ personaStore.current || "default" }}</span>
      </div>
      <div class="messages" ref="messagesRef">
        <ChatBubble v-for="(msg, i) in store.messages" :key="i" :msg="msg" />
        <div v-if="store.messages.length === 0" class="empty">
          <p>✨ 次元人格 ✨</p>
          <p class="sub">点击「+ 新对话」开始聊天</p>
        </div>
      </div>
      <ChatInput @send="handleSend" />
    </div>

    <!-- Confirm Dialog -->
    <div v-if="confirmDialog.visible" class="confirm-overlay" @click.self="onConfirm(false)">
      <div class="confirm-dialog">
        <div class="confirm-header">⚠️ 操作确认</div>
        <div class="confirm-body">
          <p class="confirm-message">{{ confirmDialog.message }}</p>
          <div v-if="confirmDialog.action" class="confirm-meta">
            <span class="confirm-action">{{ confirmDialog.action }}</span>
            <span v-if="confirmDialog.path" class="confirm-path">{{ confirmDialog.path }}</span>
            <span v-if="confirmDialog.src" class="confirm-path">{{ confirmDialog.src }} → {{ confirmDialog.dst }}</span>
            <span v-if="confirmDialog.file_count !== undefined" class="confirm-count">
              {{ confirmDialog.file_count }} 个文件, {{ confirmDialog.dir_count }} 个目录
            </span>
          </div>
        </div>
        <div class="confirm-actions">
          <button class="btn-confirm-cancel" @click="onConfirm(false)">取消</button>
          <button class="btn-confirm-ok" @click="onConfirm(true)">确认执行</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick, onMounted, watch } from 'vue'
import { useChatStore } from '../stores/chat'
import { useWebSocket } from '../composables/useWebSocket'
import { usePersonaStore } from '../stores/persona'
import { useSessionStore } from '../stores/session'
import { useThemeStore } from '../stores/theme'
import ChatBubble from '../components/ChatBubble.vue'
import ChatInput from '../components/ChatInput.vue'
import SessionList from '../components/SessionList.vue'

const store = useChatStore()
const personaStore = usePersonaStore()
const sessionStore = useSessionStore()
const themeStore = useThemeStore()
const messagesRef = ref(null)
const { connect, send, onMessage, ws } = useWebSocket()

const confirmDialog = reactive({
  visible: false,
  requestId: '',
  message: '',
  action: '',
  path: '',
  src: '',
  dst: '',
  file_count: undefined,
  dir_count: undefined
})

const bgStyle = computed(() => {
  const themeId = themeStore.current
  return {
    backgroundImage: `url(/api/themes/${themeId}/assets/bg.png)`,
    backgroundSize: 'cover',
    backgroundPosition: 'center',
    backgroundRepeat: 'no-repeat',
    opacity: store.bgOpacity ?? 0.3,
  }
})

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

watch(() => store.messages.length, () => scrollToBottom())

onMounted(() => {
  connect()
  scrollToBottom()
  onMessage.value = (msg) => {
    if (msg.type === 'segment') {
      store.appendSegment(msg.segment)
    } else if (msg.type === 'answer') {
      // 旧格式兼容
      store.appendSegment({ type: 'text', content: msg.content })
    } else if (msg.type === 'confirm') {
      // 显示确认对话框
      const data = msg.data || msg
      confirmDialog.requestId = data.request_id || ''
      confirmDialog.message = data.message || '确认执行此操作？'
      confirmDialog.action = data.action || ''
      confirmDialog.path = data.path || ''
      confirmDialog.src = data.src || ''
      confirmDialog.dst = data.dst || ''
      confirmDialog.file_count = data.file_count
      confirmDialog.dir_count = data.dir_count
      confirmDialog.visible = true
    } else if (msg.type === 'done') {
      store.finishStreaming(msg.emoji)
      // 首条消息自动命名
      autoTitleIfNeeded()
    } else if (msg.type === 'error') {
      store.handleError(msg.content || msg.message || '未知错误')
    }
    scrollToBottom()
  }
})

function onConfirm(confirmed) {
  const requestId = confirmDialog.requestId
  confirmDialog.visible = false
  const msg = JSON.stringify({
    type: 'confirm_response',
    request_id: requestId,
    confirmed: confirmed
  })
  // 直接通过 WebSocket 发送，不依赖 connected 状态
  if (ws && ws.value && ws.value.readyState === WebSocket.OPEN) {
    ws.value.send(msg)
  } else {
    send({ type: 'confirm_response', request_id: requestId, confirmed: confirmed })
  }
}

function handleSend(content) {
  store.addUserMessage(content)
  store.isStreaming = true
  scrollToBottom()
  send({
    session_id: sessionStore.currentSessionId,
    content,
    persona: personaStore.current,
    system_prompt: ''
  })
}

let autoTitleDone = false
async function autoTitleIfNeeded() {
  if (autoTitleDone) return
  autoTitleDone = true
  const msgs = store.messages
  if (msgs.length < 2) return
  const userMsg = msgs.find(m => m.role === 'user')
  const assistantMsg = msgs.find(m => m.role === 'assistant')
  if (!userMsg || !assistantMsg) return
  try {
    const sid = sessionStore.currentSessionId
    const resp = await fetch(`/api/sessions/${sid}/auto-title`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ user_message: userMsg.content, assistant_message: assistantMsg.segments?.map(s => s.content || '').join('') || assistantMsg.content || '' })
    })
    const data = await resp.json()
    if (data.name) await sessionStore.fetchSessions()
  } catch {}
}

</script>

<style scoped>
.chat-view {
  display: flex;
  height: calc(100vh - 52px);
}
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
  overflow: hidden;
}
.bg-layer {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  z-index: 0;
  pointer-events: none;
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 1;
}
.chat-header { padding: 8px 16px; border-bottom: 1px solid var(--border); display: flex; align-items: center; position: relative; z-index: 1; }
.chat-header { padding: 6px 16px; border-bottom: 1px solid var(--border); display: flex; justify-content: center; align-items: center; position: relative; z-index: 1; }
.chat-persona-name { font-size: 13px; font-weight: 600; color: var(--primary); letter-spacing: 1px; opacity: 0.8; }
.empty {
  margin: auto;
  text-align: center;
  color: var(--text-secondary);
}
.empty p { font-size: 24px; }
.empty .sub { font-size: 14px; margin-top: 8px; }

/* Confirm Dialog */
.confirm-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.confirm-dialog {
  background: var(--bg-secondary, #1e1e2e);
  border: 1px solid var(--border, #2a2a40);
  border-radius: 14px;
  padding: 24px;
  min-width: 380px;
  max-width: 520px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}
.confirm-header {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 16px;
  color: var(--text-primary, #e8e8f0);
}
.confirm-body {
  margin-bottom: 20px;
}
.confirm-message {
  font-size: 14px;
  color: var(--text-primary, #e8e8f0);
  line-height: 1.6;
  margin-bottom: 12px;
}
.confirm-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 14px;
  background: var(--bg-primary, #0f0f1a);
  border-radius: 8px;
  font-size: 13px;
}
.confirm-action {
  color: var(--primary, #7c5cfc);
  font-weight: 600;
  text-transform: uppercase;
  font-family: monospace;
}
.confirm-path {
  color: var(--text-secondary, #8888aa);
  font-family: monospace;
  word-break: break-all;
}
.confirm-count {
  color: var(--text-secondary, #8888aa);
}
.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
.btn-confirm-cancel {
  padding: 8px 20px;
  border: 1px solid var(--border, #2a2a40);
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary, #8888aa);
  cursor: pointer;
  font-size: 14px;
  transition: border-color 0.15s;
}
.btn-confirm-cancel:hover {
  border-color: var(--primary, #7c5cfc);
}
.btn-confirm-ok {
  padding: 8px 20px;
  border: none;
  border-radius: 8px;
  background: var(--primary, #7c5cfc);
  color: #fff;
  cursor: pointer;
  font-size: 14px;
  transition: opacity 0.15s;
}
.btn-confirm-ok:hover {
  opacity: 0.85;
}
</style>
