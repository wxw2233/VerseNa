<template>
  <div class="tab-content">
    <h2>运行监控</h2>
    <div class="monitor-toolbar">
      <button @click="fetchLogs" class="monitor-btn">🔄 刷新</button>
      <button @click="clearLogs" class="monitor-btn btn-danger">🗑 清空日志</button>
      <label class="monitor-auto">
        <input type="checkbox" v-model="autoRefresh" /> 自动刷新（3s）
      </label>
      <span class="monitor-count">共 {{ logLines.length }} 行</span>
    </div>
    <div class="monitor-log" ref="logRef">
      <div v-for="(line, i) in logLines" :key="i" class="log-line" :class="logLevel(line)">
        {{ line }}
      </div>
      <div v-if="!logLines.length" class="log-empty">暂无日志</div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'

const logLines = ref([])
const logRef = ref(null)
const autoRefresh = ref(false)
let monitorTimer = null

function scrollToBottom() {
  nextTick(() => {
    if (logRef.value) logRef.value.scrollTop = logRef.value.scrollHeight
  })
}

async function fetchLogs() {
  try {
    const resp = await fetch('/api/logs?lines=200')
    const data = await resp.json()
    logLines.value = data.lines || []
    scrollToBottom()
  } catch { logLines.value = [] }
}

async function clearLogs() {
  await fetch('/api/logs', { method: 'DELETE' })
  logLines.value = []
}

function logLevel(line) {
  if (line.includes('[ERROR]')) return 'log-error'
  if (line.includes('[WARN]')) return 'log-warn'
  return 'log-info'
}

watch(autoRefresh, (val) => {
  if (val) {
    fetchLogs()
    monitorTimer = setInterval(fetchLogs, 3000)
  } else {
    if (monitorTimer) clearInterval(monitorTimer)
  }
})

onMounted(() => fetchLogs())
</script>

<style scoped>
.monitor-toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.monitor-btn {
  padding: 6px 12px;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
  border-radius: 6px;
  background: rgba(20, 20, 40, 0.60);
  color: var(--text-primary);
  cursor: pointer;
  font-size: 12px;
  border: none;
  transition: filter 0.2s, transform 0.2s;
}
.monitor-btn:hover {
  filter: brightness(1.08);
  transform: translateY(-1px);
}
.monitor-auto { display: flex; align-items: center; gap: 4px; font-size: 12px; color: var(--text-secondary); cursor: pointer; }
.monitor-count { font-size: 12px; color: var(--text-secondary); margin-left: auto; }
.monitor-log {
  background: #0d1117;
  border-radius: var(--radius);
  padding: 12px;
  max-height: calc(100vh - 260px);
  overflow-y: auto;
  font-family: 'Cascadia Code', 'Fira Code', monospace;
  font-size: 12px;
  line-height: 1.6;
}
.log-line { padding: 1px 0; white-space: pre-wrap; word-break: break-all; }
.log-info { color: #8b949e; }
.log-warn { color: #d29922; }
.log-error { color: #f85149; }
.log-empty { color: #484f58; text-align: center; padding: 40px; }
.btn-danger { color: #ef4444 !important; }
</style>
