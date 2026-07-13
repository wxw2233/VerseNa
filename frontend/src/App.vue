<template>
  <div id="app-root">
    <nav class="top-bar">
      <router-link to="/" class="nav-title">次元人格</router-link>
      <a class="nav-link" :class="{ active: isSettings }" @click="toggleSettings">{{ isSettings ? '返回' : '设置' }}</a>
    </nav>
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
const route = useRoute()
const router = useRouter()
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
