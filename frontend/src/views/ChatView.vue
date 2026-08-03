<template>
  <div class="chat-view">
    <!-- 移动端侧边栏切换按钮 -->
    <button
      class="mobile-sidebar-toggle"
      @click="toggleMobileSidebar"
      :aria-label="mobileSidebarOpen ? '关闭会话列表' : '打开会话列表'"
    >
      <PanelLeftClose v-if="mobileSidebarOpen" :size="19" aria-hidden="true" />
      <PanelLeftOpen v-else :size="19" aria-hidden="true" />
    </button>

    <SessionList ref="sessionListRef" :class="{ 'mobile-open': mobileSidebarOpen }" />
    <div class="chat-main">
      <div
        class="messages"
        ref="messagesRef"
        @scroll.passive="handleMessagesScroll"
        @wheel.passive="cancelAutoScroll"
        @touchstart.passive="cancelAutoScroll"
      >
        <div class="message-rail">
          <ChatBubble
            v-for="(msg, i) in store.messages"
            :key="sessionStore.currentSessionId + '_' + i"
            :msg="msg"
            class="msg-item"
            :style="{ animationDelay: Math.min(i * 30, 200) + 'ms' }"
            @retry="handleRetry(i)"
            @edit="(newContent) => handleEdit(i, newContent)"
          />
          <EmptyState
            v-if="store.messages.length === 0"
            title="VerseNa"
            action-text="开始对话"
            @action="handleNewChat"
          />
        </div>
      </div>
      <Transition name="scroll-jump">
        <button
          v-if="!isAtBottom && store.messages.length"
          class="scroll-bottom-btn"
          :class="{ 'has-unread': unreadCount > 0 }"
          :title="unreadCount ? `${unreadCount} 条新消息` : '回到底部'"
          :aria-label="unreadCount ? `${unreadCount} 条新消息，回到底部` : '回到底部'"
          @click="scrollToBottom(true)"
        >
          <ArrowDown :size="17" aria-hidden="true" />
          <span v-if="unreadCount" class="unread-count">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
        </button>
      </Transition>
      <Transition name="connection-state">
        <div
          v-if="connectionStatus !== 'connected' && connectionStatus !== 'idle'"
          class="connection-status"
          :class="connectionStatus"
          role="status"
          aria-live="polite"
        >
          <LoaderCircle
            v-if="connectionStatus === 'connecting' || connectionStatus === 'reconnecting'"
            class="connection-spinner"
            :size="14"
            aria-hidden="true"
          />
          <WifiOff v-else :size="14" aria-hidden="true" />
          <span>{{ connectionLabel }}</span>
          <button
            v-if="connectionStatus === 'disconnected'"
            class="connection-retry-btn"
            @click="reconnect"
            title="重新连接"
            aria-label="重新连接"
          >
            <RefreshCcw :size="13" aria-hidden="true" />
          </button>
        </div>
      </Transition>
      <ChatInput
        @send="handleSend"
        @stop="handleStop"
        :auto-tts="autoTTS"
        :is-streaming="store.isStreaming"
        :is-stopping="store.isStopping"
        :connected="connected"
        @toggle-tts="autoTTS = !autoTTS; localStorage.setItem('auto-tts', autoTTS)"
      />
    </div>

    <!-- Confirm Dialog -->
    <div v-if="confirmDialog.visible" class="confirm-overlay" @click.self="onConfirm(false)">
      <div class="confirm-dialog">
        <div class="confirm-header">
          <TriangleAlert :size="19" aria-hidden="true" />
          <span>操作确认</span>
        </div>
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
import { ArrowDown, LoaderCircle, PanelLeftClose, PanelLeftOpen, RefreshCcw, TriangleAlert, WifiOff } from 'lucide-vue-next'
import { useToast } from '../composables/useToast'
import { useKeyboard } from '../composables/useKeyboard'
import { useChatStore } from '../stores/chat'
import { useWebSocket } from '../composables/useWebSocket'
import { usePersonaStore } from '../stores/persona'
import { useSessionStore } from '../stores/session'
import { useThemeStore } from '../stores/theme'
import { prepareTextForSpeech } from '../utils/ttsText'
import ChatBubble from '../components/ChatBubble.vue'
import ChatInput from '../components/ChatInput.vue'
import SessionList from '../components/SessionList.vue'
import EmptyState from '../components/EmptyState.vue'

