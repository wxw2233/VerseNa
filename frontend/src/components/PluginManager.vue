<template>
  <div class="plugin-manager">
    <h3>插件管理</h3>
    <div v-if="plugins.length === 0" class="empty">暂无插件。将插件文件夹放入 plugins/ 目录即可。</div>
    <div v-for="p in plugins" :key="p.name" class="plugin-item">
      <div class="plugin-info">
        <div class="plugin-name">{{ p.name }}</div>
        <div class="plugin-desc">{{ p.description || '无描述' }}</div>
      </div>
      <button
        class="toggle-btn"
        :class="{ enabled: p.enabled }"
        @click="toggle(p)"
      >
        {{ p.enabled ? '已启用' : '已禁用' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
const plugins = ref([])

async function loadPlugins() {
  const resp = await fetch('/api/plugins')
  plugins.value = await resp.json()
}

async function toggle(p) {
  const action = p.enabled ? 'disable' : 'enable'
  await fetch(`/api/plugins/${p.name}/${action}`, { method: 'POST' })
  await loadPlugins()
}

onMounted(loadPlugins)
</script>

<style scoped>
.plugin-manager { margin-bottom: 24px; }
.plugin-manager h3 { font-size: 16px; margin-bottom: 12px; color: var(--text-primary); }
.plugin-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 8px;
}
.plugin-name { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.plugin-desc { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }
.toggle-btn {
  padding: 6px 14px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 12px;
}
.toggle-btn.enabled {
  background: var(--primary);
  color: white;
  border-color: var(--primary);
}
.empty { color: var(--text-secondary); font-size: 13px; padding: 12px 0; }
</style>
