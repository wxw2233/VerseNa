<template>
  <div id="app-root">
    <nav class="top-bar">
      <router-link to="/" class="nav-title">次元人格</router-link>
      <router-link to="/settings" class="nav-link">设置</router-link>
    </nav>
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

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
}
.nav-link:hover {
  color: var(--primary);
}
.main-content {
  flex: 1;
  overflow: hidden;
}
</style>
