<template>
  <div class="tab-content">
    <div class="section-heading">
      <div>
        <h2>技能管理</h2>
        <span v-if="diagnostics" class="skill-count">{{ diagnostics.total }} 个技能</span>
      </div>
      <button class="icon-btn" :disabled="loading" @click="loadSkills" title="刷新技能" aria-label="刷新技能">
        <RefreshCcw :class="{ spin: loading }" :size="16" aria-hidden="true" />
      </button>
    </div>

    <form class="install-row" @submit.prevent="installSkill">
      <input
        v-model.trim="installUrl"
        type="url"
        placeholder="https://github.com/owner/repository"
        aria-label="GitHub 技能仓库地址"
        :disabled="installing"
      />
      <button class="install-btn" :disabled="installing || !installUrl">
        <LoaderCircle v-if="installing" class="spin" :size="16" aria-hidden="true" />
        <Download v-else :size="16" aria-hidden="true" />
        <span>{{ installing ? '安装中' : '安装' }}</span>
      </button>
    </form>

    <div v-if="loadError" class="state-message error">{{ loadError }}</div>
    <div v-else-if="loading && !skills.length" class="state-message">
      <LoaderCircle class="spin" :size="18" aria-hidden="true" />
      <span>正在加载</span>
    </div>
    <div v-else-if="!skills.length" class="state-message">暂无技能</div>

    <div v-if="diagnostics?.load_errors?.length" class="diagnostic-errors">
      <div v-for="error in diagnostics.load_errors" :key="error">{{ error }}</div>
    </div>

    <div v-if="skills.length" class="skill-grid">
      <div v-for="skill in skills" :key="skill.id" class="skill-card">
        <div class="skill-icon">{{ skill.icon }}</div>
        <div class="skill-info">
          <div class="skill-name">{{ skill.name }}</div>
          <div class="skill-desc">{{ skill.description }}</div>
          <div class="skill-meta">
            <span class="badge" :class="skill.source">{{ sourceLabel(skill.source) }}</span>
            <span v-if="skill.github_url" class="badge github">{{ skill.github_url }}</span>
          </div>
        </div>
        <div class="skill-actions">
          <button
            v-if="skill.source !== 'builtin'"
            class="btn-sm btn-danger"
            :disabled="deletingId === skill.id"
            @click="deleteSkill(skill.id)"
            title="卸载"
            aria-label="卸载技能"
          >
            <LoaderCircle v-if="deletingId === skill.id" class="spin" :size="15" aria-hidden="true" />
            <Trash2 v-else :size="15" aria-hidden="true" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Download, LoaderCircle, RefreshCcw, Trash2 } from 'lucide-vue-next'
import { useToast } from '../../composables/useToast'

const toast = useToast()
const skills = ref([])
const diagnostics = ref(null)
const installUrl = ref('')
const loading = ref(false)
const installing = ref(false)
const deletingId = ref('')
const loadError = ref('')

async function loadSkills() {
  loading.value = true
  loadError.value = ''
  try {
    const [skillsResp, statusResp] = await Promise.all([
      fetch('/api/skills'),
      fetch('/api/skills/status'),
    ])
    if (!skillsResp.ok) throw new Error(`HTTP ${skillsResp.status}`)
    skills.value = await skillsResp.json()
    diagnostics.value = statusResp.ok ? await statusResp.json() : null
  } catch (error) {
    loadError.value = `技能加载失败: ${error.message}`
  } finally {
    loading.value = false
  }
}

async function installSkill() {
  if (!installUrl.value || installing.value) return
  installing.value = true
  try {
    const resp = await fetch('/api/skills/install', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: installUrl.value }),
    })
    const data = await resp.json().catch(() => ({}))
    if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`)
    installUrl.value = ''
    toast.success(`已安装 ${data.skill?.name || '技能'}`)
    await loadSkills()
    window.dispatchEvent(new CustomEvent('versena:skills-changed'))
  } catch (error) {
    toast.error(`安装失败: ${error.message}`)
  } finally {
    installing.value = false
  }
}

async function deleteSkill(id) {
  if (!confirm('确定卸载此技能？')) return
  deletingId.value = id
  try {
    const resp = await fetch(`/api/skills/${encodeURIComponent(id)}`, { method: 'DELETE' })
    const data = await resp.json().catch(() => ({}))
    if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`)
    toast.success('已卸载')
    await loadSkills()
    window.dispatchEvent(new CustomEvent('versena:skills-changed'))
  } catch (e) {
    toast.error('卸载失败: ' + e.message)
  } finally {
    deletingId.value = ''
  }
}

