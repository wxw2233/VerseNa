<template>
  <div class="settings-layout">
    <!-- Sidebar Menu -->
    <aside class="sidebar">
      <router-link to="/" class="menu-item back-btn" title="返回聊天">
        <span class="menu-icon">←</span>
        <span class="menu-label">返回聊天</span>
      </router-link>
      <div class="menu-divider"></div>
      <div
        v-for="item in menuItems"
        :key="item.id"
        class="menu-item"
        :class="{ active: activeTab === item.id }"
        :title="item.label"
        @click="activeTab = item.id"
      >
        <span class="menu-icon">{{ item.icon }}</span>
        <span class="menu-label">{{ item.label }}</span>
      </div>
      <div class="sidebar-spacer"></div>
      <button v-if="authRequired" class="menu-item logout-btn" type="button" title="退出登录" @click="logout">
        <LogOut class="menu-icon" :size="16" />
        <span class="menu-label">退出登录</span>
      </button>
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

      <SecurityTab v-if="activeTab === 'security'" />
      <ToolTab v-if="activeTab === 'tool'" />
      <MemoryTab v-if="activeTab === 'memory'" />
      <AdvancedTab v-if="activeTab === 'advanced'" />
      <MonitorTab v-if="activeTab === 'monitor'" />
      <UpdateTab v-if="activeTab === 'update'" />
    </section>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { LogOut } from 'lucide-vue-next'
import { useThemeStore } from '../stores/theme'
import PersonaTab from '../components/settings/PersonaTab.vue'
import ThemePackTab from '../components/settings/ThemePackTab.vue'
import ModelTab from '../components/settings/ModelTab.vue'
import ToolTab from '../components/settings/ToolTab.vue'
import MemoryTab from '../components/settings/MemoryTab.vue'
import MonitorTab from '../components/settings/MonitorTab.vue'
import SkillTab from '../components/settings/SkillTab.vue'
import AdvancedTab from '../components/settings/AdvancedTab.vue'
import SecurityTab from '../components/settings/SecurityTab.vue'
import UpdateTab from '../components/settings/UpdateTab.vue'
import QQBotConfig from '../components/QQBotConfig.vue'
import { getAuthStatus, logoutSession } from '../utils/auth'

const activeTab = ref('persona')
const themeStore = useThemeStore()
const personaTabRef = ref(null)
const authRequired = ref(false)
const sourceUpdatesSupported = ref(false)

const allMenuItems = [
  { id: 'persona', icon: '🎭', label: '次元设置' },
  { id: 'themepack', icon: '📦', label: '主题包' },
  { id: 'model', icon: '🤖', label: '模型配置' },
  { id: 'channel', icon: '📡', label: '通道管理' },
  { id: 'plugin', icon: '🔌', label: '插件管理' },
  { id: 'skill', icon: '⚡', label: '技能' },
  { id: 'security', icon: '🔐', label: '访问安全' },
  { id: 'tool', icon: '🔧', label: '工具' },
  { id: 'memory', icon: '🧠', label: '记忆' },
  { id: 'advanced', icon: '⚙️', label: '高级' },
  { id: 'monitor', icon: '📊', label: '监控' },
  { id: 'update', icon: '↑', label: '源码更新' },
]
const menuItems = computed(() => allMenuItems.filter(item => (
  (item.id !== 'security' || authRequired.value)
  && (item.id !== 'update' || sourceUpdatesSupported.value)
)))

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
  try {
    authRequired.value = Boolean((await getAuthStatus()).required)
  } catch {}
  try {
    const updateResponse = await fetch('/api/update/status')
    const updateStatus = await updateResponse.json()
    sourceUpdatesSupported.value = Boolean(updateResponse.ok && updateStatus.supported)
  } catch {}
  await loadThemePacks()
  await themeStore.applyTheme()
})

async function logout() {
  await logoutSession()
}
</script>

<style scoped>
.settings-layout {
  display: flex;
  height: 100vh;
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

/* 返回按钮 */
.back-btn {
  text-decoration: none;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.15) !important;
}

.back-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--primary);
  border-color: var(--primary) !important;
}

.menu-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.1);
  margin: 8px 16px;
}

.sidebar-spacer {
  flex: 1;
}

.logout-btn {
  width: calc(100% - 16px);
  margin-bottom: 12px;
  font-family: inherit;
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

@media (max-width: 700px) {
  .sidebar {
    width: 56px;
    min-width: 56px;
    padding-top: 6px;
  }

  .menu-item {
    justify-content: center;
    gap: 0;
    margin: 2px 6px;
    padding: 8px 6px;
  }

  .menu-label {
    display: none;
  }

  .menu-divider {
    margin: 6px 10px;
  }

  .logout-btn {
    width: calc(100% - 12px);
    margin-bottom: 8px;
  }

  .content {
    padding: 20px 14px;
  }
}
</style>