const store = useChatStore()
const personaStore = usePersonaStore()
const sessionStore = useSessionStore()
const themeStore = useThemeStore()
const messagesRef = ref(null)
const isAtBottom = ref(true)
const unreadCount = ref(0)
const currentResponseUnread = ref(false)
const isAutoScrolling = ref(false)
let autoScrollTimer = null
const toast = useToast()
const {
  connected,
  status: connectionStatus,
  reconnectAttempts,
  maxReconnectAttempts,
  connect,
  reconnect,
  send,
  sendWithAck,
  onMessage,
} = useWebSocket()

function createId(prefix) {
  if (globalThis.crypto?.randomUUID) return `${prefix}_${globalThis.crypto.randomUUID()}`
  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`
}

function createRequestIds() {
  return {
    client_message_id: createId('msg'),
    generation_id: createId('gen'),
  }
}

function requestFingerprint(content) {
  if (typeof content === 'string') return `text:${content}`
  const reasoning = content?.reasoning_enabled === true ? ':reasoning' : ':standard'
  if (content?.image) return `image:${content.text || ''}:${content.image.dataUrl || content.image.url || ''}${reasoning}`
  if (content?.file) return `file:${content.text || ''}:${content.file.saved_as || content.file.filename || ''}${reasoning}`
  return JSON.stringify(content)
}

let retainedSendRequest = null
let retainedActionRequest = null
let actionPending = false

async function refreshCurrentHistory() {
  const sessionId = sessionStore.currentSessionId
  const response = await fetch(`/api/sessions/${sessionId}/history`)
  if (!response.ok) throw new Error(`历史记录同步失败: HTTP ${response.status}`)
  const history = await response.json()
  if (sessionStore.currentSessionId === sessionId) store.loadHistory(history)
}

const connectionLabel = computed(() => {
  if (connectionStatus.value === 'connecting') return '正在连接'
  if (connectionStatus.value === 'reconnecting') {
    const attempt = Math.max(reconnectAttempts.value, 1)
    return `正在重连 ${attempt}/${maxReconnectAttempts}`
  }
  return '连接已断开'
})

// 移动端侧边栏状态
const mobileSidebarOpen = ref(false)

const toggleMobileSidebar = () => {
  mobileSidebarOpen.value = !mobileSidebarOpen.value
}

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




const BOTTOM_THRESHOLD = 80

function resetUnreadState() {
  unreadCount.value = 0
  currentResponseUnread.value = false
}

function handleMessagesScroll() {
  const el = messagesRef.value
  if (!el) return

  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight <= BOTTOM_THRESHOLD
  if (isAutoScrolling.value && !atBottom) return

  isAtBottom.value = atBottom
  if (atBottom) {
    isAutoScrolling.value = false
    resetUnreadState()
  }
}

function cancelAutoScroll() {
  isAutoScrolling.value = false
  if (autoScrollTimer) clearTimeout(autoScrollTimer)
}

function markCurrentResponseUnread() {
  if (currentResponseUnread.value) return
  unreadCount.value += 1
  currentResponseUnread.value = true
}

function scrollToBottom(smooth = false) {
  isAtBottom.value = true
  resetUnreadState()
  if (autoScrollTimer) clearTimeout(autoScrollTimer)
  isAutoScrolling.value = smooth
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTo({
        top: messagesRef.value.scrollHeight,
        behavior: smooth ? 'smooth' : 'auto',
      })
    }

    if (smooth) {
      autoScrollTimer = setTimeout(() => {
        isAutoScrolling.value = false
        handleMessagesScroll()
      }, 500)
    }
  })
}

watch(() => store.messages.length, (newLen, oldLen) => {
  if (newLen > oldLen && isAtBottom.value) scrollToBottom()
})

// 会话切换后滚动到底部
watch(() => sessionStore.currentSessionId, () => {
  isAtBottom.value = true
  resetUnreadState()
  nextTick(() => scrollToBottom())
})

watch(connectionStatus, (nextStatus, previousStatus) => {
  if (previousStatus !== 'connected' || nextStatus === 'connected' || !store.isStreaming) return
  store.handleError('连接中断，请重新生成', store.activeGenerationId)
  toast.warning('生成因连接中断而停止')
})


// 键盘快捷键
useKeyboard({
  'ctrl+n': () => {
    sessionStore.createSession()
    toast.info('新建对话')
  },
  'ctrl+/': () => {
    mobileSidebarOpen.value = !mobileSidebarOpen.value
  },
  'escape': () => {
    if (confirmDialog.visible) {
      onConfirm(false)
    }
    if (mobileSidebarOpen.value) {
      mobileSidebarOpen.value = false
    }
  }
})

// 新建对话 - 触发 SessionList 的主题包选择对话框
const sessionListRef = ref(null)
const handleNewChat = () => {
  if (sessionListRef.value) {
    sessionListRef.value.handleNew()
  }
}

onMounted(() => {
  connect()
  scrollToBottom()
  onMessage.value = (msg) => {
    const shouldFollowOutput = isAtBottom.value
    const updatesMessageContent = msg.type === 'segment' || msg.type === 'answer' || msg.type === 'error'
    let applied = true

    if (msg.type === 'segment') {
      applied = store.appendSegment(msg.segment, msg.generation_id)
    } else if (msg.type === 'answer') {
      // 旧格式兼容
      applied = store.appendSegment({ type: 'text', content: msg.content }, msg.generation_id)
    } else if (msg.type === 'confirm') {
      if (msg.generation_id && msg.generation_id !== store.activeGenerationId) return
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
      applied = store.finishStreaming(msg.emoji, msg.generation_id)
      if (!applied) return
      // 首条消息自动命名
      autoTitleIfNeeded()
      // 保存展开状态
      saveToolExpanded()
      // 自动 TTS
      if (autoTTS.value) {
        autoSpeakLast()
      }
    } else if (msg.type === 'error') {
      applied = store.handleError(msg.content || msg.message || '未知错误', msg.generation_id)
    }

    if (!applied) return

    if (shouldFollowOutput) {
      scrollToBottom()
    } else if (updatesMessageContent) {
      markCurrentResponseUnread()
    }

    if (msg.type === 'done' || msg.type === 'error') {
      currentResponseUnread.value = false
    }
  }
})

function onConfirm(confirmed) {
  const requestId = confirmDialog.requestId
  const sent = send({
    type: 'confirm_response',
    request_id: requestId,
    confirmed,
  })
  if (!sent) {
    toast.warning('连接不可用，确认结果尚未发送')
    reconnect()
    return
  }
  confirmDialog.visible = false
}

function handleStop() {
  if (store.isStopping) return
  const generationId = store.activeGenerationId
  if (!send({ type: 'stop', generation_id: generationId })) {
    toast.warning('连接已中断，生成状态已在本地停止')
    store.handleError('连接中断，生成已停止', generationId)
    reconnect()
    return
  }
  store.requestStop(generationId)
}

async function handleSend(content, acknowledge = () => {}) {
  const fingerprint = requestFingerprint(content)
  const requestIds = retainedSendRequest?.fingerprint === fingerprint
    ? retainedSendRequest.ids
    : createRequestIds()
  let payload
  const reasoningEnabled = typeof content === 'object' && content?.reasoning_enabled === true
  if (typeof content === 'object' && content.image) {
    const msgContent = content.text
      ? content.text + '\n[图片已发送]'
      : '[图片已发送]'
    payload = {
      session_id: sessionStore.currentSessionId,
      content: msgContent,
      persona: personaStore.current,
      system_prompt: '',
      image_url: content.image.dataUrl,
      reasoning_enabled: reasoningEnabled,
      ...requestIds,
    }
  } else if (typeof content === 'object' && content.file) {
    const msgContent = (content.text ? content.text + '\n' : '') +
      `[文件: ${content.file.filename}]\n${content.file.full_text || content.file.text_preview || ''}`
    payload = {
      session_id: sessionStore.currentSessionId,
      content: msgContent,
      persona: personaStore.current,
      system_prompt: '',
      reasoning_enabled: reasoningEnabled,
      ...requestIds,
    }
  } else {
    const messageText = typeof content === 'object' ? content.text : content
    payload = {
      session_id: sessionStore.currentSessionId,
      content: messageText,
      persona: personaStore.current,
      system_prompt: '',
      reasoning_enabled: reasoningEnabled,
      ...requestIds,
    }
  }

  try {
    const accepted = await sendWithAck(payload)
    const generationId = accepted.generation_id || requestIds.generation_id
    const clientMessageId = accepted.client_message_id || requestIds.client_message_id

    retainedSendRequest = null
    if (accepted.duplicate && accepted.status !== 'running') {
      await refreshCurrentHistory()
      acknowledge(true)
      toast.info('消息已由服务端处理，会话已同步')
      return
    }

    if (typeof content === 'object' && content.image) {
      store.messages.push({
        role: 'user',
        content: content.text || '',
        image: content.image,
        streaming: false,
        clientMessageId,
        reasoningEnabled,
      })
    } else if (typeof content === 'object' && content.file) {
      store.messages.push({
        role: 'user',
        content: content.text || '',
        file: content.file,
        streaming: false,
        clientMessageId,
        reasoningEnabled,
      })
    } else {
      const messageText = typeof content === 'object' ? content.text : content
      store.addUserMessage(messageText, null, clientMessageId, reasoningEnabled)
    }

    store.startStreaming(generationId, reasoningEnabled)
    scrollToBottom()
    acknowledge(true)
  } catch (error) {
    retainedSendRequest = { fingerprint, ids: requestIds }
    acknowledge(false)
    toast.warning(error.message || '发送失败，消息已保留')
    if (!connected.value) reconnect()
  }
}

async function handleRetry(msgIndex) {
  if (actionPending) return
  actionPending = true
  const requestKey = `resend:${sessionStore.currentSessionId}:${store.messages[msgIndex]?.generationId || msgIndex}`
  const requestIds = retainedActionRequest?.key === requestKey
    ? retainedActionRequest.ids
    : createRequestIds()
  try {
    const reasoningEnabled = store.messages[msgIndex]?.reasoningEnabled === true
    const accepted = await sendWithAck({
      type: 'resend',
      session_id: sessionStore.currentSessionId,
      persona: personaStore.current,
      reasoning_enabled: reasoningEnabled,
      ...requestIds,
    })
    retainedActionRequest = null
    if (accepted.duplicate && accepted.status !== 'running') {
      await refreshCurrentHistory()
      toast.info('重新生成请求已由服务端处理，会话已同步')
      return
    }
    store.deleteFrom(msgIndex)
    store.startStreaming(accepted.generation_id || requestIds.generation_id, reasoningEnabled)
  } catch (error) {
    retainedActionRequest = { key: requestKey, ids: requestIds }
    toast.warning(error.message || '重新生成请求未发送')
    if (!connected.value) reconnect()
  } finally {
    actionPending = false
  }
}

async function handleEdit(msgIndex, newContent) {
  if (actionPending) return
  actionPending = true
  const msg = store.messages[msgIndex]
  const requestKey = `edit:${sessionStore.currentSessionId}:${msg?.dbId || msgIndex}:${newContent}`
  const requestIds = retainedActionRequest?.key === requestKey
    ? retainedActionRequest.ids
    : createRequestIds()
  try {
    const reasoningEnabled = msg?.reasoningEnabled === true
    const accepted = await sendWithAck({
      type: 'edit',
      session_id: sessionStore.currentSessionId,
      persona: personaStore.current,
      message_id: msg.dbId,
      content: newContent,
      reasoning_enabled: reasoningEnabled,
      ...requestIds,
    })
    retainedActionRequest = null
    if (accepted.duplicate && accepted.status !== 'running') {
      await refreshCurrentHistory()
      toast.info('编辑请求已由服务端处理，会话已同步')
      return
    }
    store.deleteFrom(msgIndex + 1)
    msg.content = newContent
    msg.clientMessageId = accepted.client_message_id || requestIds.client_message_id
    store.startStreaming(accepted.generation_id || requestIds.generation_id, reasoningEnabled)
  } catch (error) {
    retainedActionRequest = { key: requestKey, ids: requestIds }
    toast.warning(error.message || '编辑请求未发送，原消息保持不变')
    if (!connected.value) reconnect()
  } finally {
    actionPending = false
  }
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
  text = prepareTextForSpeech(text)
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
      body: JSON.stringify({
        user_message: userMsg.content,
        assistant_message: assistantMsg.segments
          ?.filter(segment => segment.type === 'text')
          .map(segment => segment.content || '')
          .join('') || assistantMsg.content || '',
      })
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
  height: 100vh;
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
  overflow-x: hidden;
  width: 100%;
  padding: 16px 0;
  position: relative;
  z-index: 1;
}
.message-rail {
  width: min(100%, var(--chat-content-width));
  margin-inline: auto;
  min-height: 100%;
  padding: 0 var(--chat-gutter);
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

.scroll-bottom-btn {
  position: absolute;
  right: max(var(--chat-gutter), calc((100% - var(--chat-content-width)) / 2 + var(--chat-gutter)));
  bottom: 86px;
  z-index: 10;
  width: 38px;
  height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0;
  color: var(--text-primary);
  background: var(--surface-modal);
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 50%;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.30);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  cursor: pointer;
  transition: transform var(--motion-fast) var(--ease-standard), background var(--motion-fast) var(--ease-standard), border-color var(--motion-fast) var(--ease-standard);
}
.scroll-bottom-btn.has-unread {
  width: auto;
  min-width: 38px;
  padding: 0 11px;
  border-radius: 19px;
  border-color: color-mix(in srgb, var(--primary) 55%, transparent);
}
.scroll-bottom-btn:hover {
  transform: translateY(-2px);
  background: color-mix(in srgb, var(--surface-modal) 88%, var(--primary));
  border-color: var(--primary);
}
.unread-count {
  min-width: 12px;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}
.scroll-jump-enter-active,
.scroll-jump-leave-active {
  transition: opacity var(--motion-fast) var(--ease-standard), transform var(--motion-fast) var(--ease-emphasized);
}
.scroll-jump-enter-from,
.scroll-jump-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

.connection-status {
  position: absolute;
  left: max(var(--chat-gutter), calc((100% - var(--chat-content-width)) / 2 + var(--chat-gutter)));
  bottom: 86px;
  z-index: 10;
  min-height: 32px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 0 10px;
  color: var(--text-secondary);
  background: var(--surface-modal);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.26);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  font-size: 12px;
}
.connection-status.disconnected {
  color: #fca5a5;
  border-color: rgba(248, 113, 113, 0.28);
}
.connection-retry-btn {
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-right: -6px;
  padding: 0;
  color: currentColor;
  background: transparent;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  transition: color var(--motion-fast) var(--ease-standard), background var(--motion-fast) var(--ease-standard), transform var(--motion-fast) var(--ease-standard);
}
.connection-retry-btn:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.08);
  transform: rotate(30deg);
}
.connection-spinner {
  animation: connection-spin 800ms linear infinite;
}
.connection-state-enter-active,
.connection-state-leave-active {
  transition: opacity var(--motion-fast) var(--ease-standard), transform var(--motion-fast) var(--ease-emphasized);
}
.connection-state-enter-from,
.connection-state-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
@keyframes connection-spin {
  to { transform: rotate(360deg); }
}

/* 消息淡入动画 */
.msg-item {
  animation: msg-appear var(--motion-base) var(--ease-emphasized) backwards;
}
@keyframes msg-appear {
  from {
    opacity: 0;
    transform: translateY(6px);
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
  display: flex;
  align-items: center;
  gap: 8px;
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


/* 移动端侧边栏切换按钮 */
.mobile-sidebar-toggle {
  display: none;
  position: fixed;
  top: 12px;
  left: 12px;
  z-index: 200;
  width: var(--control-height);
  height: var(--control-height);
  border-radius: 10px;
  background: var(--primary);
  color: white;
  border: none;
  cursor: pointer;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(124, 92, 252, 0.4);
  transition: transform var(--motion-fast) var(--ease-standard), box-shadow var(--motion-fast) var(--ease-standard), filter var(--motion-fast) var(--ease-standard);
}

.mobile-sidebar-toggle:hover {
  transform: scale(1.05);
  box-shadow: 0 6px 16px rgba(124, 92, 252, 0.5);
}

/* 移动端响应式 */
@media (max-width: 767px) {
  .chat-view {
    flex-direction: column;
    position: relative;
  }

  .mobile-sidebar-toggle {
    display: flex;
  }

  .chat-main {
    width: 100%;
    flex: 1;
    min-height: 0;
  }

  .messages {
    padding: 12px 0;
    padding-bottom: 100px;
  }

  .message-rail {
    padding: 0 12px;
  }

  .scroll-bottom-btn {
    right: 16px;
    bottom: 92px;
  }

  .connection-status {
    left: 16px;
    bottom: 92px;
  }

  .confirm-dialog {
    min-width: auto;
    max-width: none;
    width: calc(100% - 32px);
    margin: 16px;
  }
}
</style>
