<template>
  <div class="bubble-row" :class="msg.role">
    <div class="bubble" :class="[msg.role, { 'content-wide': usesWideLayout }]">
      <!-- 旧消息兼容 -->
      <template v-if="!msg.segments">
        <div v-if="msg.image" class="image-msg">
          <img :src="msg.image.dataUrl || msg.image.url" :alt="msg.image.filename" />
        </div>
        <div v-if="msg.file" class="file-msg">
          <FileText class="file-icon" :size="18" aria-hidden="true" />
          <span class="file-name">{{ msg.file.filename }}</span>
        </div>
        <div v-if="msg.content" class="text-seg" v-html="renderText(msg.content)"></div>
      </template>

      <!-- 新消息 segments 渲染 -->
      <template v-else>
        <template v-for="(seg, i) in msg.segments" :key="i">
          <!-- 文本段 -->
          <div v-if="seg.type === 'text'" class="text-seg" v-html="renderText(seg.content)"></div>

          <div
            v-if="seg.type === 'reasoning'"
            class="reasoning-seg"
            :data-status="seg.status"
          >
            <button class="reasoning-header" type="button" @click="toggleReasoning(seg, i)">
              <BrainCircuit :size="15" aria-hidden="true" />
              <span>{{ reasoningLabel(seg) }}</span>
              <ChevronDown class="reasoning-arrow" :class="{ open: isReasoningExpanded(seg, i) }" :size="14" aria-hidden="true" />
            </button>
            <div v-if="isReasoningExpanded(seg, i) && seg.content" class="reasoning-content">{{ seg.content }}</div>
          </div>

          <!-- 工具段时间线节点 -->
          <template v-if="seg.type === 'tool'">
            <!-- 输出完成后折叠状态：显示小提示 -->
            <div v-if="!msg.streaming && toolsCollapsed && i === firstToolIndex" class="tools-collapsed-hint" @click.stop="toggleToolsCollapse">
              <Wrench :size="14" aria-hidden="true" />
              <span>调用了 {{ toolCount }} 个工具</span>
              <ChevronRight :size="14" aria-hidden="true" />
            </div>
            <!-- 正常显示工具 -->
            <div v-if="msg.streaming || !toolsCollapsed" class="tool-seg" :data-status="seg.status" @click="seg.result_detail ? toggleExpand(seg.tool_call_id) : null">
              <div class="tool-header">
                <span class="tool-icon">{{ toolIcon(seg.tool_name) }}</span>
                <span class="tool-name">{{ seg.tool_name }}</span>
                <span class="tool-args">{{ summarizeArgs(seg.tool_args) }}</span>
                <span class="tool-status">
                  <span v-if="seg.status === 'running'" class="spinner">⏳</span>
                  <span v-if="seg.status === 'done'">✅</span>
                  <span v-if="seg.status === 'error'">❌</span>
                </span>
                <ChevronDown v-if="seg.result_detail" class="tool-arrow" :class="{ open: expanded(seg.tool_call_id) }" :size="14" aria-hidden="true" />
                <button v-if="seg.status === 'error'" class="tool-retry" @click.stop="$emit('retry')">重试</button>
              </div>
              <div class="tool-summary" v-if="seg.result_summary && !expanded(seg.tool_call_id)">{{ seg.result_summary }}</div>
              <div class="tool-detail" v-if="expanded(seg.tool_call_id)">
                <pre v-if="seg.tool_name === 'code_exec'"><code>{{ seg.result_detail }}</code></pre>
                <div v-else-if="seg.tool_name === 'web_search'" v-html="formatSearchResults(seg.result_detail)"></div>
                <pre v-else>{{ seg.result_detail }}</pre>
              </div>
            </div>

            <!-- 展开时显示折叠按钮 -->
            <div v-if="!msg.streaming && !toolsCollapsed && i === lastToolIndex" class="tools-collapse-btn" @click.stop="toggleToolsCollapse">
              <span>收起工具</span>
              <ChevronUp :size="14" aria-hidden="true" />
            </div>
          </template>
        </template>
      </template>

      <span v-if="msg.emoji" class="emoji">{{ msg.emoji }}</span>
      <div v-if="msg.streaming && !hasRunningReasoning" class="typing-indicator">
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
      </div>

      <!-- 用户消息编辑模式 -->
      <div v-if="isEditing" class="edit-area">
        <textarea v-model="editContent" class="edit-textarea" rows="3" @keydown.enter.ctrl="confirmEdit" @keydown.escape="cancelEdit"></textarea>
        <div class="edit-actions">
          <button class="edit-btn cancel" @click="cancelEdit">取消</button>
          <button class="edit-btn confirm" @click="confirmEdit">重新发送 (Ctrl+Enter)</button>
        </div>
      </div>
    </div>
    <!-- 用户消息操作按钮 -->
    <div v-if="msg.role === 'user' && !msg.streaming && !isEditing" class="msg-actions">
      <button class="action-btn" @click="startEdit" title="编辑" aria-label="编辑消息">
        <Pencil :size="14" aria-hidden="true" />
      </button>
    </div>
    <!-- 助手消息重试按钮 -->
    <button
      v-if="msg.role === 'assistant' && !msg.streaming && hasTextContent"
      class="action-btn retry-btn"
      @click="$emit('retry')"
      title="重新生成"
      aria-label="重新生成"
    ><RefreshCcw :size="14" aria-hidden="true" /></button>
    <!-- TTS 播放按钮（仅 assistant 消息） -->
    <button
      v-if="msg.role === 'assistant' && !msg.streaming && hasTextContent"
      class="tts-btn"
      :class="{ playing: isPlaying }"
      @click="speakText"
      title="语音播放"
      aria-label="语音播放"
    >
      <Volume2 v-if="isPlaying" :size="14" aria-hidden="true" />
      <Volume1 v-else :size="14" aria-hidden="true" />
    </button>
  </div>
