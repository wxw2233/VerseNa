<template>
  <div class="chat-view">
    <SessionList />
    <div class="chat-main">
      <div class="messages" ref="messagesRef">
        <ChatBubble
          v-for="(msg, i) in store.messages"
          :key="sessionStore.currentSessionId + '_' + i"
          :msg="msg"
          class="msg-item"
          :style="{ animationDelay: Math.min(i * 30, 200) + 'ms' }"
          @retry="handleRetry(i)"
          @edit="(newContent) => handleEdit(i, newContent)"
        />
        <div v-if="store.messages.length === 0" class="empty">
          <p>✨ VerseNa ✨</p>
          <p class="sub">点击「+ 新对话」开始聊天</p>
        </div>
      </div>
      <ChatInput
        @send="handleSend"
        @stop="handleStop"
        :auto-tts="autoTTS"
        :is-streaming="store.isStreaming"
        @toggle-tts="autoTTS = !autoTTS; localStorage.setItem('auto-tts', autoTTS)"
      />
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
import { useToast } from '../composables/useToast'
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
const toast = useToast()
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

// 自动 TTS 开关
const autoTTS = ref(localStorage.getItem('auto-tts') === 'true')
let ttsAudio = null




function scrollToBottom(smooth = false) {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTo({
        top: messagesRef.value.scrollHeight,
        behavior: smooth ? 'smooth' : 'instant',
      })
    }
  })
}

watch(() => store.messages.length, (newLen, oldLen) => {
  // 只在消息增加时滚动（不清空时），避免 Transition 期间误触发
  if (newLen > oldLen) scrollToBottom()
})

// 会话切换后滚动到底部
watch(() => sessionStore.currentSessionId, () => {
  nextTick(() => scrollToBottom())
})

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
      // 自动 TTS
      if (autoTTS.value) {
        autoSpeakLast()
      }
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

function handleStop() {
  send({ type: 'stop' })
  store.isStreaming = false
}

function handleSend(content) {
  if (typeof content === 'object' && content.image) {
    store.messages.push({
      role: 'user',
      content: content.text || '',
      image: content.image,
      streaming: false,
    })
    store.isStreaming = true
    scrollToBottom()
    const msgContent = content.text
      ? content.text + '\n[图片已发送]'
      : '[图片已发送]'
    send({
      session_id: sessionStore.currentSessionId,
      content: msgContent,
      persona: personaStore.current,
      system_prompt: '',
      image_url: content.image.dataUrl,
    })
  } else if (typeof content === 'object' && content.file) {
    store.messages.push({
      role: 'user',
      content: content.text || '',
      file: content.file,
      streaming: false,
    })
    store.isStreaming = true
    scrollToBottom()
    const msgContent = (content.text ? content.text + '\n' : '') +
      `[文件: ${content.file.filename}]\n${content.file.full_text || content.file.text_preview || ''}`
    send({
      session_id: sessionStore.currentSessionId,
      content: msgContent,
      persona: personaStore.current,
      system_prompt: '',
    })
  } else {
    store.addUserMessage(content)
    store.isStreaming = true
    scrollToBottom()
    send({
      session_id: sessionStore.currentSessionId,
      content,
      persona: personaStore.current,
      system_prompt: '',
    })
  }
}

function handleRetry(msgIndex) {
  // 删除该消息及之后的所有消息
  store.deleteFrom(msgIndex)
  store.isStreaming = true
  send({
    type: 'resend',
    session_id: sessionStore.currentSessionId,
    persona: personaStore.current,
  })
}

function handleEdit(msgIndex, newContent) {
  const msg = store.messages[msgIndex]
  // 删除该消息及之后的所有消息
  store.deleteFrom(msgIndex + 1)
  // 更新消息内容
  msg.content = newContent
  store.isStreaming = true
  send({
    type: 'edit',
    session_id: sessionStore.currentSessionId,
    persona: personaStore.current,
    message_id: msg.dbId,
    content: newContent,
  })
}

function stripActions(text) {
  // 过滤掉动作描述，只保留对话内容
  return text
    .replace(/\*[^*]+\*/g, '')           // *动作*
    .replace(/（[^）]+）/g, '')            // （动作）
    .replace(/\([^)]+\)/g, '')           // (动作)
    .replace(/【[^】]+】/g, '')            // 【动作】
    .replace(/「[^」]*?(?:笑|叹|摇头|点头|眨眼|耸肩|轻声|低声|小声|大喊|尖叫|哭|叹气|沉默|沉默了|顿了顿|想了想|歪头|托腮|摊手|耸肩|鞠躬|行礼|跪|坐|站|走|跑|跳|飞|转|看|望|盯|瞪|闭|睁|摸|碰|推|拉|打|踢|拍|挥|举|放|拿|递|接|抱|握|靠|躺|蹲|趴)[^」]*?」/g, '')
    .replace(/\n{2,}/g, '\n')
    .trim()
}

async function autoSpeakLast() {
  const msgs = store.messages
  const last = msgs[msgs.length - 1]
  if (!last || last.role !== 'assistant') return
  let text = ''
  if (last.segments) {
    text = last.segments.filter(s => s.type === 'text').map(s => s.content).join('')
  } else {
    text = last.content || ''
  }
  text = text.replace(/<[^>]+>/g, '')
  text = stripActions(text)
  if (!text || text.length < 2) return

  try {
    const session = sessionStore.sessions.find(s => s.id === sessionStore.currentSessionId)
    // 优先用会话关联的主题包，否则用当前主题
    const packId = session?.theme_pack_id || themeStore.current || ''
    const resp = await fetch('/api/tts/speak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text.slice(0, 2000), pack_id: packId })
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      toast.warning(err.detail || '语音合成失败，请检查 TTS 配置')
      return
    }
    const blob = await resp.blob()
    if (blob.size === 0) {
      toast.warning('TTS 返回空音频')
      return
    }
    const url = URL.createObjectURL(blob)
    if (ttsAudio) { ttsAudio.pause(); ttsAudio = null }
    ttsAudio = new Audio(url)
    ttsAudio.onended = () => { URL.revokeObjectURL(url) }
    ttsAudio.onerror = (e) => {
      URL.revokeObjectURL(url)
      toast.warning('音频播放失败')
    }
    try {
      await ttsAudio.play()
    } catch (e) {
      toast.warning('浏览器阻止了自动播放，请先点击页面任意位置后再试')
    }
  } catch (e) {
    toast.error('TTS 请求失败: ' + e.message)
  }
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
}

/* 消息淡入动画 */
.msg-item {
  animation: msg-appear 0.25s ease both;
}
@keyframes msg-appear {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
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
