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
        <CircleAlert v-if="isBlocked || hasLocalChanges || status.check_error" :size="18" />
        <CircleCheck v-else-if="isCurrent" :size="18" />
        <Download v-else :size="18" />
        <span>{{ stateMessage }}</span>
      </div>

      <div v-if="hasLocalChanges" class="local-changes">
        <div class="local-changes-title">
          <FileWarning :size="16" aria-hidden="true" />
          <span>本地修改不会被自动删除；如与上游冲突，更新会安全中止。</span>
        </div>
        <ul v-if="status.dirty_paths?.length">
          <li v-for="path in status.dirty_paths.slice(0, 6)" :key="path" class="mono">{{ path }}</li>
        </ul>
        <span v-if="status.dirty_paths?.length > 6" class="more-paths">
          另有 {{ status.dirty_paths.length - 6 }} 个文件
        </span>
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
          :title="applyDisabledReason"
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
  FileWarning,
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
  || Number(status.value?.ahead) > 0
))
const hasLocalChanges = computed(() => Boolean(status.value?.dirty))
const isCurrent = computed(() => (
  status.value?.supported
  && !status.value?.update_available
  && !status.value?.pending
  && !isBlocked.value
))
const canApply = computed(() => (
  status.value?.supported
  && Number(status.value?.ahead) === 0
  && (status.value?.update_available || status.value?.pending)
))
const applyDisabledReason = computed(() => {
  if (!status.value?.supported) return status.value?.message || '当前源码不支持在线更新'
  if (Number(status.value?.ahead) > 0) return '本地分支含有上游没有的提交，无法自动更新'
  if (!status.value?.update_available && !status.value?.pending) return '当前没有可安装的更新'
  return ''
})
const stateClass = computed(() => ({
  blocked: isBlocked.value,
  current: isCurrent.value,
  warning: !isBlocked.value && (hasLocalChanges.value || Boolean(status.value?.check_error)),
  available: !isBlocked.value && !isCurrent.value && !hasLocalChanges.value && !status.value?.check_error,
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
    if (status.value.check_error) toast.warning(status.value.check_error)
    else if (status.value.update_available) toast.success('发现源码更新')
    else toast.success('当前源码已是最新版本')
  } catch (error) {
    toast.error(`检查更新失败: ${error.message}`)
  } finally {
    action.value = ''
  }
}

async function applyUpdate() {
  if (!canApply.value) return
  const localChangeNotice = hasLocalChanges.value
    ? '检测到本地源码修改。更新会保留不冲突的修改，发生冲突时会中止且不会删除文件。\n\n'
    : ''
  if (!window.confirm(`${localChangeNotice}更新会拉取源码、补充依赖并重建前端。完成后需要重启 VerseNa，是否继续？`)) return
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
.update-state.warning { color: #f5bf68; }
.update-state.blocked { color: #ff9caa; }

.local-changes {
  margin-top: 12px;
  padding: 10px 12px;
  color: var(--text-secondary);
  background: rgba(245, 191, 104, 0.07);
  border-left: 3px solid #f5bf68;
  font-size: 12px;
}

.local-changes-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-primary);
}

.local-changes ul {
  margin: 8px 0 0;
  padding: 0 0 0 24px;
}

.local-changes li {
  margin: 3px 0;
  overflow-wrap: anywhere;
}

.more-paths {
  display: block;
  margin: 6px 0 0 24px;
}

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