</template>

<script setup>
import { ref, computed, onBeforeUnmount, watch } from 'vue'
import { marked } from 'marked'
import { BrainCircuit, ChevronDown, ChevronRight, ChevronUp, FileText, Pencil, RefreshCcw, Volume1, Volume2, Wrench } from 'lucide-vue-next'
import { useSessionStore } from '../stores/session'
import { useThemeStore } from '../stores/theme'
import { useToast } from '../composables/useToast'
import { cancelBrowserSpeech, speakWithBrowser } from '../utils/browserSpeech'
import { prepareTextForSpeech } from '../utils/ttsText'

const sessionStore = useSessionStore()
const themeStore = useThemeStore()
const toast = useToast()

// 配置 marked：安全渲染，不执行脚本
marked.setOptions({
  breaks: true,    // 换行符转 <br>
  gfm: true,       // GitHub Flavored Markdown（表格、任务列表等）
})

function renderText(content) {
  if (!content) return ''
  return marked.parse(content)
}

const props = defineProps({ msg: Object })
const emit = defineEmits(['retry', 'edit'])
const expandedReasoning = ref({})

// 编辑模式
const isEditing = ref(false)
const editContent = ref('')

function startEdit() {
  editContent.value = props.msg.content || ''
  isEditing.value = true
}
function cancelEdit() {
  isEditing.value = false
}
function confirmEdit() {
  if (editContent.value.trim()) {
    emit('edit', editContent.value.trim())
  }
  isEditing.value = false
}

const hasTools = computed(() =>
  props.msg.segments?.some(s => s.type === 'tool')
)

const hasAnswerText = computed(() =>
  props.msg.segments?.some(segment => segment.type === 'text' && segment.content?.trim()) || false
)

const hasRunningReasoning = computed(() =>
  props.msg.segments?.some(segment => segment.type === 'reasoning' && segment.status === 'running') || false
)

watch(hasAnswerText, hasText => {
  if (hasText) expandedReasoning.value = {}
})

function reasoningKey(segment, index) {
  return segment.reasoning_id || `reasoning-${index}`
}

function isReasoningExpanded(segment, index) {
  const key = reasoningKey(segment, index)
  if (Object.prototype.hasOwnProperty.call(expandedReasoning.value, key)) {
    return expandedReasoning.value[key]
  }
  return props.msg.streaming && segment.status === 'running'
}

function toggleReasoning(segment, index) {
  const key = reasoningKey(segment, index)
  expandedReasoning.value = {
    ...expandedReasoning.value,
    [key]: !isReasoningExpanded(segment, index),
  }
}

function reasoningLabel(segment) {
  if (segment.status === 'unavailable') return '当前模型不支持深度思考'
  if (segment.status === 'error') return '思考中断'
  if (segment.status === 'stopped') return '思考已停止'
  if (segment.status === 'running') return '思考中'
  const duration = Number(segment.duration_ms || 0)
  if (!duration) return '思考完成'
  return `思考完成 · ${(duration / 1000).toFixed(duration >= 10000 ? 0 : 1)} 秒`
}

