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
</script>

<style scoped>
.theme-switcher { margin-bottom: 24px; }
.theme-switcher h3 { font-size: 16px; margin-bottom: 12px; color: var(--text-primary); }
.theme-list { display: flex; gap: 12px; flex-wrap: wrap; }
.theme-card {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 16px; border-radius: 10px;
  border: 1px solid var(--border); cursor: pointer; transition: all 0.2s;
}
.theme-card:hover { border-color: var(--primary); }
.theme-card.active { background: var(--primary); border-color: var(--primary); }
.theme-dot { width: 16px; height: 16px; border-radius: 50%; }
</style>
