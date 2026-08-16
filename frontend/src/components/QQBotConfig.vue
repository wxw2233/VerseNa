<template>
  <div class="qq-config">
    <h3>QQ 机器人配置</h3>
    <div class="form-row">
      <label>App ID</label>
      <input v-model="form.app_id" placeholder="QQ 开放平台 App ID" />
    </div>
    <div class="form-row">
      <label>App Secret</label>
      <input v-model="form.app_secret" type="password" :placeholder="hasSecret ? '已保存，留空保持不变' : 'App Secret'" />
    </div>
    <div class="form-row">
      <label>
        <input type="checkbox" v-model="form.sandbox" />
        沙箱模式（测试用）
      </label>
    </div>
    <div class="form-row">
      <label>连接模式</label>
      <div class="webhook-url">WebSocket 长连接（无需公网地址）</div>
    </div>
    <button @click="save">保存配置</button>
    <div v-if="msg" class="msg" :class="{ error: isError }">{{ msg }}</div>
    <div class="status">
      状态：<span :class="{ online: botStatus === '已连接', offline: botStatus !== '已连接' }">{{ botStatus }}</span>
    </div>
  </div>
</template>

<script setup>
import { reactive, onMounted, ref } from 'vue'

const form = reactive({ app_id: '', app_secret: '', sandbox: true })
const msg = ref('')
const isError = ref(false)
const botStatus = ref('未连接')
const hasSecret = ref(false)

onMounted(async () => {
  const resp = await fetch('/api/qq/config')
  if (resp.ok) {
    const data = await resp.json()
    form.app_id = data.app_id || ''
    form.app_secret = ''
    hasSecret.value = data.has_secret === true
    form.sandbox = data.sandbox !== false
    botStatus.value = data.bot_status || '未连接'
  }
})

async function save() {
  msg.value = ''
  isError.value = false
  const resp = await fetch('/api/qq/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(form),
  })
  if (resp.ok) {
    const data = await resp.json()
    if (form.app_secret) hasSecret.value = true
    form.app_secret = ''
    botStatus.value = data.bot_status || '未知'
    msg.value = data.bot_status === '已连接' ? '保存成功，Bot 已连接！' : data.bot_status
    isError.value = data.bot_status !== '已连接'
  } else {
    msg.value = '保存失败'
    isError.value = true
  }
}
</script>

<style scoped>
.qq-config { margin-bottom: 24px; }
.qq-config h3 { font-size: 16px; margin-bottom: 12px; color: var(--text-primary); }
.form-row { margin-bottom: 12px; }
.form-row label { display: block; font-size: 13px; color: var(--text-secondary); margin-bottom: 4px; }
.form-row input[type="text"],
.form-row input[type="password"] {
  width: 100%; padding: 8px; border: 1px solid var(--border); border-radius: 6px;
  background: var(--bg-primary); color: var(--text-primary); font-size: 13px;
}
.form-row input[type="checkbox"] { margin-right: 6px; }
.webhook-url {
  padding: 8px 12px; background: var(--bg-primary); border: 1px solid var(--border);
  border-radius: 6px; font-size: 12px; color: var(--primary); font-family: monospace;
}
button {
  padding: 8px 20px; background: var(--primary); color: white; border: none;
  border-radius: 6px; cursor: pointer; font-size: 13px;
}
.msg { margin-top: 8px; font-size: 13px; color: var(--primary); }
.msg.error { color: #ff4757; }
.status { margin-top: 12px; font-size: 13px; color: var(--text-secondary); }
.status .online { color: #2ed573; font-weight: 600; }
.status .offline { color: #ff4757; }
</style>
