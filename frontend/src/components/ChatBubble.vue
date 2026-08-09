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
        <section v-if="workSegments.length" class="agent-work" :data-status="workStatus">
          <button
            class="agent-work-header"
            type="button"
            :aria-expanded="workExpanded"
            :disabled="msg.streaming"
            @click="toggleWork"
          >
            <BrainCircuit :size="15" aria-hidden="true" />
            <span class="agent-work-label">{{ workLabel }}</span>
            <span v-if="workMeta" class="agent-work-meta">{{ workMeta }}</span>
            <ChevronDown class="agent-work-arrow" :class="{ open: workExpanded }" :size="14" aria-hidden="true" />
          </button>

          <div v-if="workExpanded" class="agent-work-content">
            <template v-for="entry in workEntries" :key="entry.key">
              <div v-if="entry.segment.type === 'reasoning'" class="work-reasoning" :data-status="entry.segment.status">
                <button
                  type="button"
                  class="work-entry-header"
                  :aria-expanded="reasoningExpanded(entry.segment, entry.reasoningNumber)"
                  @click.stop="toggleReasoning(entry.segment, entry.reasoningNumber)"
                >
                  <span>思考片段 {{ entry.reasoningNumber }}</span>
                  <span v-if="entry.segment.duration_ms">{{ formatReasoningDuration(Number(entry.segment.duration_ms)) }}</span>
                  <ChevronDown
                    class="work-entry-arrow"
                    :class="{ open: reasoningExpanded(entry.segment, entry.reasoningNumber) }"
                    :size="13"
                    aria-hidden="true"
                  />
                </button>
                <div
                  v-if="reasoningExpanded(entry.segment, entry.reasoningNumber) && entry.segment.content"
                  class="work-reasoning-text"
                >{{ entry.segment.content }}</div>
              </div>

              <div
                v-else-if="entry.segment.type === 'text'"
                class="work-text text-seg"
                v-html="renderText(entry.segment.content)"
              ></div>

              <div
                v-else-if="entry.segment.type === 'tool'"
                class="tool-seg"
                :data-status="entry.segment.status"
                @click="entry.segment.result_detail ? toggleExpand(entry.segment.tool_call_id) : null"
              >
                <div class="tool-header">
                  <span class="tool-icon">{{ toolIcon(entry.segment.tool_name) }}</span>
                  <span class="tool-name">{{ entry.segment.tool_name }}</span>
                  <span class="tool-args">{{ summarizeArgs(entry.segment.tool_args) }}</span>
                  <span class="tool-status">
                    <span v-if="entry.segment.status === 'running'" class="spinner">⏳</span>
                    <span v-if="entry.segment.status === 'done'">✅</span>
                    <span v-if="entry.segment.status === 'error'">❌</span>
                  </span>
                  <ChevronDown
                    v-if="entry.segment.result_detail"
                    class="tool-arrow"
                    :class="{ open: expanded(entry.segment.tool_call_id) }"
                    :size="14"
                    aria-hidden="true"
                  />
                  <button v-if="entry.segment.status === 'error'" class="tool-retry" @click.stop="$emit('retry')">重试</button>
                </div>
                <div v-if="entry.segment.result_summary && !expanded(entry.segment.tool_call_id)" class="tool-summary">
                  {{ entry.segment.result_summary }}
                </div>
                <div v-if="expanded(entry.segment.tool_call_id)" class="tool-detail">
                  <pre v-if="entry.segment.tool_name === 'code_exec'"><code>{{ entry.segment.result_detail }}</code></pre>
                  <div v-else-if="entry.segment.tool_name === 'web_search'" v-html="formatSearchResults(entry.segment.result_detail)"></div>
                  <pre v-else>{{ entry.segment.result_detail }}</pre>
                </div>
              </div>
            </template>
          </div>
        </section>

        <div
          v-for="(seg, index) in answerSegments"
          :key="'answer-' + index"
          class="text-seg"
          v-html="renderText(seg.content)"
        ></div>
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
import { ref, reactive, computed, onBeforeUnmount, watch } from 'vue'
import { marked } from 'marked'
import { BrainCircuit, ChevronDown, FileText, Pencil, RefreshCcw, Volume1, Volume2 } from 'lucide-vue-next'
import { useSessionStore } from '../stores/session'
import { useThemeStore } from '../stores/theme'
import { useToast } from '../composables/useToast'
import { cancelBrowserSpeech, speakWithBrowser } from '../utils/browserSpeech'
import { prepareTextForSpeech } from '../utils/ttsText'
import { setDesktopPetState } from '../utils/pet'
import { finalAnswerText, splitAgentSegments } from '../utils/agentTimeline'

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
const workExpanded = ref(Boolean(props.msg.streaming))
const expandedReasoning = reactive({})
const reasoningClock = ref(Date.now())
let reasoningTimer = null
let activeReasoningId = null
let activeReasoningStartedAt = 0

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

