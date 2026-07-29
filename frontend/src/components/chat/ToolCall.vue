<template>
  <div class="tool-seg" :data-status="status" @click="toggleExpand">
    <div class="tool-header">
      <span class="tool-icon">{{ toolIcon }}</span>
      <span class="tool-name">{{ toolName }}</span>
      <span class="tool-args">{{ summarizedArgs }}</span>
      <span class="tool-status">
        <span v-if="status === 'running'" class="spinner">⏳</span>
        <span v-if="status === 'done'">✅</span>
        <span v-if="status === 'error'">❌</span>
      </span>
      <span v-if="hasDetail" class="tool-arrow" :class="{ open: expanded }">▶</span>
      <button v-if="status === 'error'" class="tool-retry" @click.stop="$emit('retry')">重试</button>
    </div>
    <div class="tool-summary" v-if="summary && !expanded">{{ summary }}</div>
    <div class="tool-detail" v-if="expanded">
      <pre v-if="toolName === 'code_exec'"><code>{{ detail }}</code></pre>
      <div v-else-if="toolName === 'web_search'" v-html="formattedSearchResults"></div>
      <pre v-else>{{ detail }}</pre>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  toolName: {
    type: String,
    required: true
  },
  toolArgs: {
    type: Object,
    default: () => ({})
  },
  status: {
    type: String,
    default: 'running'
  },
  summary: {
    type: String,
    default: ''
  },
  detail: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['retry'])
const expanded = ref(false)

const toolIcon = computed(() => {
  const icons = {
    'web_search': '🔍',
    'code_exec': '💻',
    'file_manager': '📁',
    'save_memory': '💾',
    'calculator': '🧮',
    'datetime': '📅',
    'web_fetch': '🌐',
  }
  return icons[props.toolName] || '🔧'
})

const summarizedArgs = computed(() => {
  if (!props.toolArgs || Object.keys(props.toolArgs).length === 0) return ''
  const args = props.toolArgs
  if (props.toolName === 'web_search') return args.query || ''
  if (props.toolName === 'code_exec') return args.code ? args.code.slice(0, 50) + '...' : ''
  if (props.toolName === 'file_manager') return args.path || ''
  return Object.values(args)[0]?.toString().slice(0, 30) || ''
})

const hasDetail = computed(() => {
  return props.detail && props.detail.length > 0
})

const formattedSearchResults = computed(() => {
  if (props.toolName !== 'web_search' || !props.detail) return ''
  try {
    const results = JSON.parse(props.detail)
    return results.map(r => `
      <div class="search-result">
        <a href="${r.url}" target="_blank" rel="noopener">${r.title}</a>
        <p>${r.snippet}</p>
      </div>
    `).join('')
  } catch {
    return props.detail
  }
})

function toggleExpand() {
  if (hasDetail.value) {
    expanded.value = !expanded.value
  }
}
</script>

<style scoped>
.tool-seg {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  padding: 8px 12px;
  margin: 4px 0;
  cursor: pointer;
  transition: background 0.2s;
}

.tool-seg:hover {
  background: rgba(255, 255, 255, 0.05);
}

.tool-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.tool-icon {
  font-size: 16px;
}

.tool-name {
  font-weight: 500;
  color: var(--text-primary);
}

.tool-args {
  color: var(--text-secondary);
  font-family: monospace;
  font-size: 12px;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-status {
  margin-left: auto;
}

.spinner {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.tool-arrow {
  font-size: 10px;
  transition: transform 0.2s;
}

.tool-arrow.open {
  transform: rotate(90deg);
}

.tool-retry {
  background: rgba(255, 0, 0, 0.2);
  color: #ff4444;
  border: none;
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.2s;
}

.tool-retry:hover {
  background: rgba(255, 0, 0, 0.3);
}

.tool-summary {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-secondary);
  padding-left: 24px;
}

.tool-detail {
  margin-top: 8px;
  padding: 8px 12px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
  font-size: 12px;
  overflow-x: auto;
}

.tool-detail pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.tool-detail code {
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
}

/* 搜索结果样式 */
:deep(.search-result) {
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

:deep(.search-result:last-child) {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

:deep(.search-result a) {
  color: var(--primary);
  text-decoration: none;
  font-weight: 500;
}

:deep(.search-result a:hover) {
  text-decoration: underline;
}

:deep(.search-result p) {
  margin: 4px 0 0 0;
  color: var(--text-secondary);
  font-size: 12px;
}
</style>