const usesWideLayout = computed(() => {
  if (hasTools.value) return true

  const text = props.msg.segments
    ? props.msg.segments.filter(s => s.type === 'text').map(s => s.content || '').join('\n')
    : props.msg.content || ''

  return /```|<pre[\s>]|<table[\s>]|^\s*\|.+\|\s*$/im.test(text)
})

const toolCount = computed(() => {
  return props.msg.segments?.filter(s => s.type === 'tool').length || 0
})

const firstToolIndex = computed(() => {
  return props.msg.segments?.findIndex(s => s.type === 'tool') ?? -1
})

const lastToolIndex = computed(() => {
  if (!props.msg.segments) return -1
  for (let i = props.msg.segments.length - 1; i >= 0; i--) {
    if (props.msg.segments[i].type === 'tool') return i
  }
  return -1
})

// 工具调用折叠状态
const toolsCollapsed = ref(true)

// 切换折叠状态
function toggleToolsCollapse() {
  toolsCollapsed.value = !toolsCollapsed.value
}

// 消息完成时自动折叠
watch(() => props.msg.streaming, (newVal, oldVal) => {
  if (oldVal === true && newVal === false) {
    toolsCollapsed.value = true
  }
})

const allExpanded = computed(() => {
  if (!props.msg.segments) return false
  const tools = props.msg.segments.filter(s => s.type === 'tool')
  return tools.length > 0 && tools.every(t => props.msg.expandedTools?.[t.tool_call_id])
})

function expanded(toolCallId) {
  return props.msg.expandedTools?.[toolCallId] || false
}

function toggleExpand(toolCallId) {
  if (!props.msg.expandedTools) props.msg.expandedTools = {}
  props.msg.expandedTools[toolCallId] = !props.msg.expandedTools[toolCallId]
}

function toggleAll() {
  if (!props.msg.expandedTools) props.msg.expandedTools = {}
  const tools = props.msg.segments.filter(s => s.type === 'tool')
  const expand = !allExpanded.value
  tools.forEach(t => { props.msg.expandedTools[t.tool_call_id] = expand })
}

function toolIcon(name) {
  const icons = { web_search: '🔍', code_exec: '💻', file_manager: '📁' }
  return icons[name] || '🔧'
}

function summarizeArgs(args) {
  if (!args) return ''
  if (args.query) return `「${args.query}」`
  if (args.code) return args.code.slice(0, 50) + (args.code.length > 50 ? '...' : '')
  if (args.path) return args.path
  if (args.action) return args.action
  return JSON.stringify(args).slice(0, 60)
}

// --- TTS 语音播放 ---
const isPlaying = ref(false)
let audioEl = null
let audioUrl = ''
let browserUtterance = null
let playbackRun = 0

const hasTextContent = computed(() => {
  if (!props.msg.segments) return !!props.msg.content
  return props.msg.segments.some(s => s.type === 'text' && s.content?.trim())
})

function getPlainText() {
  const text = props.msg.segments
    ? props.msg.segments
      .filter(s => s.type === 'text')
      .map(s => s.content)
      .join('')
    : props.msg.content || ''
  return prepareTextForSpeech(text)
}

async function speakText() {
  const text = getPlainText()
  if (!text) return

  if (isPlaying.value) {
    stopSpeech()
    return
  }

  const run = ++playbackRun
  let fallbackStarted = false
  const fallbackToBrowser = (detail = '') => {
    if (run !== playbackRun || fallbackStarted) return
    fallbackStarted = true
    releaseAudio()
    browserUtterance = speakWithBrowser(text, {
      onEnd: () => finishSpeech(run),
      onError: () => {
        finishSpeech(run)
        toast.error('系统语音播放失败')
      },
    })
    if (browserUtterance) {
      const reason = detail ? `：${String(detail).slice(0, 120)}` : ''
      toast.warning(`云端语音不可用，已切换到系统语音${reason}`)
    } else {
      finishSpeech(run)
      toast.error(detail || '语音播放失败，当前设备不支持系统语音')
    }
  }

  try {
    isPlaying.value = true
    const currentSession = sessionStore.currentSessionId
    const session = sessionStore.sessions.find(s => s.id === currentSession)
    const packId = session?.theme_pack_id || themeStore.current || ''

    const resp = await fetch('/api/tts/speak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text.slice(0, 2000), pack_id: packId })
    })

    if (!resp.ok) {
      const error = await resp.json().catch(() => ({}))
      fallbackToBrowser(error.detail)
      return
    }

    const blob = await resp.blob()
    if (!blob.size) {
      fallbackToBrowser('云端语音返回了空音频')
      return
    }
    if (run !== playbackRun) return
    audioUrl = URL.createObjectURL(blob)
    audioEl = new Audio(audioUrl)
    audioEl.onended = () => {
      releaseAudio()
      finishSpeech(run)
    }
    audioEl.onerror = () => {
      fallbackToBrowser('音频格式无法播放')
    }
    try {
      await audioEl.play()
    } catch (error) {
      fallbackToBrowser(error.message)
    }
  } catch (error) {
    fallbackToBrowser(error.message)
  }
}

function releaseAudio() {
  if (audioEl) {
    audioEl.pause()
    audioEl.onended = null
    audioEl.onerror = null
    audioEl = null
  }
  if (audioUrl) {
    URL.revokeObjectURL(audioUrl)
    audioUrl = ''
  }
}

function finishSpeech(run) {
  if (run !== playbackRun) return
  browserUtterance = null
  isPlaying.value = false
}

function stopSpeech() {
  playbackRun += 1
  releaseAudio()
  if (browserUtterance) cancelBrowserSpeech()
  browserUtterance = null
  isPlaying.value = false
}

onBeforeUnmount(stopSpeech)
</script>

<style scoped>
.bubble-row { display: flex; margin: 8px 16px; }
.bubble-row.user { justify-content: flex-end; }
.bubble-row.assistant { justify-content: flex-start; }

/* L3: Chat bubbles — 微毛玻璃 + 自适应描边 */
.bubble {
  max-width: min(78%, 760px);
  padding: var(--bubble-padding);
  position: relative;
  border-radius: var(--radius);
  background: rgba(10, 10, 24, 0.70);
  border: none;
  box-shadow: var(--bubble-border);
  backdrop-filter: blur(3px);
  -webkit-backdrop-filter: blur(3px);
}

.bubble.content-wide {
  width: min(94%, 1040px);
  max-width: min(94%, 1040px);
}

/* Asymmetric bottom radius: user bubble bottom-right 8px */
.bubble.user {
  background: rgba(20, 20, 40, 0.74);
  border-bottom-right-radius: 8px;
}

/* Asymmetric bottom radius: assistant bubble bottom-left 8px */
.bubble.assistant {
  background: rgba(16, 18, 36, 0.70);
  border-bottom-left-radius: 8px;
}

.text-seg { text-shadow: var(--text-glow); line-height: var(--line-height); font-size: var(--font-size-base); word-break: break-word; }

/* 图片消息 */
.image-msg {
  margin-bottom: 6px;
}
.image-msg img {
  max-width: 300px;
  max-height: 300px;
  border-radius: 8px;
  object-fit: contain;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.10);
  cursor: pointer;
}
.image-msg img:hover {
  filter: brightness(1.05);
}

/* 文件消息 */
.file-msg {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(255,255,255,0.06);
  border-radius: 8px;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.10);
  margin-bottom: 6px;
  max-width: 260px;
}
.file-icon { color: var(--text-secondary); flex-shrink: 0; }
.file-name {
  font-size: 13px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.text-seg :deep(pre) { background: rgba(0,0,0,0.2); padding: 8px; border-radius: 4px; overflow-x: auto; margin: 8px 0; font-size: 12px; }
.text-seg :deep(code) { background: rgba(0,0,0,0.15); padding: 1px 4px; border-radius: 3px; font-size: 0.9em; }
.text-seg :deep(a) { color: var(--primary); text-decoration: none; }
.text-seg :deep(a:hover) { text-decoration: underline; }
.text-seg :deep(h1), .text-seg :deep(h2), .text-seg :deep(h3) { margin: 12px 0 6px; font-weight: 700; color: var(--text-primary); }
.text-seg :deep(h1) { font-size: 1.3em; }
.text-seg :deep(h2) { font-size: 1.15em; }
.text-seg :deep(h3) { font-size: 1.05em; }
.text-seg :deep(ul), .text-seg :deep(ol) { padding-left: 20px; margin: 6px 0; }
.text-seg :deep(li) { margin: 2px 0; }
.text-seg :deep(blockquote) { border-left: 3px solid var(--primary); padding-left: 10px; margin: 8px 0; color: var(--text-secondary); }
.text-seg :deep(hr) { border: none; border-top: 1px solid rgba(255,255,255,0.06); margin: 12px 0; }
.text-seg :deep(img) { max-width: 100%; border-radius: 6px; }
.text-seg :deep(table) { border-collapse: collapse; margin: 8px 0; width: 100%; font-size: 13px; }
.text-seg :deep(th), .text-seg :deep(td) { box-shadow: 0 0 0 1px rgba(255,255,255,0.06); padding: 6px 10px; text-align: left; }
.text-seg :deep(th) { background: rgba(124, 92, 252, 0.18); font-weight: 600; padding: 8px 12px; }
.text-seg :deep(tr:nth-child(even)) { background: rgba(255,255,255,0.04); }
.text-seg :deep(strong) { color: var(--text-primary); font-weight: 700; }
.text-seg :deep(em) { font-style: italic; }
.text-seg :deep(del) { text-decoration: line-through; color: var(--text-secondary); }

.reasoning-seg {
  margin: 2px 0 8px;
  color: var(--text-secondary);
  font-size: 12px;
}
.reasoning-header {
  width: 100%;
  min-height: 28px;
  padding: 2px 0;
  display: flex;
  align-items: center;
  gap: 7px;
  border: none;
  background: transparent;
  color: inherit;
  cursor: pointer;
  text-align: left;
}
.reasoning-header span { flex: 1; }
.reasoning-arrow { transition: transform var(--motion-fast) var(--ease-standard); }
.reasoning-arrow.open { transform: rotate(180deg); }
.reasoning-content {
  max-height: 280px;
  margin: 4px 0 6px 7px;
  padding: 4px 0 4px 14px;
  overflow: auto;
  border-left: 1px solid rgba(255, 255, 255, 0.16);
  color: var(--text-secondary);
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}
.reasoning-seg[data-status="running"] { color: var(--primary); }
.reasoning-seg[data-status="unavailable"],
.reasoning-seg[data-status="error"] { color: #f59e0b; }

.tool-actions-bar { display: flex; justify-content: flex-end; margin-bottom: 4px; }
.tool-toggle-all { background: none; border: none; color: var(--text-secondary); cursor: pointer; font-size: 11px; }

.tool-seg {
  margin: 4px 0; padding: 5px 10px;
  background: rgba(124, 92, 252, 0.06);
  box-shadow: 0 0 0 1px rgba(124, 92, 252, 0.12);
  border-left: 2px solid var(--primary);
  border-radius: 0 6px 6px 0;
  font-size: 12px; position: relative;
  cursor: default;
  max-width: 100%;
}
.tool-seg:has(.tool-arrow) { cursor: pointer; }
/* 连续 tool 段连接线 */
.tool-seg + .tool-seg::before {
  content: ''; position: absolute;
  left: -3px; top: -8px; width: 3px; height: 8px;
  background: var(--primary);
}
.tool-seg + .tool-seg { margin-top: 2px; }
/* 状态配色 */
.tool-seg[data-status="running"] { border-left-color: #3b82f6; background: rgba(59, 130, 246, 0.06); }
.tool-seg[data-status="running"] + .tool-seg::before { background: #3b82f6; }
.tool-seg[data-status="done"] { border-left-color: #22c55e; background: rgba(34, 197, 94, 0.06); }
.tool-seg[data-status="done"] + .tool-seg::before { background: #22c55e; }
.tool-seg[data-status="error"] { border-left-color: #ef4444; background: rgba(239, 68, 68, 0.06); }
.tool-seg[data-status="error"] + .tool-seg::before { background: #ef4444; }

/* 工具折叠提示（原位） */
.tools-collapsed-hint {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  margin: 4px 0;
  background: rgba(124, 92, 252, 0.08);
  border: 1px solid rgba(124, 92, 252, 0.2);
  border-radius: 6px;
  cursor: pointer;
  transition: background 180ms ease, border-color 180ms ease, color 180ms ease;
  font-size: 12px;
  color: var(--text-secondary);
}
.tools-collapsed-hint:hover {
  background: rgba(124, 92, 252, 0.15);
  border-color: rgba(124, 92, 252, 0.3);
}

/* 工具折叠按钮（展开时显示） */
.tools-collapse-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  margin: 4px 0;
  background: rgba(124, 92, 252, 0.06);
  border: 1px solid rgba(124, 92, 252, 0.15);
  border-radius: 6px;
  cursor: pointer;
  transition: background 180ms ease, border-color 180ms ease, color 180ms ease;
  font-size: 12px;
  color: var(--text-secondary);
}
.tools-collapse-btn:hover {
  background: rgba(124, 92, 252, 0.12);
  border-color: rgba(124, 92, 252, 0.25);
}

/* 打字指示器 */
.typing-indicator {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
}

.typing-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary);
  animation: typing-bounce 1.4s ease-in-out infinite;
}

.typing-dot:nth-child(1) {
  animation-delay: 0s;
}

.typing-dot:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing-bounce {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  30% {
    transform: translateY(-8px);
    opacity: 1;
  }
}

.tool-header { display: flex; align-items: center; gap: 4px; flex-wrap: nowrap; }
.tool-icon { font-size: 12px; flex-shrink: 0; }
.tool-name { font-weight: 600; color: var(--primary); font-size: 11px; flex-shrink: 0; }
.tool-args { color: var(--text-secondary); font-size: 11px; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tool-status { flex-shrink: 0; font-size: 11px; }
.tool-arrow {
  flex-shrink: 0;
  color: var(--text-secondary);
  transition: transform 180ms ease;
  cursor: pointer;
}
.tool-arrow.open { transform: rotate(180deg); }
.tool-summary { margin-top: 3px; color: var(--text-secondary); font-size: 11px; padding: 2px 6px; background: rgba(0,0,0,0.05); border-radius: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tool-detail { margin-top: 6px; padding: 8px; background: rgba(0,0,0,0.2); box-shadow: 0 0 0 1px rgba(124,92,252,0.08); border-radius: 6px; font-size: 11px; max-height: 200px; overflow-y: auto; }
.tool-detail pre { margin: 0; white-space: pre-wrap; word-break: break-all; }
.tool-retry { background: none; border: none; color: #ef4444; cursor: pointer; font-size: 11px; flex-shrink: 0; padding: 0 4px; }
.search-result { padding: 2px 0; }
.search-result a { color: var(--primary); text-decoration: none; }
.search-result a:hover { text-decoration: underline; }

.spinner { animation: spin 1s linear infinite; display: inline-block; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.streaming-indicator { animation: blink 1s infinite; color: var(--primary); margin-left: 4px; }
@keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }
.emoji { font-size: 20px; position: absolute; bottom: -4px; right: -4px; }

/* TTS 播放按钮 */
.tts-btn {
  margin-top: 4px;
  width: 26px;
  height: 26px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  color: var(--text-secondary);
  opacity: 0.5;
  transition: opacity 180ms ease, color 180ms ease, background 180ms ease;
  align-self: flex-start;
  box-shadow: none;
}
.tts-btn:hover {
  opacity: 1;
  color: var(--primary);
  background: rgba(124, 92, 252, 0.1);
}
.tts-btn.playing {
  opacity: 1;
  color: var(--primary);
  animation: pulse-tts 1.5s infinite;
}
@keyframes pulse-tts {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* 编辑模式 */
.edit-area { margin-top: 8px; }
.edit-textarea {
  width: 100%;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(20, 20, 40, 0.60);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
  border: none;
  color: var(--text-primary);
  font-size: 13px;
  font-family: inherit;
  resize: vertical;
  min-height: 60px;
  outline: none;
}
.edit-textarea:focus {
  box-shadow: 0 0 0 1px var(--primary);
}
.edit-actions {
  display: flex;
  gap: 6px;
  margin-top: 6px;
  justify-content: flex-end;
}
.edit-btn {
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  border: none;
  transition: all 0.15s;
}
.edit-btn.cancel {
  background: rgba(20, 20, 40, 0.60);
  color: var(--text-secondary);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.15);
}
.edit-btn.confirm {
  background: var(--primary);
  color: #fff;
}
.edit-btn:hover { filter: brightness(1.1); }

/* 消息操作按钮 */
.msg-actions {
  display: flex;
  gap: 4px;
  margin-top: 4px;
  opacity: 0;
  transition: opacity 0.15s;
}
.bubble-row:hover .msg-actions { opacity: 1; }
.action-btn {
  width: 26px;
  height: 26px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  background: rgba(20, 20, 40, 0.60);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.10);
  border: none;
  cursor: pointer;
  transition: box-shadow 180ms ease, filter 180ms ease, opacity 180ms ease;
  opacity: 0;
}
.bubble-row:hover .action-btn { opacity: 1; }
.action-btn:hover {
  box-shadow: 0 0 0 1px var(--primary);
  filter: brightness(1.1);
}

@media (max-width: 767px) {
  .bubble {
    max-width: 88%;
  }

  .bubble.content-wide {
    width: 96%;
    max-width: 96%;
  }
}
.retry-btn {
  position: absolute;
  right: -30px;
  top: 0;
}
</style>
