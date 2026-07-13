<template>
  <div class="qq-config">
    <h3>QQ 机器人配置</h3>
    <div class="form-row">
      <label>App ID</label>
      <input v-model="form.app_id" placeholder="QQ 开放平台 App ID" />
    </div>
    <div class="form-row">
      <label>App Secret</label>
      <input v-model="form.app_secret" type="password" placeholder="App Secret" />
    </div>
    <div class="form-row">
      <label>
        <input type="checkbox" v-model="form.sandbox" />
        沙箱模式（测试用）
      </label>
    </div>
    <div class="form-row">
      <label>Webhook 地址</label>
      <div class="webhook-url">POST http://你的域名:8000/api/qq/webhook</div>
    </div>
    <button @click="save">保存配置</button>
    <div v-if="msg" class="msg">{{ msg }}</div>
  </div>
</template>

<script setup>
import { reactive, onMounted, ref } from 'vue'

const form = reactive({ app_id: '', app_secret: '', sandbox: true })
const msg = ref('')

onMounted(async () => {
  const resp = await fetch('/api/qq/config')
  if (resp.ok) {
    const data = await resp.json()
    form.app_id = data.app_id || ''
    form.app_secret = data.app_secret || ''
    form.sandbox = data.sandbox !== false
  }
})

async function save() {
  const resp = await fetch('/api/qq/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(form),
  })
  msg.value = resp.ok ? '保存成功！' : '保存失败'
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
</style>
