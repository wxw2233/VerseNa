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
      <button
        class="workspace-toggle"
        :class="{ active: workspacePanelOpen }"
        @click="workspacePanelOpen = !workspacePanelOpen"
        title="工作目录"
        :aria-label="workspacePanelOpen ? '关闭工作目录' : '打开工作目录'"
        :aria-expanded="workspacePanelOpen"
      >
        <FolderCog :size="18" aria-hidden="true" />
      </button>
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
            :choice-resolved="isChoiceResolved(i)"
            class="msg-item"
            :style="{ animationDelay: Math.min(i * 30, 200) + 'ms' }"
            @retry="handleRetry(i)"
            @edit="(newContent) => handleEdit(i, newContent)"
            @choose="payload => handleChoice(i, payload)"
          @stop-subagent="handleStopSubagent"
          @stop-plan="handleStop"
          />
          <EmptyState
            v-if="store.messages.length === 0"
            title="VerseNa"
          />
        </div>
      </div>
      <Transition name="scroll-jump">
        <button
          v-if="!isAtBottom && store.messages.length"
          class="scroll-bottom-btn"
          :class="{
            'has-unread': unreadCount > 0,
            'above-active-skill': activeSkill?.active,
          }"
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
      <Transition name="context-compaction">
        <div
          v-if="contextCompaction.visible"
          class="context-compaction-status"
          :class="contextCompaction.phase"
          role="status"
          aria-live="polite"
        >
          <LoaderCircle v-if="contextCompaction.phase === 'start'" class="context-compaction-spinner" :size="14" aria-hidden="true" />
          <Check v-else-if="contextCompaction.phase === 'done'" :size="14" aria-hidden="true" />
          <TriangleAlert v-else :size="14" aria-hidden="true" />
          <span>{{ contextCompaction.message }}</span>
          <span v-if="contextCompaction.phase === 'start'" class="context-compaction-dots" aria-hidden="true">...</span>
        </div>
      </Transition>
      <ChatInput
        @send="handleSend"
        @stop="handleStop"
        :auto-tts="autoTTS"
        :is-streaming="store.isStreaming"
        :is-stopping="store.isStopping"
        :connected="connected"
        :approval-mode="toolSettings.approval_mode"
        :host-execution-enabled="toolSettings.host_execution_enabled"
        :active-skill="activeSkill"
        @update:approval-mode="updateApprovalMode"
        @update:host-execution-enabled="updateHostExecution"
        @clear-active-skill="clearActiveSkill"
        @toggle-tts="autoTTS = !autoTTS; localStorage.setItem('auto-tts', autoTTS)"
      />
    </div>

    <Transition name="workspace-panel">
      <ToolWorkspacePanel
        v-if="workspacePanelOpen"
        :settings="toolSettings"
        :saving="toolSettingsSaving"
        @close="workspacePanelOpen = false"
        @save-workspace="saveToolWorkspace"
        @reset-workspace="saveToolWorkspace('')"
      />
    </Transition>

    <!-- Confirm Dialog -->
    <div v-if="confirmDialog.visible" class="confirm-overlay" @click.self="onConfirm(false)">
      <div class="confirm-dialog">
        <div class="confirm-header">
          <TriangleAlert :size="19" aria-hidden="true" />
          <span>操作确认</span>
        </div>
        <div class="confirm-body">
          <p class="confirm-message">{{ confirmDialog.message }}</p>
          <p v-if="confirmDialog.securityWarning" class="confirm-warning">
            {{ confirmDialog.securityWarning }}
          </p>
          <div v-if="confirmDialog.action" class="confirm-meta">
            <span class="confirm-action">{{ confirmDialog.action }}</span>
            <span v-if="confirmDialog.path" class="confirm-path">{{ confirmDialog.path }}</span>
            <span v-if="confirmDialog.src" class="confirm-path">{{ confirmDialog.src }} → {{ confirmDialog.dst }}</span>
            <span v-if="confirmDialog.file_count !== undefined" class="confirm-count">
              {{ confirmDialog.file_count }} 个文件, {{ confirmDialog.dir_count }} 个目录
            </span>
            <pre v-if="confirmDialog.code" class="confirm-code">{{ confirmDialog.code }}</pre>
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
import { ref, reactive, computed, nextTick, onBeforeUnmount, onMounted, watch } from 'vue'
import { ArrowDown, Check, FolderCog, LoaderCircle, PanelLeftClose, PanelLeftOpen, RefreshCcw, TriangleAlert, WifiOff } from 'lucide-vue-next'
import { useToast } from '../composables/useToast'
import { useKeyboard } from '../composables/useKeyboard'
import { useChatStore } from '../stores/chat'
import { useWebSocket } from '../composables/useWebSocket'
import { usePersonaStore } from '../stores/persona'
import { useSessionStore } from '../stores/session'
import { useThemeStore } from '../stores/theme'
import { cancelBrowserSpeech, speakWithBrowser } from '../utils/browserSpeech'
import { prepareTextForSpeech } from '../utils/ttsText'
import { detectAgentPetState, setDesktopPetState } from '../utils/pet'
import { finalAnswerText } from '../utils/agentTimeline'
import ChatBubble from '../components/ChatBubble.vue'
import ChatInput from '../components/ChatInput.vue'
import SessionList from '../components/SessionList.vue'
import EmptyState from '../components/EmptyState.vue'
import ToolWorkspacePanel from '../components/ToolWorkspacePanel.vue'

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
const workspacePanelOpen = ref(false)
const contextCompaction = reactive({
  visible: false,
  phase: 'start',
  mode: 'automatic',
  message: '正在整理上下文',
})
let contextCompactionTimer = null
const toolSettingsSaving = ref(false)
const toolSettings = reactive({
  tool_workspace: '',
  effective_workspace: '',
  approval_mode: 'ask',
  host_execution_enabled: false,
  is_default: true,
})
const activeSkill = ref({ active: false, command: '', arguments: '' })
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
  dir_count: undefined,
  code: '',
  securityWarning: '',
})

