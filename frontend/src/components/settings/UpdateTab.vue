<template>
  <div class="tab-content update-tab">
    <header class="tab-header">
      <RefreshCw :size="22" aria-hidden="true" />
      <h2>源码更新</h2>
    </header>

    <div v-if="loading" class="loading-row">
      <LoaderCircle class="spin" :size="18" />
      <span>正在读取版本状态</span>
    </div>

    <template v-else-if="status">
      <div class="version-rows">
        <div class="version-row">
          <span>版本</span>
          <strong>{{ status.version || '-' }}</strong>
        </div>
        <div class="version-row">
          <span>分支</span>
          <strong class="mono"><GitBranch :size="15" />{{ status.branch || '-' }}</strong>
        </div>
        <div class="version-row">
          <span>提交</span>
          <strong class="mono">{{ status.commit_short || '-' }}</strong>
        </div>
        <div class="version-row">
          <span>上游</span>
          <strong class="mono">{{ status.upstream || '-' }}</strong>
        </div>
      </div>

      <div class="update-state" :class="stateClass">
        <CircleAlert v-if="isBlocked" :size="18" />
        <CircleCheck v-else-if="isCurrent" :size="18" />
        <Download v-else :size="18" />
        <span>{{ stateMessage }}</span>
      </div>

      <div class="update-actions">
        <button
          type="button"
          class="action-button secondary"
          :disabled="Boolean(action) || !status.supported"
          @click="checkUpdates"
        >
          <LoaderCircle v-if="action === 'check'" class="spin" :size="17" />
          <RefreshCw v-else :size="17" />
          <span>检查更新</span>
        </button>
        <button
          type="button"
          class="action-button primary"
          :disabled="Boolean(action) || !canApply"
          @click="applyUpdate"
        >
          <LoaderCircle v-if="action === 'apply'" class="spin" :size="17" />
          <Download v-else :size="17" />
          <span>{{ status.pending ? '继续更新' : '立即更新' }}</span>
        </button>
      </div>

      <p v-if="status.restart_required" class="restart-notice">
        <Power :size="16" />
        <span>更新已经写入，重启 VerseNa 后生效。</span>
      </p>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  CircleAlert,
  CircleCheck,
  Download,
  GitBranch,
  LoaderCircle,
  Power,
  RefreshCw,
} from 'lucide-vue-next'
import { useToast } from '../../composables/useToast'

const toast = useToast()
const status = ref(null)
const loading = ref(true)
const action = ref('')

const isBlocked = computed(() => (
  !status.value?.supported
  || status.value?.dirty
  || Number(status.value?.ahead) > 0
))
const isCurrent = computed(() => (
  status.value?.supported
  && !status.value?.update_available
  && !status.value?.pending
  && !isBlocked.value
))
const canApply = computed(() => (
  status.value?.supported
  && !status.value?.dirty
  && Number(status.value?.ahead) === 0
  && (status.value?.update_available || status.value?.pending)
))
const stateClass = computed(() => ({
  blocked: isBlocked.value,
  current: isCurrent.value,
  available: !isBlocked.value && !isCurrent.value,
}))
const stateMessage = computed(() => status.value?.message || '无法读取更新状态')

async function request(url, method = 'GET') {
  const response = await fetch(url, { method })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`)
  return data
}

async function loadStatus() {
  loading.value = true
  try {
    status.value = await request('/api/update/status')
  } catch (error) {
    toast.error(`读取更新状态失败: ${error.message}`)
  } finally {
    loading.value = false
  }
}

async function checkUpdates() {
  action.value = 'check'
  try {
    status.value = await request('/api/update/check', 'POST')
    if (status.value.update_available) toast.success('发现源码更新')
    else toast.success('当前源码已是最新版本')
  } catch (error) {
    toast.error(`检查更新失败: ${error.message}`)
  } finally {
    action.value = ''
  }
}

async function applyUpdate() {
  if (!canApply.value) return
  if (!window.confirm('更新会拉取源码、补充依赖并重建前端。完成后需要重启 VerseNa，是否继续？')) return
  action.value = 'apply'
  try {
    status.value = await request('/api/update/apply', 'POST')
    toast.success(status.value.applied ? '源码更新完成，请重启 VerseNa' : '当前源码已是最新版本')
  } catch (error) {
    toast.error(`源码更新失败: ${error.message}`)
    await loadStatus()
  } finally {
    action.value = ''
  }
}

onMounted(loadStatus)
</script>

<style scoped>
.update-tab {
  max-width: 760px;
}

.tab-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 26px;
}

.tab-header h2 {
  margin: 0;
  font-size: 20px;
}

.loading-row,
.update-state,
.restart-notice {
  display: flex;
  align-items: center;
  gap: 9px;
}

.loading-row {
  min-height: 52px;
  color: var(--text-secondary);
  font-size: 13px;
}

.version-rows {
  border-top: 1px solid rgba(255, 255, 255, 0.12);
}

.version-row {
  min-height: 45px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.12);
  font-size: 13px;
}

.version-row > span {
  color: var(--text-secondary);
}

.version-row strong {
  min-width: 0;
  overflow-wrap: anywhere;
  color: var(--text-primary);
}

.mono {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 12px;
}

.update-state {
  min-height: 48px;
  margin-top: 18px;
  padding: 0 12px;
  border-left: 3px solid currentColor;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.05);
  font-size: 13px;
}

.update-state.current { color: #79d69a; }
.update-state.available { color: var(--primary); }
.update-state.blocked { color: #ff9caa; }

.update-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 22px;
}

.action-button {
  min-height: 40px;
  padding: 0 15px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: var(--text-primary);
  cursor: pointer;
}

.action-button.secondary {
  background: rgba(20, 20, 40, 0.55);
}

.action-button.primary {
  border-color: color-mix(in srgb, var(--primary) 72%, white);
  background: color-mix(in srgb, var(--primary) 82%, #11131f);
}

.action-button:disabled {
  opacity: 0.42;
  cursor: default;
}

.restart-notice {
  margin-top: 18px;
  color: var(--text-secondary);
  font-size: 13px;
}

.spin {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 520px) {
  .version-row {
    align-items: flex-start;
    flex-direction: column;
    gap: 5px;
    padding: 10px 0;
  }

  .update-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

  .action-button {
    width: 100%;
    padding: 0 10px;
  }
}
</style>
