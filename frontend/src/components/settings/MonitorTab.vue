<template>
  <div class="tab-content">
    <h2>运行监控</h2>
    <div class="monitor-toolbar">
      <button @click="refreshAll" class="monitor-btn">刷新</button>
      <button @click="clearLogs" class="monitor-btn btn-danger">清空日志</button>
      <label class="monitor-auto">
        <input type="checkbox" v-model="autoRefresh" /> 自动刷新（3 秒）
      </label>
      <span class="monitor-count">共 {{ logLines.length }} 行</span>
    </div>

    <div class="diagnostic-grid">
      <div class="diagnostic-card">
        <span class="diagnostic-label">当前工作区记忆</span>
        <strong>{{ diagnostics.memory?.workspace ?? 0 }}</strong>
        <small>全局 {{ diagnostics.memory?.global ?? 0 }} 条</small>
      </div>
      <div class="diagnostic-card">
        <span class="diagnostic-label">工具调用</span>
        <strong>{{ runtimeTotals.toolCalls }}</strong>
        <small>失败 {{ runtimeTotals.failures }} 次</small>
      </div>
      <div class="diagnostic-card">
        <span class="diagnostic-label">重复调用拦截</span>
        <strong>{{ runtimeTotals.repeated }}</strong>
        <small>保护 Agent 不陷入循环</small>
      </div>
      <div class="diagnostic-card">
        <span class="diagnostic-label">子代理</span>
        <strong>{{ diagnostics.active_subagents?.length || 0 }}</strong>
        <small>{{ diagnostics.active_subagents?.length ? '正在执行' : '当前空闲' }}</small>
      </div>
      <div class="diagnostic-card">
        <span class="diagnostic-label">上下文估算</span>
        <strong>{{ runtimeTotals.contextTokens }}</strong>
        <small>token，消息 {{ runtimeTotals.contextMessages }}</small>
      </div>
    </div>

    <div v-if="runtimeStates.length" class="runtime-list">
      <div v-for="state in runtimeStates" :key="state.session_id" class="runtime-row">
        <span class="runtime-status" :class="{ active: state.active }"></span>
        <code>{{ state.session_id }}</code>
        <span>{{ state.active ? '运行中' : '已结束' }}</span>
        <span>工具 {{ state.tool_calls_total }}</span>
        <span v-if="state.last_compaction">最近压缩 {{ state.last_compaction.at }}</span>
      </div>
    </div>

    <div v-if="diagnostics.tasks?.length" class="task-list">
      <div v-for="task in diagnostics.tasks" :key="task.session_id" class="task-row">
        <div class="task-row-main">
          <strong>{{ task.name || task.session_id }}</strong>
          <span class="task-phase" :class="task.status">{{ task.phase }}</span>
          <span v-if="!task.recovery_ok" class="task-warning">需要恢复核对</span>
        </div>
        <small>已验证 {{ task.acceptance?.verified?.length || 0 }} · 待完成 {{ task.acceptance?.pending?.length || 0 }} · 未验证 {{ task.acceptance?.unverified?.length || 0 }}</small>
        <div v-if="task.recovery_findings?.length" class="task-findings">
          {{ task.recovery_findings[0].message }}
        </div>
        <div v-else-if="task.context_conflicts?.length" class="task-findings">
          {{ task.context_conflicts[0].message }}
        </div>
      </div>
    </div>

    <div v-if="diagnostics.skill_events?.length" class="skill-audit-list">
      <div class="skill-audit-title">最近技能审计</div>
      <div v-for="event in diagnostics.skill_events.slice(0, 8)" :key="event.id" class="skill-audit-row">
        <span class="skill-audit-event" :data-event="event.event_type">{{ skillEventLabel(event.event_type) }}</span>
        <strong>{{ event.skill_id }}</strong>
        <code v-if="event.command">/{{ event.command }}</code>
        <small>{{ formatTime(event.created_at) }}</small>
      </div>
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
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'

const logLines = ref([])
const logRef = ref(null)
const autoRefresh = ref(false)
const diagnostics = ref({ memory: {}, runtime: {}, active_subagents: [] })
let monitorTimer = null

const runtimeStates = computed(() => Object.values(diagnostics.value.runtime || {}))
const runtimeTotals = computed(() => runtimeStates.value.reduce((total, state) => ({
  toolCalls: total.toolCalls + Number(state.tool_calls_total || 0),
  failures: total.failures + Number(state.tool_failures || 0),
  repeated: total.repeated + Number(state.repeated_blocks || 0),
  contextTokens: Math.max(total.contextTokens, Number(state.context_tokens || 0)),
  contextMessages: Math.max(total.contextMessages, Number(state.context_messages || 0)),
}), { toolCalls: 0, failures: 0, repeated: 0, contextTokens: 0, contextMessages: 0 }))

function scrollToBottom() {
  nextTick(() => {
    if (logRef.value) logRef.value.scrollTop = logRef.value.scrollHeight
  })
}

