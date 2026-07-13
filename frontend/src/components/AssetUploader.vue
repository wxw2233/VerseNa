<template>
  <div class="asset-uploader">
    <h3>素材装饰</h3>
    <p class="hint">上传图片装饰你的聊天界面</p>
    
    <div class="asset-grid">
      <!-- 聊天背景图 -->
      <div class="asset-item">
        <div class="asset-label">聊天背景</div>
        <div class="asset-preview" @click="uploadAsset('bg')">
          <img v-if="assets.bg" :src="assets.bg" class="preview-img bg-preview" />
          <div v-else class="placeholder">点击上传</div>
        </div>
        <button v-if="assets.bg" class="remove-btn" @click="removeAsset('bg')">移除</button>
        <div v-if="assets.bg" class="opacity-control">
          <label>不透明度</label>
          <input type="range" min="0" max="1" step="0.1" v-model.number="bgOpacity" @input="applyBgOpacity" />
          <span>{{ (bgOpacity * 100).toFixed(0) }}%</span>
        </div>
      </div>

      <!-- 角色头像 -->
      <div class="asset-item">
        <div class="asset-label">角色头像</div>
        <div class="asset-preview avatar-preview" @click="uploadAsset('avatar')">
          <img v-if="assets.avatar" :src="assets.avatar" class="preview-img avatar-img" />
          <div v-else class="placeholder">点击上传</div>
        </div>
        <button v-if="assets.avatar" class="remove-btn" @click="removeAsset('avatar')">移除</button>
      </div>

      <!-- 头像框 -->
      <div class="asset-item">
        <div class="asset-label">头像框</div>
        <div class="asset-preview avatar-preview" @click="uploadAsset('avatar-frame')">
          <img v-if="assets['avatar-frame']" :src="assets['avatar-frame']" class="preview-img" />
          <div v-else class="placeholder">点击上传</div>
        </div>
        <button v-if="assets['avatar-frame']" class="remove-btn" @click="removeAsset('avatar-frame')">移除</button>
      </div>

      <!-- 用户气泡装饰 -->
      <div class="asset-item">
        <div class="asset-label">用户气泡装饰</div>
        <div class="asset-preview" @click="uploadAsset('bubble-user')">
          <img v-if="assets['bubble-user']" :src="assets['bubble-user']" class="preview-img small" />
          <div v-else class="placeholder">点击上传</div>
        </div>
        <button v-if="assets['bubble-user']" class="remove-btn" @click="removeAsset('bubble-user')">移除</button>
      </div>

      <!-- Agent 气泡装饰 -->
      <div class="asset-item">
        <div class="asset-label">Agent 气泡装饰</div>
        <div class="asset-preview" @click="uploadAsset('bubble-agent')">
          <img v-if="assets['bubble-agent']" :src="assets['bubble-agent']" class="preview-img small" />
          <div v-else class="placeholder">点击上传</div>
        </div>
        <button v-if="assets['bubble-agent']" class="remove-btn" @click="removeAsset('bubble-agent')">移除</button>
      </div>
    </div>

    <!-- 导出/导入 -->
    <div class="package-actions">
      <button class="btn-export" @click="exportTheme">导出主题包</button>
      <label class="btn-import">
        导入主题包
        <input type="file" accept=".zip" @change="importTheme" style="display:none" />
      </label>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { useThemeStore } from '../stores/theme'

const themeStore = useThemeStore()
const bgOpacity = ref(0.3)

const assets = reactive({
  bg: '',
  avatar: '',
  'avatar-frame': '',
  'bubble-user': '',
  'bubble-agent': '',
})

const assetFileMap = {
  'bg': 'bg.png',
  'avatar': 'avatar.png',
  'avatar-frame': 'avatar-frame.png',
  'bubble-user': 'bubble-user.png',
  'bubble-agent': 'bubble-agent.png',
}

watch(() => themeStore.current, () => loadAssets())

onMounted(() => loadAssets())