function sourceLabel(source) {
  if (source === 'builtin') return '内置'
  if (source === 'custom') return '本地'
  return '已安装'
}

onMounted(() => loadSkills())
</script>

<style scoped>
.section-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
.section-heading > div { display: flex; align-items: baseline; gap: 10px; }
.section-heading h2 { margin: 0; }
.skill-count { color: var(--text-secondary); font-size: 12px; }
.icon-btn {
  width: var(--control-icon-size); height: var(--control-icon-size); display: inline-flex; align-items: center; justify-content: center;
  padding: 0; color: var(--text-secondary); background: transparent; border: none; border-radius: var(--radius-sm); cursor: pointer;
}
.icon-btn:hover:not(:disabled) { color: var(--text-primary); background: rgba(255,255,255,0.08); }
.install-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; margin-bottom: 16px; }
.install-row input {
  min-width: 0; height: 38px; padding: 0 11px; color: var(--text-primary); background: rgba(20,20,40,0.60);
  border: 1px solid rgba(255,255,255,0.14); border-radius: var(--radius-sm); outline: none; font: inherit; font-size: 13px;
}
.install-row input:focus { border-color: var(--primary); }
.install-btn {
  min-width: 88px; height: 38px; display: inline-flex; align-items: center; justify-content: center; gap: 7px;
  padding: 0 14px; color: white; background: var(--primary); border: none; border-radius: var(--radius-sm); cursor: pointer;
}
.install-btn:disabled, .icon-btn:disabled, .btn-sm:disabled { opacity: 0.55; cursor: not-allowed; }
.state-message { min-height: 90px; display: flex; align-items: center; justify-content: center; gap: 8px; color: var(--text-secondary); font-size: 13px; }
.state-message.error, .diagnostic-errors { color: #fca5a5; }
.diagnostic-errors { margin-bottom: 12px; padding: 9px 11px; background: rgba(127,29,29,0.18); border: 1px solid rgba(248,113,113,0.2); border-radius: var(--radius-sm); font-size: 12px; }
.spin { animation: spin 800ms linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.skill-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.skill-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  background: rgba(20, 20, 40, 0.60);
  box-shadow: var(--ui-border);
  border-radius: var(--radius);
}
.skill-icon {
  font-size: 28px;
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255,255,255,0.06);
  border-radius: 10px;
  flex-shrink: 0;
}
.skill-info { flex: 1; min-width: 0; }
.skill-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.skill-desc {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}
.skill-meta {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}
.badge {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 10px;
}
.badge.builtin {
  background: rgba(124, 92, 252, 0.15);
  color: var(--primary);
}
.badge.installed {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}
.badge.custom { background: rgba(14,165,233,0.14); color: #7dd3fc; }
.badge.github {
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-secondary);
  font-family: monospace;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.skill-actions { display: flex; gap: 4px; }
.btn-sm {
  width: 36px;
  height: 36px;
  background: rgba(255, 255, 255, 0.08);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.15);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  color: var(--text-secondary);
}
.btn-sm:hover {
  box-shadow: 0 0 0 1px var(--primary);
  filter: brightness(1.08);
}
.btn-sm:disabled:hover { box-shadow: 0 0 0 1px rgba(255,255,255,0.15); filter: none; }
.btn-danger:hover {
  box-shadow: 0 0 0 1px #ef4444;
}

@media (max-width: 640px) {
  .install-row { grid-template-columns: 1fr; }
  .install-btn { width: 100%; }
}
</style>
