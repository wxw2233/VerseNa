<template>
  <div class="asset-uploader">
    <h3>素材装饰</h3>
    <p class="hint">点击示意图位置或下方素材行上传图片</p>

    <!-- 示意图 -->
    <div class="diagram">
      <div class="diagram-sidebar">
        <div class="diagram-label clickable" @click="scrollToAsset('sidebar-bg')">⑥ 侧栏</div>
        <div class="diagram-divider clickable" @click="scrollToAsset('divider')">⑦</div>
      </div>
      <div class="diagram-main">
        <div class="diagram-chat" @click="scrollToAsset('bg')">
          <span class="diagram-label">① 背景</span>
          <div class="diagram-bubble-user" @click.stop="scrollToAsset('bubble-user')">④</div>
          <div class="diagram-bubble-agent" @click.stop="scrollToAsset('bubble-agent')">⑤</div>
        </div>
        <div class="diagram-avatar" @click="scrollToAsset('avatar')">②③</div>
        <div class="diagram-input" @click="scrollToAsset('input-bg')">
          <span>⑧</span>
          <span class="diagram-send" @click.stop="scrollToAsset('send-btn')">⑨</span>
        </div>
      </div>
    </div>

    <!-- 9 个素材上传行 -->
    <div class="asset-rows">
      <div
        v-for="(info, key) in assetList"
        :key="key"
        :ref="el => { if (el) rowRefs[key] = el }"
        class="asset-row"
      >
        <span class="row-num">{{ info.num }}</span>
        <span class="row-label">{{ info.label }}</span>
        <div class="row-preview" @click="uploadAsset(key)">
          <img v-if="assets[key]" :src="assets[key]" class="thumb" />
          <div v-else class="thumb-placeholder">+</div>
        </div>
        <label class="upload-btn">
          上传
          <input type="file" accept="image/*" class="hidden-input" @change="onFileChange($event, key)" />
        </label>
        <button v-if="assets[key]" class="remove-btn" @click="removeAsset(key)">移除</button>
        <span v-else class="remove-placeholder"></span>

        <!-- 不透明度滑块（仅聊天背景） -->
        <div v-if="key === 'bg' && assets.bg" class="opacity-control">
          <label>不透明度</label>
          <input type="range" min="0" max="1" step="0.1" v-model.number="chatStore.bgOpacity" />
          <span>{{ (chatStore.bgOpacity * 100).toFixed(0) }}%</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, onMounted, watch } from 'vue'
import { useThemeStore } from '../stores/theme'
import { useChatStore } from '../stores/chat'

const themeStore = useThemeStore()
const chatStore = useChatStore()

const assetList = {
  bg: { num: '①', label: '聊天背景' },
  avatar: { num: '②', label: '角色头像' },
  'avatar-frame': { num: '③', label: '头像框' },
  'bubble-user': { num: '④', label: '用户气泡装饰' },
  'bubble-agent': { num: '⑤', label: 'Agent气泡装饰' },
  'sidebar-bg': { num: '⑥', label: '侧栏背景' },
  divider: { num: '⑦', label: '会话分隔线' },
  'input-bg': { num: '⑧', label: '输入框背景' },
  'send-btn': { num: '⑨', label: '发送按钮' },
}

const assets = reactive({})
const rowRefs = {}

const assetFileMap = {}
for (const key of Object.keys(assetList)) {
  assets[key] = ''
  assetFileMap[key] = `${key}.png`
}

watch(() => themeStore.current, () => loadAssets())
onMounted(() => loadAssets())

