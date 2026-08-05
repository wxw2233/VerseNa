<template>
  <div id="app-root">
    <ParticleBg color="#7c5cfc" :count="40" :speed="0.3" />
    <div class="bg-layer" :style="bgStyle" :class="{ 'bg-visible': bgReady }"></div>
    <div v-if="authChecking" class="auth-loading" aria-label="正在验证访问状态">
      <LoaderCircle :size="24" />
    </div>
    <LoginScreen
      v-else-if="authRequired && !authenticated"
      @authenticated="handleAuthenticated"
    />
    <main v-else class="main-content">
      <router-view v-slot="{ Component, route }">
        <Transition :name="transitionName" mode="out-in">
          <KeepAlive>
            <component :is="Component" :key="route.path" />
          </KeepAlive>
        </Transition>
      </router-view>
    </main>
    <Toast />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { LoaderCircle } from 'lucide-vue-next'
import { usePersonaStore } from './stores/persona'
import { useSessionStore } from './stores/session'
import { useThemeStore } from './stores/theme'
import { useBrightness } from './composables/useBrightness'
import Toast from './components/Toast.vue'
import ParticleBg from './components/ParticleBg.vue'
import LoginScreen from './components/LoginScreen.vue'
import { getAuthStatus, onAuthenticationRequired } from './utils/auth'

const route = useRoute()
const router = useRouter()
const personaStore = usePersonaStore()
const sessionStore = useSessionStore()
const themeStore = useThemeStore()
const { update: updateBrightness } = useBrightness()

const bgReady = ref(true)
const authChecking = ref(true)
const authRequired = ref(false)
const authenticated = ref(false)
let currentBgUrl = ''
let coreInitialized = false
let removeAuthListener = null

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

// 页面切换动画方向
const transitionName = ref('slide-right')
const prevPath = ref('/')

watch(() => route.path, (newPath) => {
  if (newPath === '/settings') {
    transitionName.value = 'slide-left'
  } else if (prevPath.value === '/settings') {
    transitionName.value = 'slide-right'
  } else {
    transitionName.value = 'slide-left'
  }
  prevPath.value = newPath
})

const isSettings = computed(() => route.path === '/settings')
function toggleSettings() {
  if (isSettings.value) { router.push('/') }
  else { router.push('/settings') }
}

async function initializeCoreData() {
  if (coreInitialized) return
  coreInitialized = true
  const results = await Promise.allSettled([
    sessionStore.fetchSessions({ retries: 4, retryDelay: 250 }),
    personaStore.fetchPersonas({ retries: 4, retryDelay: 250 }),
    themeStore.fetchThemes({ retries: 4, retryDelay: 250 }),
  ])

  results.forEach((result, index) => {
    if (result.status === 'rejected') {
      const resource = ['sessions', 'personas', 'themes'][index]
      console.error(`Failed to initialize ${resource}:`, result.reason)
    }
  })

  try {
    await themeStore.restoreTheme()
  } catch (err) {
    console.error('Failed to restore theme:', err)
  }
}

async function handleAuthenticated() {
  authenticated.value = true
  authChecking.value = false
  await initializeCoreData()
}

async function checkAuthentication() {
  authChecking.value = true
  try {
    const status = await getAuthStatus()
    authRequired.value = Boolean(status.required)
    authenticated.value = Boolean(status.authenticated)
    if (authenticated.value) await initializeCoreData()
  } catch (err) {
    console.error('Failed to check authentication:', err)
    authRequired.value = true
    authenticated.value = false
  } finally {
    authChecking.value = false
  }
}

onMounted(() => {
  removeAuthListener = onAuthenticationRequired(() => {
    authRequired.value = true
    authenticated.value = false
    coreInitialized = false
  })
  checkAuthentication()
})

onUnmounted(() => removeAuthListener?.())
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
  transition: opacity var(--motion-slow) ease-out;
}
.main-content { position: relative; z-index: 1; }
.main-content {
  flex: 1;
  overflow: hidden;
  position: relative;
}

.auth-loading {
  position: relative;
  z-index: 2;
  min-height: 100vh;
  display: grid;
  place-items: center;
  color: var(--primary);
}

.auth-loading :deep(svg) {
  animation: auth-spin 0.8s linear infinite;
}

@keyframes auth-spin {
  to { transform: rotate(360deg); }
}

/* 路由切换动画 - 双向滑动 */
.slide-left-enter-active,
.slide-left-leave-active,
.slide-right-enter-active,
.slide-right-leave-active {
  transition: opacity var(--motion-base) var(--ease-standard), transform var(--motion-base) var(--ease-emphasized);
}

.slide-left-enter-from {
  transform: translateX(18px);
  opacity: 0;
}

.slide-left-leave-to {
  transform: translateX(-12px);
  opacity: 0;
}

.slide-right-enter-from {
  transform: translateX(-18px);
  opacity: 0;
}

.slide-right-leave-to {
  transform: translateX(12px);
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .slide-left-enter-active,
  .slide-left-leave-active,
  .slide-right-enter-active,
  .slide-right-leave-active,
  .bg-layer.bg-visible {
    transition: none;
  }
}
</style>
