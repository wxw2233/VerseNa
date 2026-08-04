<template>
  <div class="tab-content">
    <h2>工具</h2>
    <p class="tab-desc">Agent 可以自动调用以下工具来完成任务。</p>

    <div class="workspace-row">
      <span class="workspace-label">工具工作区</span>
      <code :title="workspace">{{ workspace || '加载中...' }}</code>
    </div>

    <div class="tool-list">
      <div v-for="tool in tools" :key="tool.name" class="tool-card">
        <div class="tool-icon">{{ toolIcons[tool.name] || '🔧' }}</div>
        <div class="tool-info">
          <div class="tool-name">{{ tool.name }}</div>
          <div class="tool-desc">{{ tool.description }}</div>
        </div>
        <span class="tool-badge builtin">内置</span>
      </div>
      <div v-if="tools.length === 0" class="empty-hint">加载中...</div>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const tools = ref([])
const workspace = ref('')

const toolIcons = {
  web_search: '🔍',
  web_fetch: '🌐',
  code_exec: '💻',
  file_manager: '📁',
  save_memory: '🧠',
  datetime: '🕐',
  calculator: '🧮',
}

async function loadTools() {
  try {
    const resp = await fetch('/api/tools')
    tools.value = await resp.json()
  } catch { tools.value = [] }
}

async function loadWorkspace() {
  try {
    const resp = await fetch('/api/tools/workspace')
    const data = await resp.json()
    workspace.value = data.path || ''
  } catch { workspace.value = '' }
}

onMounted(() => {
  loadTools()
  loadWorkspace()
})
</script>

<style scoped>
.tab-desc { font-size: 13px; color: var(--text-secondary); margin-bottom: 16px; }

.workspace-row {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  padding: 10px 0 16px;
}
.workspace-label {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--text-secondary);
}
.workspace-row code {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: var(--text-primary);
}

.tool-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.tool-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 18px;
  background: rgba(20, 20, 40, 0.45);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  transition: box-shadow 0.2s;
}
.tool-card:hover {
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.18);
}
.tool-icon {
  font-size: 22px;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(20, 20, 40, 0.60);
  border-radius: 8px;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.12);
  flex-shrink: 0;
}
.tool-info { flex: 1; min-width: 0; }
.tool-name {
  font-size: 14px;
  font-weight: 600;
  font-family: monospace;
  color: var(--text-primary);
}
.tool-desc {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
  line-height: 1.4;
}
.tool-badge {
  font-size: 11px;
  padding: 2px 10px;
  border-radius: 10px;
  background: rgba(124, 92, 252, 0.12);
  color: var(--primary);
  font-weight: 600;
  flex-shrink: 0;
}

.empty-hint {
  text-align: center;
  padding: 24px;
  color: var(--text-secondary);
  font-size: 14px;
}

</style>
