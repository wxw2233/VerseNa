<template>
  <div class="settings">
    <ThemeSwitcher />
    <hr style="border-color: var(--border); margin: 24px 0;" />
    <h2>模型配置</h2>
    <div class="form-group">
      <label>API Base URL</label>
      <input v-model="form.base_url" placeholder="https://api.deepseek.com/v1" />
    </div>
    <div class="form-group">
      <label>API Key</label>
      <input v-model="form.api_key" type="password" placeholder="sk-..." />
    </div>
    <div class="form-group">
      <label>模型名称</label>
      <input v-model="form.model_name" placeholder="deepseek-chat" />
    </div>
    <button @click="save">保存</button>
  </div>
</template>

<script setup>
import { reactive, onMounted } from 'vue'
import ThemeSwitcher from '../components/ThemeSwitcher.vue'

const form = reactive({ api_key: '', base_url: '', model_name: '' })

onMounted(async () => {
  const resp = await fetch('/api/config/model')
  const data = await resp.json()
  form.base_url = data.base_url || ''
  form.model_name = data.model_name || ''
})

async function save() {
  await fetch('/api/config/model', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(form)
  })
  alert('保存成功')
}
</script>

<style scoped>
.settings {
  max-width: 500px;
  margin: 40px auto;
  padding: 20px;
}
.form-group {
  margin-bottom: 16px;
}
label {
  display: block;
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}
input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
}
button {
  padding: 10px 24px;
  background: var(--primary);
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}
</style>