// 自动 TTS 开关
const autoTTS = ref(localStorage.getItem('auto-tts') === 'true')
let ttsAudio = null
let ttsAudioUrl = ''
let autoBrowserUtterance = null
let autoSpeechRun = 0
let petDoneTimer = null

const petState = computed(() => {
  return detectAgentPetState({
    isStopping: store.isStopping,
    isStreaming: store.isStreaming,
    messages: store.messages,
  })
})

function syncPetState() {
  setDesktopPetState(petState.value, themeStore.current)
}

watch([petState, () => themeStore.current], syncPetState, { immediate: true })




const BOTTOM_THRESHOLD = 12

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

// 消息内容在同一个流式消息内持续变化，等待 DOM 完成更新后再保持底部锁定。
watch(() => store.messages, () => {
  if (isAtBottom.value) scrollToBottom()
}, { deep: true, flush: 'post' })

// 会话切换后滚动到底部
watch(() => sessionStore.currentSessionId, () => {
  isAtBottom.value = true
  resetUnreadState()
  nextTick(() => scrollToBottom())
  loadToolSettings()
  loadSkillState()
}, { immediate: true })

async function loadSkillState() {
  const sessionId = sessionStore.currentSessionId
  try {
    const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/skill-state`)
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const data = await response.json()
    if (sessionStore.currentSessionId === sessionId) activeSkill.value = data
  } catch {
    if (sessionStore.currentSessionId === sessionId) {
      activeSkill.value = { active: false, command: '', arguments: '' }
    }
  }
}

async function clearActiveSkill() {
  const sessionId = sessionStore.currentSessionId
  try {
    const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/skill-state`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ active_command: '' }),
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`)
    if (sessionStore.currentSessionId === sessionId) activeSkill.value = data
    toast.info('已关闭当前技能')
  } catch (error) {
    toast.error(error.message || '关闭技能失败')
  }
}

async function loadToolSettings() {
  const sessionId = sessionStore.currentSessionId
  try {
    const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/tool-settings`)
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const data = await response.json()
    if (sessionStore.currentSessionId === sessionId) Object.assign(toolSettings, data)
  } catch {
    Object.assign(toolSettings, {
      tool_workspace: '',
      effective_workspace: '',
      approval_mode: 'ask',
      host_execution_enabled: false,
      is_default: true,
    })
    toast.warning('工作目录设置加载失败')
  }
}

async function updateToolSettings(updates) {
  const sessionId = sessionStore.currentSessionId
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/tool-settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || `保存失败: HTTP ${response.status}`)
  if (sessionStore.currentSessionId === sessionId) Object.assign(toolSettings, data)
  return data
}

