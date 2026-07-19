<template>
  <div class="tab-content">
    <h2>工具</h2>
    <p class="tab-desc">Agent 可以自动调用以下工具来完成任务。</p>

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

    <hr class="divider" />
    <h3>信任模式</h3>
    <div class="trust-mode-row">
      <div class="trust-info">
        <div class="trust-label">🔒 信任模式</div>
        <div class="trust-desc">开启后，除系统核心文件外，所有文件操作无需确认直接执行。</div>
      </div>
      <label class="toggle-switch">
        <input type="checkbox" v-model="trustMode" @change="saveTrustMode" />
        <span class="toggle-slider"></span>
      </label>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const tools = ref([])
const trustMode = ref(false)

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

async function loadTrustMode() {
  try {
    const resp = await fetch('/api/config/trust_mode')
    const data = await resp.json()
    trustMode.value = data.enabled === true || data.enabled === 'true'
  } catch { trustMode.value = false }
}

async function saveTrustMode() {
  try {
    await fetch('/api/config/trust_mode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: trustMode.value })
    })
  } catch {}
}

onMounted(() => {
  loadTools()
  loadTrustMode()
})
</script>

<style scoped>
.tab-desc { font-size: 13px; color: var(--text-secondary); margin-bottom: 16px; }

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

.divider {
  border: none;
  box-shadow: 0 -1px 0 rgba(255, 255, 255, 0.04);
  margin: 24px 0;
  height: 1px;
}

.trust-mode-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  background: rgba(20, 20, 40, 0.45);
  border-radius: 10px;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.08);
}
.trust-label { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.trust-desc { font-size: 12px; color: var(--text-secondary); margin-top: 4px; }
.toggle-switch {
  position: relative;
  width: 44px;
  height: 24px;
  flex-shrink: 0;
}
.toggle-switch input { opacity: 0; width: 0; height: 0; }
.toggle-slider {
  position: absolute;
  cursor: pointer;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(255,255,255,0.12);
  border-radius: 12px;
  transition: 0.2s;
}
.toggle-slider::before {
  content: '';
  position: absolute;
  height: 18px; width: 18px;
  left: 3px; bottom: 3px;
  background: white;
  border-radius: 50%;
  transition: 0.2s;
}
.toggle-switch input:checked + .toggle-slider { background: var(--primary); }
.toggle-switch input:checked + .toggle-slider::before { transform: translateX(20px); }

h3 {
  font-size: 16px;
  margin-bottom: 12px;
}
</style>
