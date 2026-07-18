<template>
  <div class="bg-uploader">
    <h3>聊天背景</h3>
    <p class="hint">上传后将替换整个页面的背景图</p>
    <div class="bg-preview" @click="triggerUpload">
      <img v-if="bgUrl" :src="bgUrl" class="bg-img" />
      <span v-else class="bg-placeholder">+ 点击上传背景图</span>
    </div>
    <div class="bg-actions">
      <button class="bg-upload" @click="triggerUpload">上传图片</button>
      <button v-if="bgUrl" class="bg-clear" @click="clearBg">清除背景</button>
    </div>
    <div class="bg-opacity">
      <label>透明度 <span>{{ bgOpacity }}</span></label>
      <input type="range" min="0.05" max="1" step="0.05" v-model.number="bgOpacity" @input="updateOpacity" />
    </div>
    <input type="file" ref="fileInput" @change="handleUpload" accept="image/*" hidden />
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useThemeStore } from '../stores/theme'

const themeStore = useThemeStore()
const fileInput = ref(null)
const bgUrl = ref('')
const bgOpacity = ref(parseFloat(localStorage.getItem('bg-opacity') || '0.3'))

function updateOpacity() {
  localStorage.setItem('bg-opacity', bgOpacity.value)
  document.documentElement.style.setProperty('--bg-opacity', bgOpacity.value)
}

onMounted(() => {
  loadBg()
  const savedOpacity = localStorage.getItem('bg-opacity') || '0.3'
  document.documentElement.style.setProperty('--bg-opacity', savedOpacity)
})
watch(() => themeStore.current, () => { loadBg() })

async function loadBg() {
  const themeId = themeStore.current
  if (!themeId || themeId === 'null') return
  try {
    const resp = await fetch('/api/themes/' + themeId + '/assets/bg.png')
    if (resp.ok) {
      bgUrl.value = '/api/themes/' + themeId + '/assets/bg.png?t=' + Date.now()
    } else {
      bgUrl.value = ''
    }
  } catch {}
}

function triggerUpload() { fileInput.value?.click() }

async function handleUpload(event) {
  const file = event.target.files?.[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file, 'bg.png')

  const themeId = themeStore.current
  if (!themeId || themeId === 'null') {
    alert('请先应用一个主题包')
    return
  }

  const resp = await fetch('/api/themes/' + themeId + '/upload', { method: 'POST', body: formData })
  if (resp.ok) {
    bgUrl.value = '/api/themes/' + themeId + '/assets/bg.png?t=' + Date.now()
  } else {
    alert('上传失败')
  }
}

function clearBg() { bgUrl.value = '' }
</script>

<style scoped>
.bg-uploader { padding: 16px; }
.bg-uploader h3 { font-size: 16px; margin-bottom: 4px; color: var(--text-primary); }
.bg-uploader .hint { font-size: 12px; color: var(--text-secondary); margin-bottom: 12px; }
.bg-preview { width: 100%; height: 120px; border: 2px dashed var(--border); border-radius: 8px; display: flex; align-items: center; justify-content: center; cursor: pointer; overflow: hidden; margin-bottom: 8px; }
.bg-placeholder { font-size: 14px; color: var(--text-secondary); }
.bg-img { width: 100%; height: 100%; object-fit: cover; }
.bg-actions { display: flex; gap: 8px; }
.bg-upload { padding: 6px 16px; background: var(--primary); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; }
.bg-clear { padding: 6px 16px; background: transparent; border: 1px solid var(--border); color: var(--text-secondary); border-radius: 6px; cursor: pointer; font-size: 13px; }
.bg-opacity { margin-top: 12px; }
.bg-opacity label { font-size: 13px; color: var(--text-secondary); display: flex; justify-content: space-between; }
.bg-opacity input[type="range"] { width: 100%; margin-top: 4px; accent-color: var(--primary); }
</style>