async function fetchLogs() {
  try {
    const response = await fetch('/api/logs?lines=200')
    const data = await response.json()
    logLines.value = data.lines || []
    scrollToBottom()
  } catch {
    logLines.value = []
  }
}

async function fetchDiagnostics() {
  try {
    const response = await fetch('/api/diagnostics')
    if (response.ok) diagnostics.value = await response.json()
  } catch {}
}

async function refreshAll() {
  await Promise.all([fetchLogs(), fetchDiagnostics()])
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

function skillEventLabel(eventType) {
  return ({ loaded: '已加载', activated: '已激活', adopted: '已采用', cleared: '已关闭' })[eventType] || eventType
}

function formatTime(value) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('zh-CN')
}

watch(autoRefresh, (enabled) => {
  if (enabled) {
    refreshAll()
    monitorTimer = setInterval(refreshAll, 3000)
  } else if (monitorTimer) {
    clearInterval(monitorTimer)
    monitorTimer = null
  }
})

onMounted(refreshAll)
onBeforeUnmount(() => {
  if (monitorTimer) clearInterval(monitorTimer)
})
</script>

<style scoped>
.monitor-toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.monitor-btn { padding: 6px 12px; box-shadow: 0 0 0 1px rgba(255,255,255,0.20); border-radius: 6px; background: rgba(20,20,40,0.60); color: var(--text-primary); cursor: pointer; font-size: 12px; border: none; }
.monitor-auto { display: flex; align-items: center; gap: 4px; font-size: 12px; color: var(--text-secondary); cursor: pointer; }
.monitor-count { font-size: 12px; color: var(--text-secondary); margin-left: auto; }
.diagnostic-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-bottom: 12px; }
.diagnostic-card { display: flex; flex-direction: column; gap: 4px; min-width: 0; padding: 12px 14px; border-radius: 8px; background: rgba(20,20,40,0.48); box-shadow: 0 0 0 1px rgba(255,255,255,0.10); }
.diagnostic-label { color: var(--text-secondary); font-size: 11px; }
.diagnostic-card strong { color: var(--text-primary); font-size: 22px; font-variant-numeric: tabular-nums; }
.diagnostic-card small { color: var(--text-secondary); font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.runtime-list { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
.runtime-row { display: flex; align-items: center; gap: 10px; min-width: 0; padding: 7px 10px; color: var(--text-secondary); font-size: 11px; background: rgba(20,20,40,0.34); border-radius: 6px; }
.runtime-row code { min-width: 120px; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.runtime-status { width: 7px; height: 7px; flex: 0 0 7px; border-radius: 50%; background: #71717a; }
.runtime-status.active { background: #4ade80; box-shadow: 0 0 8px rgba(74,222,128,0.75); }
.task-list { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
.task-row { padding: 9px 10px; border-radius: 6px; background: rgba(20,20,40,0.34); color: var(--text-secondary); font-size: 11px; }
.task-row-main { display: flex; align-items: center; gap: 8px; min-width: 0; }
.task-row-main strong { color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.task-phase { padding: 2px 6px; border-radius: 4px; background: rgba(255,255,255,0.08); }
.task-phase.completed { color: #4ade80; } .task-phase.blocked { color: #f87171; } .task-phase.validating { color: #facc15; }
.task-warning { color: #facc15; }
.task-row small { display: block; margin-top: 4px; }
.task-findings { margin-top: 4px; color: #fca5a5; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.skill-audit-list { display: flex; flex-direction: column; gap: 5px; margin-bottom: 12px; }
.skill-audit-title { color: var(--text-secondary); font-size: 11px; }
.skill-audit-row { display: flex; align-items: center; gap: 7px; min-width: 0; padding: 7px 10px; border-radius: 6px; color: var(--text-secondary); background: rgba(20,20,40,0.34); font-size: 11px; }
.skill-audit-row strong, .skill-audit-row code { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-primary); }
.skill-audit-row small { margin-left: auto; white-space: nowrap; color: var(--text-secondary); }
.skill-audit-event { color: #a1a1aa; }
.skill-audit-event[data-event="activated"] { color: #67e8f9; }
.skill-audit-event[data-event="adopted"] { color: #86efac; }
.monitor-log { background: #0d1117; border-radius: var(--radius); padding: 12px; max-height: calc(100vh - 390px); min-height: 180px; overflow-y: auto; font-family: 'Cascadia Code', 'Fira Code', monospace; font-size: 12px; line-height: 1.6; }
.log-line { padding: 1px 0; white-space: pre-wrap; word-break: break-all; }
.log-info { color: #8b949e; } .log-warn { color: #d29922; } .log-error { color: #f85149; }
.log-empty { color: #484f58; text-align: center; padding: 40px; }
.btn-danger { color: #ef4444 !important; }
@media (max-width: 800px) { .diagnostic-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .runtime-row { flex-wrap: wrap; } }
</style>