async function updateApprovalMode(mode) {
  const previous = toolSettings.approval_mode
  toolSettings.approval_mode = mode
  try {
    await updateToolSettings({ approval_mode: mode })
    toast.info(mode === 'auto' ? '已切换为自动审批' : '已切换为请求批准')
  } catch (error) {
    toolSettings.approval_mode = previous
    toast.error(error.message || '审批模式保存失败')
  }
}

async function updateHostExecution(enabled) {
  const previous = toolSettings.host_execution_enabled
  toolSettings.host_execution_enabled = enabled
  try {
    await updateToolSettings({ host_execution_enabled: enabled })
    toast.warning(enabled
      ? '主机执行已启用；每条命令仍需手动确认'
      : '主机执行已关闭')
  } catch (error) {
    toolSettings.host_execution_enabled = previous
    toast.error(error.message || '主机执行权限保存失败')
  }
}

async function saveToolWorkspace(path) {
  if (toolSettingsSaving.value) return
  toolSettingsSaving.value = true
  try {
    await updateToolSettings({ tool_workspace: path })
    toast.info(path ? '工作目录已切换' : '已恢复默认工作目录')
  } catch (error) {
    toast.error(error.message || '工作目录保存失败')
  } finally {
    toolSettingsSaving.value = false
  }
}

watch(connectionStatus, (nextStatus, previousStatus) => {
  if (previousStatus !== 'connected' || nextStatus === 'connected' || !store.isStreaming) return
  store.handleError('连接中断，请重新生成', store.activeGenerationId)
  toast.warning('生成因连接中断而停止')
})


