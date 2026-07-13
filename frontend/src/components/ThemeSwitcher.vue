<template>
  <div class="theme-switcher">
    <h3>主题</h3>
    <div class="theme-list">
      <div
        v-for="t in themeStore.themes"
        :key="t.id"
        class="theme-card"
        :class="{ active: themeStore.current === t.id }"
        @click="themeStore.applyTheme(t.id)"
      >
        <div class="theme-dot" :style="{ background: getPreviewColor(t.id) }"></div>
        <span>{{ t.name }}</span>
        <button
          v-if="t.id !== 'default'"
          class="delete-btn"
          @click.stop="deleteTheme(t.id)"
          title="删除主题"
        >×</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useThemeStore } from '../stores/theme'
const themeStore = useThemeStore()
onMounted(() => themeStore.fetchThemes())

const previewColors = { default: '#7c5cfc', miku: '#39C5BB' }
function getPreviewColor(id) { return previewColors[id] || '#888' }

async function deleteTheme(id) {
  if (!confirm(`确定要删除主题 "${id}" 吗？`)) return
  const resp = await fetch(`/api/themes/${id}`, { method: 'DELETE' })
  if (resp.ok) {
    await themeStore.fetchThemes()
  } else {
    const err = await resp.json()
    alert(err.detail || '删除失败')
  }
}
</script>

<style scoped>
.theme-switcher { margin-bottom: 24px; }
.theme-switcher h3 { font-size: 16px; margin-bottom: 12px; color: var(--text-primary); }
.theme-list { display: flex; gap: 12px; flex-wrap: wrap; }
.theme-card {
  position: relative;
  display: flex; align-items: center; gap: 8px;
  padding: 10px 16px; border-radius: 10px;
  border: 1px solid var(--border); cursor: pointer; transition: all 0.2s;
}
.theme-card:hover { border-color: var(--primary); }
.theme-card.active { background: var(--primary); border-color: var(--primary); }
.theme-dot { width: 16px; height: 16px; border-radius: 50%; }
.delete-btn {
  display: none;
  position: absolute; top: -6px; right: -6px;
  width: 18px; height: 18px; border-radius: 50%;
  background: #e74c3c; color: white; border: none;
  font-size: 12px; line-height: 18px; text-align: center;
  cursor: pointer; padding: 0;
}
.theme-card:hover .delete-btn { display: block; }
.delete-btn:hover { background: #c0392b; }
</style>
