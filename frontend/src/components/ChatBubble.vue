<template>
  <div class="bubble-row" :class="msg.role">
    <div class="bubble" :class="msg.role">
      <!-- 旧消息兼容 -->
      <template v-if="!msg.segments">
        <div class="text-seg" v-html="renderText(msg.content || '')"></div>
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
          <div v-if="seg.type === 'tool'" class="tool-seg" :data-status="seg.status">
            <div class="tool-header">
              <span class="tool-icon">{{ toolIcon(seg.tool_name) }}</span>
              <span class="tool-name">{{ seg.tool_name }}</span>
              <span class="tool-args">{{ summarizeArgs(seg.tool_args) }}</span>
              <span class="tool-status">
                <span v-if="seg.status === 'running'" class="spinner">⏳</span>
                <span v-if="seg.status === 'done'">✅</span>
                <span v-if="seg.status === 'error'">❌</span>
              </span>
            </div>
            <div class="tool-summary" v-if="seg.result_summary">{{ seg.result_summary }}</div>
            <div class="tool-detail" v-if="expanded(seg.tool_call_id)">
              <pre v-if="seg.tool_name === 'code_exec'"><code>{{ seg.result_detail }}</code></pre>
              <div v-else-if="seg.tool_name === 'web_search'" v-html="formatSearchResults(seg.result_detail)"></div>
              <pre v-else>{{ seg.result_detail }}</pre>
            </div>
            <div class="tool-actions">
              <button class="tool-expand" @click="toggleExpand(seg.tool_call_id)" v-if="seg.result_detail">
                {{ expanded(seg.tool_call_id) ? '收起' : '展开详情' }}
              </button>
              <button class="tool-retry" v-if="seg.status === 'error'" @click="$emit('retry')">
                重试
              </button>
            </div>
          </div>
        </template>
      </template>

      <span v-if="msg.emoji" class="emoji">{{ msg.emoji }}</span>
      <span v-if="msg.streaming" class="streaming-indicator">●</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

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

function renderText(content) {
  // 简单 Markdown：代码块、粗体、链接
  let html = content
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
  return html
}

function formatSearchResults(detail) {
  if (!detail) return ''
  // 尝试解析为链接列表
  const lines = detail.split('\n').filter(l => l.trim())
  return lines.map(line => {
    const urlMatch = line.match(/(https?:\/\/[^\s]+)/)
    if (urlMatch) {
      return `<div class="search-result"><a href="${urlMatch[1]}" target="_blank">${line}</a></div>`
    }
    return `<div class="search-result">${line}</div>`
  }).join('')
}
</script>

<style scoped>
.bubble-row { display: flex; margin: 8px 16px; }
.bubble-row.user { justify-content: flex-end; }
.bubble-row.assistant { justify-content: flex-start; }
.bubble {
  max-width: 80%; padding: var(--bubble-padding); border-radius: var(--bubble-radius);
  box-shadow: var(--bubble-shadow); border: var(--bubble-border); position: relative;
}
.bubble.user { background: var(--bubble-user); }
.bubble.assistant { background: var(--bubble-agent); }
.text-seg { line-height: var(--line-height); font-size: var(--font-size-base); word-break: break-word; }
.text-seg :deep(pre) { background: rgba(0,0,0,0.2); padding: 8px; border-radius: 4px; overflow-x: auto; margin: 8px 0; font-size: 12px; }
.text-seg :deep(code) { background: rgba(0,0,0,0.15); padding: 1px 4px; border-radius: 3px; font-size: 0.9em; }
.text-seg :deep(a) { color: var(--primary); text-decoration: none; }

.tool-actions-bar { display: flex; justify-content: flex-end; margin-bottom: 4px; }
.tool-toggle-all { background: none; border: none; color: var(--text-secondary); cursor: pointer; font-size: 11px; }

.tool-seg {
  margin: 8px 0; padding: 8px 12px;
  background: rgba(124, 92, 252, 0.08);
  border-left: 3px solid var(--primary);
  border-radius: 0 8px 8px 0;
  font-size: 13px; position: relative;
}
/* 连续 tool 段连接线 */
.tool-seg + .tool-seg::before {
  content: ''; position: absolute;
  left: -3px; top: -8px; width: 3px; height: 8px;
  background: var(--primary);
}
/* 状态配色 */
.tool-seg[data-status="running"] { border-left-color: #3b82f6; }
.tool-seg[data-status="running"] + .tool-seg::before { background: #3b82f6; }
.tool-seg[data-status="done"] { border-left-color: #22c55e; }
.tool-seg[data-status="done"] + .tool-seg::before { background: #22c55e; }
.tool-seg[data-status="error"] { border-left-color: #ef4444; }
.tool-seg[data-status="error"] + .tool-seg::before { background: #ef4444; }

.tool-header { display: flex; align-items: center; gap: 6px; }
.tool-icon { font-size: 14px; }
.tool-name { font-weight: 600; color: var(--primary); }
.tool-args { color: var(--text-secondary); font-size: 12px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tool-status { flex-shrink: 0; }
.tool-summary { margin-top: 4px; color: var(--text-secondary); font-size: 12px; }
.tool-detail { margin-top: 8px; padding: 8px; background: var(--bg-primary); border-radius: 4px; font-size: 12px; max-height: 200px; overflow-y: auto; }
.tool-detail pre { margin: 0; white-space: pre-wrap; word-break: break-all; }
.tool-actions { margin-top: 4px; display: flex; gap: 8px; }
.tool-expand, .tool-retry { background: none; border: none; color: var(--primary); cursor: pointer; font-size: 12px; }
.tool-retry { color: #ef4444; }
.search-result { padding: 2px 0; }
.search-result a { color: var(--primary); text-decoration: none; }
.search-result a:hover { text-decoration: underline; }

.spinner { animation: spin 1s linear infinite; display: inline-block; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.streaming-indicator { animation: blink 1s infinite; color: var(--primary); margin-left: 4px; }
@keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }
.emoji { font-size: 20px; position: absolute; bottom: -4px; right: -4px; }
</style>
