<template>
  <div id="app-root">
    <nav class="top-bar">
      <router-link to="/" class="nav-title">次元人格</router-link>
      <a class="nav-link" :class="{ active: isSettings }" @click="toggleSettings">{{ isSettings ? '返回' : '设置' }}</a>
    </nav>
    <div class="bg-layer" :style="bgStyle"></div>
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useThemeStore } from './stores/theme'

const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()

const bgStyle = computed(() => {
  const themeId = themeStore.current
  if (!themeId || themeId === 'null') return {}
  return {
    backgroundImage: "url(/api/themes/" + themeId + "/assets/bg.png)",
  }
})
const isSettings = computed(() => route.path === '/settings')
function toggleSettings() {
  if (isSettings.value) {
    router.push('/')
  } else {
    router.push('/settings')
  }
}
</script>

<style scoped>
.bg-layer {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background-size: cover;
  background-position: center;
  z-index: 0;
  pointer-events: none;
  opacity: var(--bg-opacity, 0.3);
}
.top-bar, .main-content {
  position: relative;
  z-index: 1;
}

/* L1: Top bar — 12px blur, 0.75 opacity, inner glow, no bottom border */
.top-bar {
  display: flex;
  align-items: center;
  padding: 12px 20px;
  background: transparent;
   

  box-shadow: none;
  /* no bottom border — perceptual border via box-shadow instead */
}
.nav-title { text-shadow: 0 0 8px rgba(0,0,0,0.5);
  font-size: 18px;
  font-weight: bold;
  color: var(--primary);
  text-decoration: none;
  margin-right: auto;
  letter-spacing: 1px;
}
.nav-link {
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  cursor: pointer;
  padding: 4px 12px;
  border-radius: 8px;
  transition: background 0.2s, color 0.2s;
}
.nav-link {
  color: var(--text-secondary); text-decoration: none; font-size: 14px;
  cursor: pointer; padding: 4px 12px; border-radius: 8px;
  transition: background 0.15s, color 0.15s;
  text-shadow: 0 0 4px rgba(0,0,0,0.3);
}
.nav-link:hover {
  color: var(--primary);
  background: rgba(124, 92, 252, 0.15);
}
.nav-link.active {
  color: var(--primary);
}
.main-content {
  flex: 1;
  overflow: hidden;
}
</style>
