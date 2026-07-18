<template>
  <div class="chat-view">
    <SessionList />
    <div class="chat-main">

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
      // 保存展开状态
      saveToolExpanded()
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


// 工具展开状态持久化（localStorage）
function saveToolExpanded() {
  const key = 'tool_expanded_' + sessionStore.currentSessionId
  const expanded = {}
  for (const msg of store.messages) {
    if (msg.expandedTools) {
      Object.assign(expanded, msg.expandedTools)
    }
  }
  if (Object.keys(expanded).length > 0) {
    localStorage.setItem(key, JSON.stringify(expanded))
  }
}

function loadToolExpanded() {
  const key = 'tool_expanded_' + sessionStore.currentSessionId
  try {
    const saved = localStorage.getItem(key)
    if (saved) {
      const expanded = JSON.parse(saved)
      // 重新映射到当前消息的 segments
      for (const msg of store.messages) {
        if (msg.segments) {
          msg.expandedTools = msg.expandedTools || {}
          for (const seg of msg.segments) {
            if (seg.type === 'tool' && expanded[seg.tool_call_id]) {
              msg.expandedTools[seg.tool_call_id] = true
            }
          }
        }
      }
    }
  } catch {}
}

// 加载后恢复展开状态
setTimeout(loadToolExpanded, 100)

</script>

<style scoped>
/* L2: Chat view — 8px blur, 0.62 opacity */
.chat-view {
  display: flex;
  height: calc(100vh - 52px);
  /* transparent - bg shows through */
}
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
  overflow: hidden;
  /* transparent */
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 1;
  /* transparent — inherits from chat-main L2 */
}
/* Minimal subtle header */
.chat-header {
  padding: 10px 16px 8px;
  display: flex;
  justify-content: center;
  align-items: center;
  position: relative;
  z-index: 1;
}
.chat-persona-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  letter-spacing: 2px;
  opacity: 0.5;
}
.empty {
  margin: auto;
  text-align: center;
  color: var(--text-secondary);
}
.empty p { text-shadow: 0 0 6px rgba(0,0,0,0.4); font-size: 24px; }
.empty .sub { font-size: 14px; margin-top: 8px; }

/* Confirm Dialog — glass L3 style */
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
  background: var(--panel-l3);
   

  box-shadow: var(--border-subtle), var(--glow-inner), 0 8px 32px rgba(0, 0, 0, 0.4);
  border-radius: var(--radius);
  padding: 24px;
  min-width: 380px;
  max-width: 520px;
}
.confirm-header {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 16px;
  color: var(--text-primary);
}
.confirm-body {
  margin-bottom: 20px;
}
.confirm-message {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.6;
  margin-bottom: 12px;
}
.confirm-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 14px;
  background: var(--panel-l4);
  border-radius: 8px;
  box-shadow: var(--border-subtle);
  font-size: 13px;
}
.confirm-action {
  color: var(--primary);
  font-weight: 600;
  text-transform: uppercase;
  font-family: monospace;
}
.confirm-path {
  color: var(--text-secondary);
  font-family: monospace;
  word-break: break-all;
}
.confirm-count {
  color: var(--text-secondary);
}
.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
/* L4 buttons for confirm dialog */
.btn-confirm-cancel {
  padding: 8px 20px;
  box-shadow: var(--border-subtle);
  border-radius: var(--radius-sm);
  background: var(--panel-l4);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 14px;
  border: none;
  transition: filter 0.2s, transform 0.2s, box-shadow 0.2s;
}
.btn-confirm-cancel:hover {
  box-shadow: 0 0 0 1px var(--primary);
  filter: brightness(1.08);
  transform: translateY(-1px);
}
.btn-confirm-ok {
  padding: 8px 20px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: #fff;
  cursor: pointer;
  font-size: 14px;
  transition: filter 0.2s, transform 0.2s;
}
.btn-confirm-ok:hover {
  filter: brightness(1.08);
  transform: translateY(-1px);
}
</style>