// 键盘快捷键
useKeyboard({
  'ctrl+n': () => {
    sessionListRef.value?.handleNew()
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

// 新建对话 - 发送首条消息时由 SessionList 打开主题包选择框
const sessionListRef = ref(null)
const pendingInitialSend = ref(null)

function hasRealCurrentSession() {
  return Boolean(
    sessionStore.currentSessionId
    && sessionStore.currentSessionId !== 'default',
  )
}

function queueInitialSend(content, acknowledge) {
  if (!sessionListRef.value) {
    acknowledge(false)
    toast.error('主题包选择器尚未就绪，请稍后重试')
    return
  }

  pendingInitialSend.value = { content, acknowledge }
  sessionListRef.value.handleNew({
    onCreated: async () => {
      const pending = pendingInitialSend.value
      pendingInitialSend.value = null
      if (pending) await handleSend(pending.content, pending.acknowledge)
    },
    onCancel: () => {
      const pending = pendingInitialSend.value
      pendingInitialSend.value = null
      pending?.acknowledge(false)
    },
  })
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
      confirmDialog.code = data.code || data.data?.code || ''
      confirmDialog.securityWarning = data.security_warning || data.data?.security_warning || ''
      confirmDialog.visible = true
    } else if (msg.type === 'skill_state') {
      activeSkill.value = msg.state || { active: false, command: '', arguments: '' }
    } else if (msg.type === 'context_compaction') {
      if (
        msg.generation_id
        && store.activeGenerationId
        && msg.generation_id !== store.activeGenerationId
      ) return
      if (contextCompactionTimer) clearTimeout(contextCompactionTimer)
      contextCompaction.mode = msg.mode || 'automatic'
      contextCompaction.phase = msg.phase || 'start'
      contextCompaction.message = msg.phase === 'done'
        ? (msg.message || '上下文整理完成')
        : msg.phase === 'error'
          ? `上下文整理失败：${msg.message || '未知错误'}`
          : '正在整理上下文'
      contextCompaction.visible = true
      if (msg.phase !== 'start') {
        contextCompactionTimer = setTimeout(() => {
          contextCompaction.visible = false
        }, msg.phase === 'error' ? 2400 : 1200)
      }
    } else if (msg.type === 'done') {
      applied = store.finishStreaming(msg.emoji, msg.generation_id)
      if (!applied) return
      setDesktopPetState('done', themeStore.current)
      if (petDoneTimer) clearTimeout(petDoneTimer)
      petDoneTimer = setTimeout(syncPetState, 1400)
      // 首条消息自动命名
      autoTitleIfNeeded()
      // 保存展开状态
      saveToolExpanded()
      loadSkillState()
      // 自动 TTS
      if (autoTTS.value) {
        autoSpeakLast()
      }
    } else if (msg.type === 'error') {
      applied = store.handleError(msg.content || msg.message || '未知错误', msg.generation_id)
      if (applied) {
        setDesktopPetState('error', themeStore.current)
        if (petDoneTimer) clearTimeout(petDoneTimer)
        petDoneTimer = setTimeout(syncPetState, 1400)
      }
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

function handleStopSubagent(subagentId) {
  if (!subagentId) return
  const sent = send({
    type: 'stop_subagent',
    session_id: sessionStore.currentSessionId,
    generation_id: store.activeGenerationId,
    subagent_id: subagentId,
  })
  if (!sent) {
    toast.warning('连接不可用，无法停止子代理')
    reconnect()
  }
}

async function handleSend(content, acknowledge = () => {}) {
  if (!hasRealCurrentSession()) {
    queueInitialSend(content, acknowledge)
    return
  }

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

    if (typeof content === 'string' && content.trim().toLowerCase() === '/compact') {
      retainedSendRequest = null
      acknowledge(true)
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

function isChoiceResolved(messageIndex) {
  const message = store.messages[messageIndex]
  if (message?.choicePending) return true
  return store.messages.slice(messageIndex + 1).some(item => item.role === 'user')
}

function handleChoice(messageIndex, payload) {
  const message = store.messages[messageIndex]
  const option = payload?.option
  if (!message || message.choicePending || !option || isChoiceResolved(messageIndex)) return
  message.choicePending = true
  const response = option.custom ? `其他：${option.label}` : `${option.id}：${option.label}`
  handleSend(response, success => {
    if (!success) message.choicePending = false
  })
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
    text = finalAnswerText(last.segments)
  } else {
    text = last.content || ''
  }
  text = prepareTextForSpeech(text)
  if (!text || text.length < 2) return

  const run = ++autoSpeechRun
  let fallbackStarted = false
  releaseAutoAudio()
  cancelBrowserSpeech()
  autoBrowserUtterance = null

  const fallbackToBrowser = (message, detail = '') => {
    if (run !== autoSpeechRun || fallbackStarted) return
    fallbackStarted = true
    releaseAutoAudio()
    autoBrowserUtterance = speakWithBrowser(text, {
      onEnd: () => {
        if (run === autoSpeechRun) {
          autoBrowserUtterance = null
          syncPetState()
        }
      },
      onError: () => {
        if (run === autoSpeechRun) {
          autoBrowserUtterance = null
          syncPetState()
        }
        toast.warning('系统语音播放失败')
      },
    })
    if (autoBrowserUtterance) {
      setDesktopPetState('speaking', themeStore.current)
      const reason = detail ? `：${String(detail).slice(0, 120)}` : ''
      toast.warning(`${message}${reason}`)
    } else {
      toast.warning(detail || '语音播放失败，当前设备不支持系统语音')
    }
  }

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
      fallbackToBrowser('云端语音不可用，已切换到系统语音', err.detail)
      return
    }
    const blob = await resp.blob()
    if (blob.size === 0) {
      fallbackToBrowser('云端语音不可用，已切换到系统语音', 'TTS 返回空音频')
      return
    }
    if (run !== autoSpeechRun) return
    ttsAudioUrl = URL.createObjectURL(blob)
    ttsAudio = new Audio(ttsAudioUrl)
    ttsAudio.onended = () => {
      releaseAutoAudio()
      syncPetState()
    }
    ttsAudio.onerror = () => {
      fallbackToBrowser('云端音频无法播放，已切换到系统语音', '音频播放失败')
    }
    try {
      await ttsAudio.play()
      setDesktopPetState('speaking', themeStore.current)
    } catch (e) {
      fallbackToBrowser('自动音频播放受限，已切换到系统语音', e.message)
    }
  } catch (e) {
    fallbackToBrowser('云端语音不可用，已切换到系统语音', e.message)
  }
}

function releaseAutoAudio() {
  if (ttsAudio) {
    ttsAudio.pause()
    ttsAudio.onended = null
    ttsAudio.onerror = null
    ttsAudio = null
  }
  if (ttsAudioUrl) {
    URL.revokeObjectURL(ttsAudioUrl)
    ttsAudioUrl = ''
  }
}

onBeforeUnmount(() => {
  autoSpeechRun += 1
  releaseAutoAudio()
  if (autoBrowserUtterance) cancelBrowserSpeech()
  autoBrowserUtterance = null
  if (contextCompactionTimer) clearTimeout(contextCompactionTimer)
})

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
          ? finalAnswerText(assistantMsg.segments)
          : assistantMsg.content || '',
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
.workspace-toggle {
  position: absolute;
  top: 12px;
  right: 14px;
  z-index: 30;
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  color: var(--text-secondary);
  background: var(--surface-control);
  border: 1px solid rgba(255, 255, 255, 0.13);
  border-radius: 8px;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.2);
  cursor: pointer;
  backdrop-filter: blur(12px);
}
.workspace-toggle:hover,
.workspace-toggle.active {
  color: var(--text-primary);
  border-color: color-mix(in srgb, var(--primary) 65%, transparent);
  background: color-mix(in srgb, var(--surface-control) 88%, var(--primary));
}
.workspace-panel-enter-active,
.workspace-panel-leave-active {
  transition: width var(--motion-base) var(--ease-emphasized), opacity var(--motion-fast) var(--ease-standard), transform var(--motion-base) var(--ease-emphasized);
}
.workspace-panel-enter-from,
.workspace-panel-leave-to {
  width: 0;
  opacity: 0;
  transform: translateX(20px);
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
.scroll-bottom-btn.above-active-skill {
  bottom: 124px;
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

.context-compaction-status {
  position: absolute;
  left: 50%;
  bottom: 86px;
  z-index: 16;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  max-width: min(460px, calc(100% - 32px));
  padding: 7px 11px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 8px;
  background: rgba(24, 24, 32, 0.88);
  box-shadow: 0 5px 18px rgba(0, 0, 0, 0.18);
  color: var(--text-secondary);
  font-size: 12px;
  transform: translateX(-50%);
  pointer-events: none;
}
.context-compaction-status.done { color: var(--success, #62c78a); }
.context-compaction-status.error { color: var(--danger, #ef7d7d); }
.context-compaction-spinner { animation: spin 0.9s linear infinite; }
.context-compaction-dots { width: 18px; overflow: hidden; animation: compaction-dots 1.2s steps(4, end) infinite; }
@keyframes compaction-dots {
  0% { width: 0; }
  100% { width: 18px; }
}
.context-compaction-enter-active,
.context-compaction-leave-active { transition: opacity 0.18s ease, transform 0.18s ease; }
.context-compaction-enter-from,
.context-compaction-leave-to { opacity: 0; transform: translate(-50%, 6px); }
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
  background: rgba(2, 6, 12, 0.78);
  backdrop-filter: blur(5px);
  -webkit-backdrop-filter: blur(5px);


  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.confirm-dialog {
  background: #152337;
  border: 1px solid rgba(255, 255, 255, 0.18);
  color: #f3f6fb;


  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.24), 0 14px 42px rgba(0, 0, 0, 0.58);
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
  color: #f3f6fb;
}
.confirm-body {
  margin-bottom: 20px;
}
.confirm-message {
  font-size: 14px;
  color: #f3f6fb;
  line-height: 1.6;
  margin-bottom: 12px;
}
.confirm-warning {
  margin: 0 0 12px;
  padding: 10px 12px;
  color: #fde68a;
  background: rgba(245, 158, 11, 0.13);
  border: 1px solid rgba(245, 158, 11, 0.32);
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.5;
}
.confirm-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 14px;
  background: #0d1929;
  border: 1px solid rgba(255, 255, 255, 0.1);
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
  color: #c5cfdd;
  font-family: monospace;
  word-break: break-all;
}
.confirm-count {
  color: #c5cfdd;
}
.confirm-code {
  max-height: 240px;
  margin: 4px 0 0;
  padding: 10px;
  overflow: auto;
  color: #e5edf7;
  background: #08111d;
  border-radius: 5px;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
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
  background: #23344a;
  color: #e1e7ef;
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

  .scroll-bottom-btn.above-active-skill {
    bottom: 130px;
  }

  .connection-status {
    left: 16px;
    bottom: 92px;
  }

  .context-compaction-status {
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
