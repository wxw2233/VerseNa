<template>
  <div class="file-msg" @click="toggleExpand">
    <div class="file-header">
      <span class="file-icon">{{ fileIcon }}</span>
      <div class="file-info">
        <span class="file-name">{{ filename }}</span>
        <span class="file-size" v-if="size">{{ formatSize(size) }}</span>
      </div>
      <span class="file-expand" v-if="hasPreview">{{ expanded ? '▼' : '?' }}</span>
    </div>
    <div v-if="expanded && hasPreview" class="file-preview">
      <pre v-if="textPreview">{{ textPreview }}</pre>
      <div v-else class="no-preview">无法预览此文件类型</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  filename: {
    type: String,
    required: true
  },
  size: {
    type: Number,
    default: null
  },
  textPreview: {
    type: String,
    default: ''
  },
  fullText: {
    type: String,
    default: ''
  }
})

const expanded = ref(false)

const fileIcon = computed(() => {
  const ext = props.filename.split('.').pop()?.toLowerCase()
  const icons = {
    'txt': '📄',
    'md': '📝',
    'py': '🐍',
    'js': '📜',
    'json': '📋',
    'csv': '📊',
    'pdf': '📕',
    'docx': '📘',
    'xlsx': '📗',
    'pptx': '📙',
    'zip': '📦',
    'rar': '📦',
    '7z': '📦',
  }
  return icons[ext] || '📄'
})

const hasPreview = computed(() => {
  return props.textPreview || props.fullText
})

function toggleExpand() {
  if (hasPreview.value) {
    expanded.value = !expanded.value
  }
}

function formatSize(bytes) {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}
</script>

<style scoped>
.file-msg {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: background 0.2s;
  max-width: 300px;
}

.file-msg:hover {
  background: rgba(255, 255, 255, 0.08);
}

.file-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.file-icon {
  font-size: 24px;
  flex-shrink: 0;
}

.file-info {
  flex: 1;
  min-width: 0;
}

.file-name {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.file-expand {
  font-size: 10px;
  color: var(--text-secondary);
  transition: transform 0.2s;
}

.file-preview {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.file-preview pre {
  background: rgba(0, 0, 0, 0.3);
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  max-height: 200px;
  overflow-y: auto;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.no-preview {
  text-align: center;
  color: var(--text-secondary);
  font-size: 12px;
  padding: 8px;
}

/* 移动端样式 */
@media (max-width: 767px) {
  .file-msg {
    max-width: 250px;
  }
}
</style>
