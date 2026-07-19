<template>
  <div class="settings-layout">
    <!-- Sidebar Menu -->
    <aside class="sidebar">
      <div
        v-for="item in menuItems"
        :key="item.id"
        class="menu-item"
        :class="{ active: activeTab === item.id }"
        @click="activeTab = item.id"
      >
        <span class="menu-icon">{{ item.icon }}</span>
        <span class="menu-label">{{ item.label }}</span>
      </div>
    </aside>

    <!-- Content Area -->
    <section class="content">
      <PersonaTab
        v-if="activeTab === 'persona'"
        :theme-packs="themePacks"
        :pack-icons="packIcons"
        @pack-changed="onPackChanged"
        ref="personaTabRef"
      />

      <ThemePackTab
        v-if="activeTab === 'themepack'"
        :theme-packs="themePacks"
        :pack-icons="packIcons"
        @pack-changed="onPackChanged"
      />

      <ModelTab v-if="activeTab === 'model'" />

      <div v-if="activeTab === 'channel'" class="tab-content">
        <h2>通道管理</h2>
        <QQBotConfig />
      </div>

      <div v-if="activeTab === 'plugin'" class="tab-content">
        <h2>插件管理</h2>
        <div class="empty-state">
          <div class="empty-icon">🔌</div>
          <div class="empty-title">暂无插件</div>
          <div class="empty-desc">将插件文件夹放入 <code>plugins/</code> 目录即可自动加载</div>
        </div>
      </div>

      <SkillTab v-if="activeTab === 'skill'" />

      <ToolTab v-if="activeTab === 'tool'" />
      <MemoryTab v-if="activeTab === 'memory'" />
      <AdvancedTab v-if="activeTab === 'advanced'" />
      <MonitorTab v-if="activeTab === 'monitor'" />
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useThemeStore } from '../stores/theme'
import PersonaTab from '../components/settings/PersonaTab.vue'
import ThemePackTab from '../components/settings/ThemePackTab.vue'
import ModelTab from '../components/settings/ModelTab.vue'
import ToolTab from '../components/settings/ToolTab.vue'
import MemoryTab from '../components/settings/MemoryTab.vue'
import MonitorTab from '../components/settings/MonitorTab.vue'
import SkillTab from '../components/settings/SkillTab.vue'
import AdvancedTab from '../components/settings/AdvancedTab.vue'
import QQBotConfig from '../components/QQBotConfig.vue'

const activeTab = ref('persona')
const themeStore = useThemeStore()
const personaTabRef = ref(null)

const menuItems = [
  { id: 'persona', icon: '🎭', label: '次元设置' },
  { id: 'themepack', icon: '📦', label: '主题包' },
  { id: 'model', icon: '🤖', label: '模型配置' },
  { id: 'channel', icon: '📡', label: '通道管理' },
  { id: 'plugin', icon: '🔌', label: '插件管理' },
  { id: 'skill', icon: '⚡', label: '技能' },
  { id: 'tool', icon: '🔧', label: '工具' },
  { id: 'memory', icon: '🧠', label: '记忆' },
  { id: 'advanced', icon: '⚙️', label: '高级' },
  { id: 'monitor', icon: '📊', label: '监控' },
]

// --- Shared theme pack data ---
const themePacks = ref([])
const packIcons = ref({})

async function loadThemePacks() {
  try {
    const resp = await fetch('/api/themepacks')
    const data = await resp.json()
    themePacks.value = Array.isArray(data) ? data : []
    for (const pack of themePacks.value) {
      try {
        const iconResp = await fetch(`/api/themes/${pack.id}/assets/icon.png`)
        if (iconResp.ok) {
          packIcons.value[pack.id] = `/api/themes/${pack.id}/assets/icon.png?t=${Date.now()}`
        } else {
          packIcons.value[pack.id] = null
        }
      } catch {
        packIcons.value[pack.id] = null
      }
    }
  } catch {
    themePacks.value = []
  }
}

async function onPackChanged() {
  await loadThemePacks()
  await themeStore.applyTheme()
}

onMounted(async () => {
  await loadThemePacks()
  await themeStore.applyTheme()
})
</script>

<style scoped>
.settings-layout {
  display: flex;
  height: calc(100vh - 49px);
  overflow: hidden;
}

/* Sidebar */
.sidebar {
  width: var(--sidebar-width, 180px);
  min-width: var(--sidebar-width, 180px);
  background: transparent;
  box-shadow: var(--glow-inner);
  display: flex;
  flex-direction: column;
  padding-top: 8px;
  position: relative;
  z-index: 2;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 16px;
  margin: 2px 8px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-secondary);
  transition: background 0.15s, color 0.15s, border-color 0.15s;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.44) !important;
  box-shadow: none !important;
  background: rgba(20, 20, 40, 0.60);
  user-select: none;
}

.menu-item:hover {
  background: rgba(255, 255, 255, 0.24);
  color: var(--text-primary);
  border-color: rgba(255, 255, 255, 0.60) !important;
}

.menu-item.active {
  background: color-mix(in srgb, var(--highlight) 44%, transparent);
  color: var(--primary);
  font-weight: 600;
  border-color: var(--highlight) !important;
}

.menu-icon {
  font-size: 16px;
  width: 20px;
  text-align: center;
}

/* Content Area */
.content {
  flex: 1;
  overflow-y: auto;
  padding: 28px 36px;
  background: transparent;
}

.tab-content h2 {
  font-size: 20px;
  margin-bottom: 20px;
}

/* Empty state */
.empty-state { text-align: center; padding: 60px 20px; }
.empty-icon { font-size: 48px; margin-bottom: 16px; }
.empty-title { font-size: 18px; font-weight: 600; color: var(--text-primary); margin-bottom: 8px; }
.empty-desc { color: var(--text-secondary); font-size: 14px; }
.empty-desc code { background: rgba(124,92,252,0.15); padding: 2px 6px; border-radius: 4px; font-size: 13px; }
</style>
