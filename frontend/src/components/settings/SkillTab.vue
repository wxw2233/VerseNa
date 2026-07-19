<template>
  <div class="tab-content">
    <h2>技能管理</h2>
    <p class="hint">技能由 Agent 根据对话内容自动选择。在聊天中输入 <code>/skill install &lt;github-url&gt;</code> 安装新技能。</p>

    <div class="skill-grid">
      <div v-for="skill in skills" :key="skill.id" class="skill-card">
        <div class="skill-icon">{{ skill.icon }}</div>
        <div class="skill-info">
          <div class="skill-name">{{ skill.name }}</div>
          <div class="skill-desc">{{ skill.description }}</div>
          <div class="skill-meta">
            <span class="badge" :class="skill.source">{{ skill.source === 'builtin' ? '内置' : '已安装' }}</span>
            <span v-if="skill.github_url" class="badge github">{{ skill.github_url }}</span>
          </div>
        </div>
        <div class="skill-actions">
          <button v-if="skill.source !== 'builtin'" class="btn-sm btn-danger" @click="deleteSkill(skill.id)" title="卸载">🗑</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useToast } from '../../composables/useToast'

const toast = useToast()
const skills = ref([])

async function loadSkills() {
  try {
    const resp = await fetch('/api/skills')
    skills.value = await resp.json()
  } catch {}
}

async function deleteSkill(id) {
  if (!confirm('确定卸载此技能？')) return
  try {
    await fetch(`/api/skills/${id}`, { method: 'DELETE' })
    toast.success('已卸载')
    await loadSkills()
  } catch (e) {
    toast.error('卸载失败: ' + e.message)
  }
}

onMounted(() => loadSkills())
</script>

<style scoped>
.hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 16px;
}
.hint code {
  background: rgba(124,92,252,0.15);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}

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
}
.btn-sm:hover {
  box-shadow: 0 0 0 1px var(--primary);
  filter: brightness(1.08);
}
.btn-danger:hover {
  box-shadow: 0 0 0 1px #ef4444;
}
</style>
