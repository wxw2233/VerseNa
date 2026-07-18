<template>
  <div class="slot-grid">
    <div v-for="slot in slots" :key="slot.key" class="slot-card">
      <div class="slot-name">{{ slot.label }}</div>
      <div class="slot-preview" @click="triggerUpload(slot.key)">
        <img v-if="slotImages[slot.key]" :src="slotImages[slot.key]" class="slot-img" />
        <span v-else class="slot-placeholder">+</span>
      </div>
      <button class="slot-upload" @click="triggerUpload(slot.key)">上传</button>
      <button v-if="slotImages[slot.key]" class="slot-clear" @click="clearSlot(slot.key)">清除</button>
      <input type="file" :ref="el => inputRefs[slot.key] = el" @change="handleUpload($event, slot.key)" accept="image/*" hidden />
    </div>
  </div>
</template>

<script setup>
import { reactive, onMounted, watch } from 'vue'
import { useThemeStore } from '../stores/theme'
import { useChatStore } from '../stores/chat'

const themeStore = useThemeStore()
const chatStore = useChatStore()

const slots = [
  { key: 'topbar-bg',    label: '顶栏背景' },
  { key: 'sidebar-bg',   label: '侧栏背景' },
  { key: 'sidebar-divider', label: '分隔线' },
  { key: 'chat-bg',      label: '聊天背景' },
  { key: 'bubble-user',  label: '用户气泡' },
  { key: 'bubble-agent', label: 'Agent气泡' },
  { key: 'input-bg',     label: '输入框' },
  { key: 'send-btn',     label: '发送按钮' },
  { key: 'card-bg',      label: '设置卡片' },
  { key: 'avatar-frame', label: '头像框' },
  { key: 'corner-decor', label: '右下装饰' },
]

const slotImages = reactive({})
const inputRefs = {}

// 文件映射（服务端文件名固定）
const assetFileMap = {}
for (const s of slots) {
  assetFileMap[s.key] = `${s.key}.png`
}

watch(() => themeStore.current, () => loadAssets())
onMounted(() => loadAssets())

async function loadAssets() {
  const themeId = themeStore.current
  if (!themeId || themeId === 'null' || themeId === 'undefined') return
  for (const s of slots) {
    const key = s.key
    const filename = assetFileMap[key]
    try {
      const resp = await fetch(`/api/themes/${themeId}/assets/${filename}`)
      if (resp.ok) {
        slotImages[key] = `/api/themes/${themeId}/assets/${filename}`
        document.documentElement.style.setProperty(`--ui-${key}`, `url(/api/themes/${themeId}/assets/${filename})`)
      } else {
        slotImages[key] = ''
      }
    } catch {
      slotImages[key] = ''
    }
  }
}

function triggerUpload(key) {
  inputRefs[key]?.click()
}

async function handleUpload(event, key) {
  const file = event.target.files?.[0]
  if (!file) { alert('未选择文件'); return }
  if (file.size === 0) { alert('文件为空'); return }
  alert('上传中: ' + file.name + ' (' + file.size + ' bytes)')
  const targetName = assetFileMap[key]
  const renamedFile = new File([file], targetName, { type: file.type })
  const formData = new FormData()
  formData.append('file', renamedFile)

  const resp = await fetch(`/api/themes/${themeStore.current}/upload`, {
    method: 'POST',
    body: formData,
  })
  if (resp.ok) {
    const url = `/api/themes/${themeStore.current}/assets/${targetName}?t=${Date.now()}`
    slotImages[key] = url
    document.documentElement.style.setProperty('--ui-' + key, 'url(' + url + ')'); applyAsset(key, url)
    applyAsset(key, url)
  }
}

async function clearSlot(key) {
  await fetch(`/api/themes/${themeStore.current}/assets/${assetFileMap[key]}`, { method: 'DELETE' }).catch(() => {})
  slotImages[key] = ''
  document.documentElement.style.setProperty(`--ui-${key}`, 'none')
}

function applyAsset(key, url) {
  const sel = {
    'topbar-bg': '.top-bar',
    'sidebar-bg': '.sidebar',
    'chat-bg': '.bg-layer',
    'bubble-user': '.bubble-row.user .bubble',
    'bubble-agent': '.bubble-row.assistant .bubble',
    'input-bg': '.input-bar',
    'send-btn': '.input-bar button',
    'card-bg': '.settings-card',
    'avatar-frame': '.avatar-icon',
    'corner-decor': '.corner-decor'
  }
  const selector = sel[key]
  if (selector) {
    const el = document.querySelector(selector)
    if (el) {
      el.style.backgroundImage = 'url(' + url + ')'
      el.style.backgroundSize = key === 'chat-bg' ? 'cover' : 'auto'
    }
  }
}

</script>

<style scoped>
.slot-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.slot-card { text-align: center; padding: 8px; border: 1px solid var(--border); border-radius: var(--card-radius); background: var(--card-bg); }
.slot-name { font-size: 12px; color: var(--text-secondary); margin-bottom: 6px; }
.slot-preview { width: 100%; height: 60px; border: 1px dashed var(--border); border-radius: 4px; display: flex; align-items: center; justify-content: center; cursor: pointer; overflow: hidden; }
.slot-placeholder { font-size: 24px; color: var(--text-secondary); }
.slot-img { width: 100%; height: 100%; object-fit: cover; }
.slot-upload, .slot-clear { margin-top: 4px; padding: 2px 8px; border: none; border-radius: 4px; font-size: 11px; cursor: pointer; }
.slot-upload { background: var(--primary); color: white; }
.slot-clear { background: transparent; color: var(--text-secondary); }
</style>
