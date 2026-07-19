<template>
  <div class="bubble-row" :class="msg.role">
    <div class="bubble" :class="msg.role">
      <!-- 旧消息兼容 -->
      <template v-if="!msg.segments">
        <div v-if="msg.image" class="image-msg">
          <img :src="msg.image.dataUrl || msg.image.url" :alt="msg.image.filename" />
        </div>
        <div v-if="msg.file" class="file-msg">
          <span class="file-icon">📄</span>
          <span class="file-name">{{ msg.file.filename }}</span>
        </div>
        <div v-if="msg.content" class="text-seg" v-html="renderText(msg.content)"></div>
      </template>

      <!-- 新消息 segments 渲染 -->
      <template v-else>
        <div v-if="hasTools" class="tool-actions-bar">
          <button class="tool-toggle-all" @click="toggleAll">
            {{ allExpanded ? '折叠全部工具' : '展开全部工具' }}
          </button>
        </div>

        <template v-for="(seg, i) in msg.segments" :key="i">
          <!-- 文本段 -->
          <div v-if="seg.type === 'text'" class="text-seg" v-html="renderText(seg.content)"></div>

          <!-- 工具段时间线节点 -->
          <div v-if="seg.type === 'tool'" class="tool-seg" :data-status="seg.status" @click="seg.result_detail ? toggleExpand(seg.tool_call_id) : null">
            <div class="tool-header">
              <span class="tool-icon">{{ toolIcon(seg.tool_name) }}</span>
              <span class="tool-name">{{ seg.tool_name }}</span>
              <span class="tool-args">{{ summarizeArgs(seg.tool_args) }}</span>
              <span class="tool-status">
                <span v-if="seg.status === 'running'" class="spinner">⏳</span>
                <span v-if="seg.status === 'done'">✅</span>
                <span v-if="seg.status === 'error'">❌</span>
              </span>
              <span v-if="seg.result_detail" class="tool-arrow" :class="{ open: expanded(seg.tool_call_id) }">▼</span>
              <button v-if="seg.status === 'error'" class="tool-retry" @click.stop="$emit('retry')">重试</button>
            </div>
            <div class="tool-summary" v-if="seg.result_summary && !expanded(seg.tool_call_id)">{{ seg.result_summary }}</div>
            <div class="tool-detail" v-if="expanded(seg.tool_call_id)">
              <pre v-if="seg.tool_name === 'code_exec'"><code>{{ seg.result_detail }}</code></pre>
              <div v-else-if="seg.tool_name === 'web_search'" v-html="formatSearchResults(seg.result_detail)"></div>
              <pre v-else>{{ seg.result_detail }}</pre>
            </div>
          </div>
        </template>
      </template>

      <span v-if="msg.emoji" class="emoji">{{ msg.emoji }}</span>
      <span v-if="msg.streaming" class="streaming-indicator">●</span>
    </div>
    <!-- TTS 播放按钮（仅 assistant 消息） -->
    <button
      v-if="msg.role === 'assistant' && !msg.streaming && hasTextContent"
      class="tts-btn"
      :class="{ playing: isPlaying }"
      @click="speakText"
      title="语音播放"
    >{{ isPlaying ? '🔊' : '🔈' }}</button>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { marked } from 'marked'
import { useSessionStore } from '../stores/session'
import { useThemeStore } from '../stores/theme'

const sessionStore = useSessionStore()
const themeStore = useThemeStore()

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
const emit = defineEmits(['retry'])

const hasTools = computed(() =>
  props.msg.segments?.some(s => s.type === 'tool')
)

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

const hasTextContent = computed(() => {
  if (!props.msg.segments) return !!props.msg.content
  return props.msg.segments.some(s => s.type === 'text' && s.content?.trim())
})

function stripActions(text) {
  return text
    .replace(/\*[^*]+\*/g, '')
    .replace(/（[^）]+）/g, '')
    .replace(/\([^)]+\)/g, '')
    .replace(/【[^】]+】/g, '')
    .replace(/\n{2,}/g, '\n')
    .trim()
}

function getPlainText() {
  if (!props.msg.segments) return props.msg.content || ''
  return stripActions(
    props.msg.segments
      .filter(s => s.type === 'text')
      .map(s => s.content)
      .join('')
      .replace(/<[^>]+>/g, '')
  )
}

async function speakText() {
  const text = getPlainText()
  if (!text) return

  // 如果正在播放，停止
  if (isPlaying.value && audioEl) {
    audioEl.pause()
    audioEl = null
    isPlaying.value = false
    return
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
      isPlaying.value = false
      return
    }

    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    audioEl = new Audio(url)
    audioEl.onended = () => {
      isPlaying.value = false
      URL.revokeObjectURL(url)
    }
    audioEl.onerror = () => {
      isPlaying.value = false
      URL.revokeObjectURL(url)
    }
    audioEl.play()
  } catch {
    isPlaying.value = false
  }
}
</script>

<style scoped>
.bubble-row { display: flex; margin: 8px 16px; }
.bubble-row.user { justify-content: flex-end; }
.bubble-row.assistant { justify-content: flex-start; }

/* L3: Chat bubbles — 微毛玻璃 + 自适应描边 */
.bubble {
  max-width: 80%;
  padding: var(--bubble-padding);
  position: relative;
  border-radius: var(--radius);
  background: rgba(10, 10, 24, 0.60);
  border: none;
  box-shadow: var(--bubble-border);
  backdrop-filter: blur(1px);
  -webkit-backdrop-filter: blur(1px);
}

/* Asymmetric bottom radius: user bubble bottom-right 8px */
.bubble.user {
  background: rgba(20, 20, 40, 0.65);
  border-bottom-right-radius: 8px;
}

/* Asymmetric bottom radius: assistant bubble bottom-left 8px */
.bubble.assistant {
  background: rgba(20, 20, 40, 0.60);
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
.file-icon { font-size: 20px; flex-shrink: 0; }
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

.tool-header { display: flex; align-items: center; gap: 4px; flex-wrap: nowrap; }
.tool-icon { font-size: 12px; flex-shrink: 0; }
.tool-name { font-weight: 600; color: var(--primary); font-size: 11px; flex-shrink: 0; }
.tool-args { color: var(--text-secondary); font-size: 11px; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tool-status { flex-shrink: 0; font-size: 11px; }
.tool-arrow {
  flex-shrink: 0;
  font-size: 9px;
  color: var(--text-secondary);
  transition: transform 0.2s;
  cursor: pointer;
  padding: 0 2px;
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
  padding: 3px 8px;
  background: transparent;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-size: 14px;
  color: var(--text-secondary);
  opacity: 0.5;
  transition: all 0.2s;
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
</style>
