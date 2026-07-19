<template>
  <div id="app-root">
    <nav class="top-bar">
      <router-link to="/" class="nav-title">次元人格</router-link>
      <a class="nav-link" :class="{ active: isSettings }" @click="toggleSettings">{{ isSettings ? '返回' : '设置' }}</a>
    </nav>
    <div class="bg-layer" :style="bgStyle" :class="{ 'bg-visible': bgReady }"></div>
    <main class="main-content">
      <router-view v-slot="{ Component, route }">
        <Transition name="page-fade" mode="out-in">
          <component :is="Component" :key="route.path" />
        </Transition>
      </router-view>
    </main>
    <Toast />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useThemeStore } from './stores/theme'
import { useBrightness } from './composables/useBrightness'
import Toast from './components/Toast.vue'

const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()
const { update: updateBrightness } = useBrightness()

const bgReady = ref(true)
let currentBgUrl = ''

const bgStyle = computed(() => {
  const themeId = themeStore.current
  if (!themeId || themeId === 'null') return {}
  const opacity = localStorage.getItem('bg-opacity') || '0.3'
  const ts = localStorage.getItem('bg-ts') || '0'
  return {
    backgroundImage: 'url(/api/themes/' + themeId + '/assets/bg.png?ts=' + ts + ')',
    '--target-opacity': opacity,
  }
})

watch(bgStyle, (val) => {
  const url = val.backgroundImage ? val.backgroundImage.replace(/^url\(/, '').replace(/\)$/, '') : ''
  updateBrightness(url, val['--target-opacity'])

  // 背景图变化时：先隐藏，预加载完成后淡入
  if (url && url !== currentBgUrl) {
    currentBgUrl = url
    bgReady.value = false
    const img = new Image()
    img.onload = () => { bgReady.value = true }
    img.onerror = () => { bgReady.value = true }
    img.src = url
  }
}, { immediate: true })

const isSettings = computed(() => route.path === '/settings')
function toggleSettings() {
  if (isSettings.value) { router.push('/') }
  else { router.push('/settings') }
}

onMounted(() => { themeStore.restoreTheme() })
</script>

<style scoped>
.bg-layer {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background-size: cover;
  background-position: center;
  z-index: 0;
  pointer-events: none;
  opacity: 0;
  transition: none;
}
.bg-layer.bg-visible {
  opacity: var(--target-opacity, 0.3);
  transition: opacity 0.4s ease;
}
.top-bar, .main-content { position: relative; z-index: 1; }

.top-bar {
  display: flex; align-items: center; padding: 12px 20px;
  background: transparent; box-shadow: none;
}
.nav-title {
  text-shadow: 0 0 8px rgba(0,0,0,0.5);
  font-size: 18px; font-weight: bold; color: var(--primary);
  text-decoration: none; margin-right: auto; letter-spacing: 1px;
}
.nav-link {
  color: var(--text-secondary); font-size: 14px; cursor: pointer;
  padding: 4px 12px; border-radius: 8px;
  transition: background 0.15s, color 0.15s;
  text-shadow: 0 0 4px rgba(0,0,0,0.3);
}
.nav-link:hover { color: var(--primary); background: rgba(124, 92, 252, 0.15); }
.nav-link.active { color: var(--primary); }
.main-content {
  flex: 1;
  overflow: hidden;
  position: relative;
}

/* 路由切换动画 */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.page-fade-enter-from {
  opacity: 0;
  transform: translateY(6px);
}
.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