const segmentGroups = computed(() => splitAgentSegments(props.msg.segments || []))
const workSegments = computed(() => segmentGroups.value.work)
const answerSegments = computed(() => segmentGroups.value.answer.filter(segment => segment.type === 'text'))
const hasTools = computed(() => workSegments.value.some(segment => segment.type === 'tool'))

const reasoningEntries = computed(() =>
  workSegments.value.filter(segment => segment.type === 'reasoning')
)

const workEntries = computed(() => {
  let reasoningNumber = 0
  return workSegments.value.map((segment, index) => {
    if (segment.type === 'reasoning') reasoningNumber += 1
    return {
      segment,
      reasoningNumber,
      key: segment.reasoning_id || segment.tool_call_id || `work-${index}`,
    }
  })
})

const completedReasoningMs = computed(() =>
  reasoningEntries.value.reduce((total, segment) => {
    if (segment.status === 'running') return total
    return total + Number(segment.duration_ms || 0)
  }, 0)
)

const reasoningDurationMs = computed(() => {
  const active = reasoningEntries.value.find(segment => segment.status === 'running')
  if (!active || !activeReasoningStartedAt) return completedReasoningMs.value
  return completedReasoningMs.value + Math.max(0, reasoningClock.value - activeReasoningStartedAt)
})

function stopReasoningClock() {
  if (reasoningTimer) {
    clearInterval(reasoningTimer)
    reasoningTimer = null
  }
  activeReasoningId = null
  activeReasoningStartedAt = 0
}

function syncReasoningClock(entries) {
  const active = entries.find(segment => segment.status === 'running')
  if (!active) {
    stopReasoningClock()
    return
  }

  const activeId = active.reasoning_id || active
  if (activeReasoningId !== activeId) {
    activeReasoningId = activeId
    activeReasoningStartedAt = Date.now() - Number(active.duration_ms || 0)
  }

  reasoningClock.value = Date.now()
  if (!reasoningTimer) {
    reasoningTimer = setInterval(() => {
      reasoningClock.value = Date.now()
    }, 200)
  }
}

watch(reasoningEntries, syncReasoningClock, { deep: true, immediate: true })

const workStatus = computed(() => {
  if (workSegments.value.some(segment => segment.status === 'running')) return 'running'
  if (workSegments.value.some(segment => segment.status === 'error')) return 'error'
  if (workSegments.value.some(segment => segment.status === 'stopped')) return 'stopped'
  return props.msg.streaming ? 'running' : 'done'
})

const hasRunningReasoning = computed(() =>
  reasoningEntries.value.some(segment => segment.status === 'running')
)

const toolCount = computed(() =>
  workSegments.value.filter(segment => segment.type === 'tool').length
)

const workLabel = computed(() => {
  if (workStatus.value === 'error') return '工作中断'
  if (workStatus.value === 'stopped') return '工作已停止'
  if (workStatus.value === 'running') return '正在工作'
  return '工作完成'
})

function formatReasoningDuration(duration) {
  const seconds = duration / 1000
  return `${seconds.toFixed(duration >= 10000 ? 0 : 1)} 秒`
}

const workMeta = computed(() => {
  const parts = []
  if (reasoningEntries.value.length) {
    const duration = reasoningDurationMs.value
    parts.push(duration ? `思考 ${formatReasoningDuration(duration)}` : `${reasoningEntries.value.length} 段思考`)
  }
  if (toolCount.value) parts.push(`${toolCount.value} 个工具`)
  return parts.join(' · ')
})

