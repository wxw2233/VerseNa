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
  const opacity = localStorage.getItem('bg-opacity') || '0.3'
  return {
    backgroundImage: "url(/api/themes/" + themeId + "/assets/bg.png)",
    opacity: opacity,
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
}
.top-bar, .main-content {
  position: relative;
  z-index: 1;
}

.top-bar {
  display: flex;
  align-items: center;
  padding: 12px 20px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border);
}
.nav-title {
  font-size: 18px;
  font-weight: bold;
  color: var(--primary);
  text-decoration: none;
  margin-right: auto;
}
.nav-link {
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  cursor: pointer;
}
.nav-link:hover, .nav-link.active {
  color: var(--primary);
}
.main-content {
  flex: 1;
  overflow: hidden;
}
</style>
