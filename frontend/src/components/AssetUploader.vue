<template>
  <div class="bg-uploader">
    <h3>聊天背景</h3>
    <p class="hint">上传后将替换聊天区域的背景图</p>
    <div class="bg-preview" @click="triggerUpload">
      <img v-if="bgUrl" :src="bgUrl" class="bg-img" />
      <span v-else class="bg-placeholder">+ 点击上传背景图</span>
    </div>
    <div class="bg-actions">
      <button class="bg-upload" @click="triggerUpload">上传图片</button>
      <button v-if="bgUrl" class="bg-clear" @click="clearBg">清除背景</button>
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

onMounted(() => {
  loadBg()
})

watch(() => themeStore.current, () => {
  loadBg()
})

async function loadBg() {
  const themeId = themeStore.current
  if (!themeId || themeId === 'null') return
  try {
    const resp = await fetch('/api/themes/' + themeId + '/assets/bg.png')
    if (resp.ok) {
      bgUrl.value = '/api/themes/' + themeId + '/assets/bg.png?t=' + Date.now()
      applyBg(bgUrl.value)
    } else {
      bgUrl.value = ''
    }
  } catch {}
}

function triggerUpload() {
  fileInput.value?.click()
}

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

  const resp = await fetch('/api/themes/' + themeId + '/upload', {
    method: 'POST',
    body: formData,
  })
  if (resp.ok) {
    bgUrl.value = '/api/themes/' + themeId + '/assets/bg.png?t=' + Date.now()
    applyBg(bgUrl.value)
  } else {
    alert('上传失败')
  }
}

function applyBg(url) {
  const bg = document.querySelector('.bg-layer')
  if (bg) {
    bg.style.backgroundImage = 'url(' + url + ')'
    bg.style.backgroundSize = 'cover'
    bg.style.backgroundPosition = 'center'
  }
}

function clearBg() {
  bgUrl.value = ''
  const bg = document.querySelector('.bg-layer')
  if (bg) bg.style.backgroundImage = ''
}
</script>