const usesWideLayout = computed(() => {
  if (hasTools.value) return true

  const text = props.msg.segments
    ? props.msg.segments.filter(s => s.type === 'text').map(s => s.content || '').join('\n')
    : props.msg.content || ''

  return /```|<pre[\s>]|<table[\s>]|^\s*\|.+\|\s*$/im.test(text)
})

watch(() => props.msg.streaming, (newVal, oldVal) => {
  if (newVal === true) workExpanded.value = true
  if (oldVal === true && newVal === false) {
    workExpanded.value = false
    Object.keys(expandedReasoning).forEach(key => delete expandedReasoning[key])
  }
})

function toggleWork() {
  if (props.msg.streaming) return
  workExpanded.value = !workExpanded.value
}

function expanded(toolCallId) {
  return props.msg.expandedTools?.[toolCallId] || false
}

function reasoningKey(segment, number) {
  return segment.reasoning_id || `reasoning-${number}`
}

function reasoningExpanded(segment, number) {
  return expandedReasoning[reasoningKey(segment, number)] || false
}

function toggleReasoning(segment, number) {
  const key = reasoningKey(segment, number)
  expandedReasoning[key] = !expandedReasoning[key]
}

function toggleExpand(toolCallId) {
  if (!props.msg.expandedTools) props.msg.expandedTools = {}
  props.msg.expandedTools[toolCallId] = !props.msg.expandedTools[toolCallId]
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
  return Boolean(finalAnswerText(props.msg.segments).trim())
})

function getPlainText() {
  const text = props.msg.segments
    ? finalAnswerText(props.msg.segments)
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
    setDesktopPetState('speaking', themeStore.current)
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
  setDesktopPetState('idle', themeStore.current)
}

function stopSpeech() {
  playbackRun += 1
  releaseAudio()
  if (browserUtterance) cancelBrowserSpeech()
  browserUtterance = null
  isPlaying.value = false
  setDesktopPetState('idle', themeStore.current)
}

onBeforeUnmount(() => {
  stopReasoningClock()
  stopSpeech()
})
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

.agent-work {
  margin: 2px 0 8px;
  color: var(--text-secondary);
  font-size: 12px;
  border: 1px solid rgba(124, 92, 252, 0.22);
  border-radius: 6px;
  background: rgba(124, 92, 252, 0.06);
}
.agent-work-header {
  width: 100%;
  min-height: 30px;
  padding: 4px 9px;
  display: flex;
  align-items: center;
  gap: 7px;
  border: none;
  background: transparent;
  color: inherit;
  cursor: pointer;
  text-align: left;
}
.agent-work-header:hover { color: var(--primary); }
.agent-work-header:disabled { cursor: default; }
.agent-work-header:disabled:hover { color: inherit; }
.agent-work-label { color: var(--text-primary); font-weight: 600; }
.agent-work-meta { color: var(--text-secondary); font-size: 11px; }
.agent-work-arrow { margin-left: auto; transition: transform var(--motion-fast) var(--ease-standard); }
.agent-work-arrow.open { transform: rotate(180deg); }
.agent-work[data-status="running"] .agent-work-header { color: var(--primary); }
.agent-work[data-status="error"] .agent-work-header,
.agent-work[data-status="stopped"] .agent-work-header { color: #f59e0b; }
.agent-work-content {
  max-height: 520px;
  margin: 0 8px 8px;
  padding: 6px 0 4px 12px;
  overflow: auto;
  border-left: 1px solid rgba(255, 255, 255, 0.16);
  line-height: 1.65;
}
.work-reasoning {
  padding: 4px 0 8px;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
}
.work-reasoning + .work-reasoning,
.work-reasoning + .work-text,
.work-reasoning + .tool-seg,
.work-text + .work-reasoning,
.work-text + .tool-seg,
.tool-seg + .work-reasoning,
.tool-seg + .work-text { margin-top: 10px; }
.work-reasoning[data-status="running"] { color: var(--primary); }
.work-reasoning[data-status="unavailable"],
.work-reasoning[data-status="error"] { color: #f59e0b; }
.work-entry-header {
  width: 100%;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 4px;
  color: var(--text-tertiary, var(--text-secondary));
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 11px;
  text-align: left;
}
.work-entry-header:hover { color: var(--primary); }
.work-entry-header span:first-child { flex: 1; }
.work-entry-arrow { flex: 0 0 auto; transition: transform var(--motion-fast) var(--ease-standard); }
.work-entry-arrow.open { transform: rotate(180deg); }
.work-reasoning-text { white-space: pre-wrap; }
.work-text { color: var(--text-secondary); }

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
