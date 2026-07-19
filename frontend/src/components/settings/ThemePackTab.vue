<template>
  <div class="tab-content">
    <h2>主题包管理</h2>
    <p class="hint">导出/导入/管理完整主题包（包含颜色、素材、角色配置）</p>

    <div class="tp-grid">
      <div v-for="pack in themePacks" :key="pack.id" class="tp-card">
        <div class="tp-preview">
          <img v-if="packIconUrl(pack.id)" :src="packIconUrl(pack.id)" class="tp-icon" />
          <div v-else class="tp-icon-fallback" :style="{ background: pack.theme?.colors?.primary || '#7c5cfc' }"></div>
        </div>
        <div class="tp-info">
          <div class="tp-name">{{ pack.name || pack.id }}</div>
          <div class="tp-meta">
            <span v-if="pack.character?.name">🎭 {{ pack.character.name }}</span>
            <span v-if="pack.theme?.name">🎨 {{ pack.theme.name }}</span>
          </div>
        </div>
        <div class="tp-actions">
          <button class="btn-sm" @click="exportPack(pack.id)" title="导出">📦</button>
          <button class="btn-sm" @click="applyPack(pack.id)" title="一键更新关联会话">⚡</button>
          <button class="btn-sm btn-sm-danger" @click="deletePack(pack.id)" title="删除">🗑</button>
        </div>
      </div>
      <div v-if="themePacks.length === 0" class="empty-hint">暂无主题包</div>
    </div>

    <div class="package-actions">
      <label class="btn-action">
        导入主题包（zip）
        <input type="file" accept=".zip" @change="importPack" style="display:none" />
      </label>
    </div>
  </div>
</template>

<script setup>
import { useThemeStore } from '../../stores/theme'
import { useToast } from '../../composables/useToast'

const props = defineProps({
  themePacks: { type: Array, default: () => [] },
  packIcons: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['pack-changed'])
const themeStore = useThemeStore()
const toast = useToast()

function packIconUrl(packId) {
  return props.packIcons[packId] || null
}

async function exportPack(packId) {
  try {
    const resp = await fetch(`/api/themepacks/${packId}/export`)
    if (resp.ok) {
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${packId}-themepack.zip`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('导出成功')
    } else {
      toast.error('导出失败')
    }
  } catch (e) {
    toast.error('导出失败: ' + e.message)
  }
}

async function deletePack(packId) {
  if (!confirm(`确定删除主题包「${packId}」？`)) return
  try {
    const resp = await fetch(`/api/themepacks/${packId}`, { method: 'DELETE' })
    if (resp.ok) {
      emit('pack-changed')
      toast.success('删除成功')
    } else {
      const err = await resp.json()
      toast.error(err.detail || '删除失败')
    }
  } catch (e) {
    toast.error('删除失败: ' + e.message)
  }
}

async function applyPack(packId) {
  if (!confirm(`确定一键更新关联会话「${packId}」？`)) return
  try {
    const resp = await fetch(`/api/themepacks/${packId}/apply`, { method: 'POST' })
    if (resp.ok) {
      toast.success('已更新关联会话')
    } else {
      const err = await resp.json()
      toast.error(err.detail || '更新失败')
    }
  } catch (e) {
    toast.error('更新失败: ' + e.message)
  }
}

async function importPack(e) {
  const file = e.target.files[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  try {
    const resp = await fetch('/api/themepacks/import', { method: 'POST', body: formData })
    if (resp.ok) {
      const data = await resp.json()
      emit('pack-changed')
      toast.success(`导入成功！主题包: ${data.name || data.id || '已导入'}`)
    } else {
      const err = await resp.json()
      toast.error(err.detail || '导入失败')
    }
  } catch (e) {
    toast.error('导入失败: ' + e.message)
  }
}
</script>

<style scoped>
.tp-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}
.tp-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: rgba(20, 20, 40, 0.60);
  box-shadow: var(--ui-border);
  border-radius: var(--radius);
  transition: filter 0.2s, transform 0.2s, box-shadow 0.2s;
}
.tp-card:hover {
  box-shadow: 0 0 0 1px var(--primary), var(--glow-inner);
  filter: brightness(1.05);
  transform: translateY(-1px);
}
.tp-preview {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  flex-shrink: 0;
  overflow: hidden;
}
.tp-icon {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.tp-icon-fallback {
  width: 100%;
  height: 100%;
}
.tp-info { flex: 1; min-width: 0; }
.tp-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.tp-meta {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
  display: flex;
  gap: 8px;
}
.tp-actions { display: flex; gap: 4px; }

.btn-sm {
  width: 36px;
  height: 36px;
  background: rgba(20, 20, 40, 0.60);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: filter 0.2s, transform 0.2s, box-shadow 0.2s;
}
.btn-sm:hover {
  box-shadow: 0 0 0 1px var(--primary);
  filter: brightness(1.08);
  transform: translateY(-1px);
}
.btn-sm-danger:hover {
  box-shadow: 0 0 0 1px #e74c3c;
}

.package-actions {
  display: flex;
  gap: 10px;
  margin-top: 12px;
}
.btn-action {
  flex: 1;
  padding: 10px 16px;
  background: rgba(20, 20, 40, 0.60);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
  border: none;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 13px;
  text-align: center;
  transition: filter 0.2s, transform 0.2s, box-shadow 0.2s;
}
.btn-action:hover {
  box-shadow: 0 0 0 1px var(--primary);
  color: var(--primary);
  filter: brightness(1.05);
  transform: translateY(-1px);
}

.hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 12px;
}
.empty-hint {
  text-align: center;
  padding: 24px;
  color: var(--text-secondary);
  font-size: 14px;
}
</style>
