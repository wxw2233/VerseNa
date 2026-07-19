<template>
  <div class="tab-content">
    <h2>工具</h2>
    <div class="tool-list">
      <div class="tool-card">
        <div class="tool-icon">🔍</div>
        <div class="tool-info">
          <div class="tool-name">web_search</div>
          <div class="tool-desc">联网搜索工具，支持通过搜索引擎查询实时信息</div>
        </div>
        <span class="tool-badge builtin">内置</span>
      </div>
      <div class="tool-card">
        <div class="tool-icon">💻</div>
        <div class="tool-info">
          <div class="tool-name">code_exec</div>
          <div class="tool-desc">代码执行工具，支持在沙箱环境中运行 Python 代码</div>
        </div>
        <span class="tool-badge builtin">内置</span>
      </div>
      <div class="tool-card">
        <div class="tool-icon">📁</div>
        <div class="tool-info">
          <div class="tool-name">file_manager</div>
          <div class="tool-desc">文件管理器，支持读取、写入、搜索、编辑、复制、移动、删除等操作</div>
        </div>
        <span class="tool-badge builtin">内置</span>
      </div>
    </div>

    <hr class="divider" />
    <h3>信任模式</h3>
    <div class="trust-mode-row">
      <div class="trust-info">
        <div class="trust-label">🔒 信任模式</div>
        <div class="trust-desc">开启后，除系统核心文件外，所有文件操作无需确认直接执行。</div>
      </div>
      <label class="toggle-switch">
        <input type="checkbox" v-model="trustMode" @change="saveTrustMode" />
        <span class="toggle-slider"></span>
      </label>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const trustMode = ref(false)

async function loadTrustMode() {
  try {
    const resp = await fetch('/api/config/trust_mode')
    const data = await resp.json()
    trustMode.value = data.enabled === true || data.enabled === 'true'
  } catch { trustMode.value = false }
}

async function saveTrustMode() {
  try {
    await fetch('/api/config/trust_mode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: trustMode.value })
    })
  } catch {}
}

onMounted(() => loadTrustMode())
</script>

<style scoped>
.tool-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.tool-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 20px;
  background: rgba(20, 20, 40, 0.60);
  box-shadow: var(--ui-border);
  border-radius: var(--radius);
}
.tool-icon {
  font-size: 24px;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(20, 20, 40, 0.60);
  border-radius: 8px;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
}
.tool-info { flex: 1; }
.tool-name {
  font-size: 14px;
  font-weight: 600;
  font-family: monospace;
}
.tool-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 2px;
}
.tool-badge {
  font-size: 11px;
  padding: 2px 10px;
  border-radius: 10px;
  background: rgba(124, 92, 252, 0.12);
  color: var(--primary);
  font-weight: 600;
}

.divider {
  border: none;
  box-shadow: 0 -1px 0 rgba(255, 255, 255, 0.04);
  margin: 28px 0;
  height: 1px;
}

.trust-mode-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  background: rgba(20, 20, 40, 0.60);
  border-radius: var(--radius);
  box-shadow: var(--ui-border);
}
.trust-label { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.trust-desc { font-size: 12px; color: var(--text-secondary); margin-top: 4px; }
.toggle-switch {
  position: relative;
  width: 44px;
  height: 24px;
  flex-shrink: 0;
}
.toggle-switch input { opacity: 0; width: 0; height: 0; }
.toggle-slider {
  position: absolute;
  cursor: pointer;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(255,255,255,0.12);
  border-radius: 12px;
  transition: 0.2s;
}
.toggle-slider::before {
  content: '';
  position: absolute;
  height: 18px; width: 18px;
  left: 3px; bottom: 3px;
  background: white;
  border-radius: 50%;
  transition: 0.2s;
}
.toggle-switch input:checked + .toggle-slider { background: var(--primary); }
.toggle-switch input:checked + .toggle-slider::before { transform: translateX(20px); }

h3 {
  font-size: 16px;
  margin-bottom: 12px;
}
</style>
