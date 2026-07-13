<template>
  <div class="theme-creator">
    <h3>创建新主题</h3>
    <div class="form-row">
      <label>主题 ID</label>
      <input v-model="form.id" placeholder="my-theme" />
    </div>
    <div class="form-row">
      <label>主题名称</label>
      <input v-model="form.name" placeholder="我的主题" />
    </div>
    <div class="color-grid">
      <div class="color-item" v-for="key in colorKeys" :key="key.key">
        <label>{{ key.label }}</label>
        <div class="color-input">
          <input type="color" v-model="form[key.key]" />
          <span>{{ form[key.key] }}</span>
        </div>
      </div>
    </div>
    <button @click="create" :disabled="!form.id || !form.name">创建主题</button>
    <div v-if="msg" class="msg">{{ msg }}</div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useThemeStore } from '../stores/theme'

const themeStore = useThemeStore()
const msg = ref('')

const form = reactive({
  id: '', name: '',
  primary: '#7c5cfc', bg_primary: '#0f0f1a', bg_secondary: '#1a1a2e',
  text_primary: '#e8e8f0', text_secondary: '#8888aa', border: '#2a2a40',
})

const colorKeys = [
  { key: 'primary', label: '主色调' },
  { key: 'bg_primary', label: '主背景' },
  { key: 'bg_secondary', label: '次背景' },
  { key: 'text_primary', label: '主文字' },
  { key: 'text_secondary', label: '次文字' },
  { key: 'border', label: '边框' },
]

async function create() {
  const resp = await fetch('/api/themes/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(form),
  })
  if (resp.ok) {
    msg.value = '创建成功！'
    await themeStore.fetchThemes()
    form.id = ''
    form.name = ''
  } else {
    const err = await resp.json()
    msg.value = err.detail || '创建失败'
  }
}
</script>

<style scoped>
.theme-creator { margin-bottom: 24px; }
.theme-creator h3 { font-size: 16px; margin-bottom: 12px; color: var(--text-primary); }
.form-row { margin-bottom: 10px; }
.form-row label { display: block; font-size: 13px; color: var(--text-secondary); margin-bottom: 4px; }
.form-row input {
  width: 100%; padding: 8px; border: 1px solid var(--border); border-radius: 6px;
  background: var(--bg-primary); color: var(--text-primary); font-size: 13px;
}
.color-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin: 12px 0; }
.color-item label { font-size: 12px; color: var(--text-secondary); }
.color-input { display: flex; align-items: center; gap: 6px; }
.color-input input[type="color"] { width: 32px; height: 32px; border: none; cursor: pointer; }
.color-input span { font-size: 11px; color: var(--text-secondary); }
button {
  padding: 8px 20px; background: var(--primary); color: white; border: none;
  border-radius: 6px; cursor: pointer; font-size: 13px;
}
button:disabled { opacity: 0.5; cursor: not-allowed; }
.msg { margin-top: 8px; font-size: 13px; color: var(--primary); }
</style>