async function loadAssets() {
  const themeId = themeStore.current
  for (const [key, filename] of Object.entries(assetFileMap)) {
    try {
      const resp = await fetch(`/api/themes/${themeId}/assets/${filename}`)
      if (resp.ok) {
        assets[key] = `/api/themes/${themeId}/assets/${filename}`
      } else {
        assets[key] = ''
      }
    } catch {
      assets[key] = ''
    }
  }
}

async function uploadAsset(type) {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*'
  input.onchange = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    const formData = new FormData()
    formData.append('file', file)
    
    // 先删除旧的
    if (assets[type]) {
      await fetch(`/api/themes/${themeStore.current}/assets/${assetFileMap[type]}`, { method: 'DELETE' }).catch(() => {})
    }
    
    const resp = await fetch(`/api/themes/${themeStore.current}/upload`, {
      method: 'POST',
      body: formData,
    })
    if (resp.ok) {
      const data = await resp.json()
      assets[type] = `/api/themes/${themeStore.current}/assets/${data.filename}?t=${Date.now()}`
    }
  }
  input.click()
}

async function removeAsset(type) {
  if (!confirm('确定移除这个素材？')) return
  await fetch(`/api/themes/${themeStore.current}/assets/${assetFileMap[type]}`, { method: 'DELETE' }).catch(() => {})
  assets[type] = ''
}

function applyBgOpacity() {
  let el = document.getElementById('bg-opacity-style')
  if (!el) {
    el = document.createElement('style')
    el.id = 'bg-opacity-style'
    document.head.appendChild(el)
  }
  el.textContent = `.chat-main::before { opacity: ${bgOpacity.value}; }`
}

async function exportTheme() {
  const resp = await fetch(`/api/themes/${themeStore.current}/export`)
  if (resp.ok) {
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${themeStore.current}-theme.zip`
    a.click()
    URL.revokeObjectURL(url)
  }
}

async function importTheme(e) {
  const file = e.target.files[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  const resp = await fetch('/api/themes/import', { method: 'POST', body: formData })
  if (resp.ok) {
    await themeStore.fetchThemes()
    alert('导入成功！')
  } else {
    alert('导入失败')
  }
}
</script>

<style scoped>
.asset-uploader { margin-bottom: 24px; }
.asset-uploader h3 { font-size: 16px; margin-bottom: 4px; color: var(--text-primary); }
.hint { font-size: 12px; color: var(--text-secondary); margin-bottom: 12px; }
.asset-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.asset-item { display: flex; flex-direction: column; gap: 6px; }
.asset-label { font-size: 12px; color: var(--text-secondary); }
.asset-preview {
  width: 100%; height: 80px; border: 1px dashed var(--border); border-radius: 8px;
  display: flex; align-items: center; justify-content: center; cursor: pointer;
  overflow: hidden; transition: border-color 0.2s;
}
.asset-preview:hover { border-color: var(--primary); }
.placeholder { font-size: 12px; color: var(--text-secondary); }
.preview-img { width: 100%; height: 100%; object-fit: cover; }
.preview-img.small { width: 48px; height: 48px; object-fit: contain; }
.bg-preview { object-fit: cover; opacity: 0.5; }
.avatar-preview { height: 80px; width: 80px; border-radius: 50%; }
.avatar-img { border-radius: 50%; }
.remove-btn {
  padding: 2px 8px; background: transparent; border: 1px solid #ff4757;
  border-radius: 4px; color: #ff4757; cursor: pointer; font-size: 11px;
  align-self: flex-start;
}
.remove-btn:hover { background: #ff4757; color: white; }
.opacity-control { display: flex; align-items: center; gap: 6px; }
.opacity-control label { font-size: 11px; color: var(--text-secondary); }
.opacity-control input { flex: 1; }
.opacity-control span { font-size: 11px; color: var(--text-secondary); min-width: 30px; }
.package-actions { display: flex; gap: 10px; margin-top: 16px; }
.btn-export, .btn-import {
  flex: 1; padding: 8px 12px; background: transparent;
  border: 1px solid var(--border); border-radius: 6px;
  color: var(--text-secondary); cursor: pointer; font-size: 13px;
  text-align: center;
}
.btn-export:hover, .btn-import:hover { border-color: var(--primary); color: var(--primary); }
</style>