function scrollToAsset(key) {
  const el = rowRefs[key]
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

async function loadAssets() {
  const themeId = themeStore.current
  for (const key of Object.keys(assetList)) {
    const filename = assetFileMap[key]
    try {
      const resp = await fetch(`/api/themes/${themeId}/assets/${filename}`)
      assets[key] = resp.ok ? `/api/themes/${themeId}/assets/${filename}` : ''
    } catch {
      assets[key] = ''
    }
  }
}

async function uploadAsset(type) {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*'
  input.onchange = (e) => doUpload(e.target.files[0], type)
  input.click()
}

function onFileChange(e, type) {
  doUpload(e.target.files[0], type)
}

async function doUpload(file, type) {
  if (!file) return
  const targetName = assetFileMap[type]
  const renamedFile = new File([file], targetName, { type: file.type })
  const formData = new FormData()
  formData.append('file', renamedFile)

  const resp = await fetch(`/api/themes/${themeStore.current}/upload`, {
    method: 'POST',
    body: formData,
  })
  if (resp.ok) {
    assets[type] = `/api/themes/${themeStore.current}/assets/${targetName}?t=${Date.now()}`
  }
}

async function removeAsset(type) {
  if (!confirm('确定移除这个素材？')) return
  await fetch(`/api/themes/${themeStore.current}/assets/${assetFileMap[type]}`, { method: 'DELETE' }).catch(() => {})
  assets[type] = ''
}
</script>

<style scoped>
.asset-uploader {
  margin-bottom: 24px;
}
.asset-uploader h3 {
  font-size: 16px;
  margin-bottom: 4px;
  color: var(--text-primary);
}
.hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

/* ===== 示意图 ===== */
.diagram {
  display: flex;
  border: 2px dashed var(--border, #444);
  border-radius: 10px;
  background: var(--bg-secondary, #1a1a2e);
  padding: 16px;
  gap: 12px;
  margin-bottom: 20px;
  min-height: 200px;
  font-size: 12px;
  color: var(--text-secondary, #aaa);
}
.diagram-sidebar {
  width: 64px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}
.diagram-sidebar .diagram-label {
  padding: 8px 4px;
  border: 1px dashed var(--border, #555);
  border-radius: 6px;
  text-align: center;
  width: 100%;
}
.diagram-sidebar .diagram-divider {
  flex: 1;
  width: 100%;
  border: 1px dashed var(--border, #555);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.diagram-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  position: relative;
}
.diagram-chat {
  flex: 1;
  border: 1px dashed var(--border, #555);
  border-radius: 8px;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  cursor: pointer;
  position: relative;
  min-height: 80px;
}
.diagram-chat:hover { border-color: var(--primary, #5b7fff); }
.diagram-chat > .diagram-label { align-self: flex-start; }
.diagram-bubble-user {
  align-self: flex-end;
  background: var(--primary, #5b7fff);
  color: #fff;
  padding: 4px 10px;
  border-radius: 8px 8px 2px 8px;
  cursor: pointer;
  max-width: 60%;
  text-align: center;
}
.diagram-bubble-agent {
  align-self: flex-start;
  background: var(--bg-tertiary, #2a2a3e);
  color: var(--text-primary, #eee);
  padding: 4px 10px;
  border-radius: 8px 8px 8px 2px;
  cursor: pointer;
  max-width: 60%;
  text-align: center;
}
.diagram-avatar {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 44px;
  height: 44px;
  border: 2px dashed var(--border, #555);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  cursor: pointer;
  background: var(--bg-secondary, #1a1a2e);
}
.diagram-avatar:hover { border-color: var(--primary, #5b7fff); }
.diagram-input {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px dashed var(--border, #555);
  border-radius: 8px;
  padding: 8px 12px;
  cursor: pointer;
}
.diagram-input:hover { border-color: var(--primary, #5b7fff); }
.diagram-input span:first-child { flex: 1; }
.diagram-send {
  background: var(--primary, #5b7fff);
  color: #fff;
  padding: 4px 10px;
  border-radius: 6px;
  cursor: pointer;
}

/* ===== 素材行 ===== */
.asset-rows {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.asset-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.row-num {
  width: 24px;
  text-align: center;
  font-size: 14px;
  color: var(--primary, #5b7fff);
  flex-shrink: 0;
}
.row-label {
  width: 100px;
  font-size: 13px;
  color: var(--text-primary, #eee);
  flex-shrink: 0;
}
.row-preview {
  width: 48px;
  height: 48px;
  border: 1px dashed var(--border, #444);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  overflow: hidden;
  flex-shrink: 0;
  transition: border-color 0.2s;
}
.row-preview:hover { border-color: var(--primary, #5b7fff); }
.thumb {
  width: 48px;
  height: 48px;
  object-fit: cover;
}
.thumb-placeholder {
  font-size: 18px;
  color: var(--text-secondary, #777);
}
.upload-btn {
  padding: 4px 12px;
  border: 1px solid var(--border, #444);
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  color: var(--text-primary, #eee);
  background: transparent;
  transition: background 0.2s;
}
.upload-btn:hover { background: var(--bg-tertiary, #2a2a3e); }
.hidden-input {
  display: none;
}
.remove-btn {
  padding: 4px 12px;
  background: transparent;
  border: 1px solid #ff4757;
  border-radius: 6px;
  color: #ff4757;
  cursor: pointer;
  font-size: 12px;
}
.remove-btn:hover { background: #ff4757; color: white; }
.remove-placeholder {
  width: 48px;
}

/* 不透明度 */
.opacity-control {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-basis: 100%;
  padding-left: 34px;
}
.opacity-control label {
  font-size: 11px;
  color: var(--text-secondary, #777);
}
.opacity-control input[type="range"] {
  flex: 1;
  max-width: 200px;
}
.opacity-control span {
  font-size: 11px;
  color: var(--text-secondary, #777);
  min-width: 32px;
}
</style>
