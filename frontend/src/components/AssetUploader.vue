<template>
  <div class="asset-uploader">
    <!-- 主题包图标 -->
    <div class="section">
      <h3>主题包图标</h3>
      <p class="hint">上传图片作为主题包的显示图标</p>
      <div class="icon-preview" @click="triggerIconUpload">
        <img v-if="iconUrl" :src="iconUrl" class="icon-img" />
        <span v-else class="icon-placeholder">+</span>
      </div>
      <div class="actions">
        <button class="btn-upload" @click="triggerIconUpload">上传图标</button>
        <button v-if="iconUrl" class="btn-clear" @click="clearIcon">清除</button>
      </div>
      <input type="file" ref="iconInput" @change="handleIconUpload" accept="image/*" hidden />
    </div>

    <!-- 聊天背景 -->
    <div class="section">
      <h3>聊天背景</h3>
      <p class="hint">上传后将替换整个页面的背景图</p>
      <div class="bg-preview" @click="triggerBgUpload">
        <img v-if="bgUrl" :src="bgUrl" class="bg-img" />
        <span v-else class="bg-placeholder">+ 点击上传背景图</span>
      </div>
      <div class="actions">
        <button class="btn-upload" @click="triggerBgUpload">上传背景</button>
        <button v-if="bgUrl" class="btn-clear" @click="clearBg">清除背景</button>
      </div>
      <div class="opacity-control">
        <label>透明度 <span>{{ bgOpacity }}</span></label>
        <input type="range" min="0.05" max="1" step="0.05" v-model.number="bgOpacity" @input="updateOpacity" />
      </div>
      <input type="file" ref="bgInput" @change="handleBgUpload" accept="image/*" hidden />
    </div>

    <!-- 参考音频（音色克隆） -->
    <div class="section">
      <h3>参考音频</h3>
      <p class="hint">上传一段角色语音（3-10秒），用于 TTS 音色克隆</p>
      <div class="audio-preview" v-if="audioUrl">
        <audio :src="audioUrl" controls class="audio-player"></audio>
      </div>
      <div class="audio-empty" v-else>
        <span class="audio-icon">🎵</span>
        <span>未上传参考音频</span>
      </div>
      <div class="actions">
        <button class="btn-upload" @click="triggerAudioUpload">{{ audioUrl ? '更换音频' : '上传音频' }}</button>
        <button v-if="audioUrl" class="btn-clear" @click="clearAudio">清除</button>
      </div>
      <input type="file" ref="audioInput" @change="handleAudioUpload" accept="audio/*" hidden />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'

const props = defineProps({
  packId: { type: String, required: true }
})

const emit = defineEmits(['icon-uploaded'])

const iconInput = ref(null)
const bgInput = ref(null)
const audioInput = ref(null)
const iconUrl = ref('')
const bgUrl = ref('')
const audioUrl = ref('')
const bgOpacity = ref(parseFloat(localStorage.getItem('bg-opacity') || '0.3'))

function updateOpacity() {
  localStorage.setItem('bg-opacity', bgOpacity.value)
  document.documentElement.style.setProperty('--bg-opacity', bgOpacity.value)
}

onMounted(() => {
  loadAssets()
  const savedOpacity = localStorage.getItem('bg-opacity') || '0.3'
  document.documentElement.style.setProperty('--bg-opacity', savedOpacity)
})

watch(() => props.packId, () => { loadAssets() })

async function loadAssets() {
  if (!props.packId) return
  try {
    // 加载图标
    const iconResp = await fetch(`/api/themes/${props.packId}/assets/icon.png`)
    if (iconResp.ok) {
      iconUrl.value = `/api/themes/${props.packId}/assets/icon.png?t=${Date.now()}`
    } else {
      iconUrl.value = ''
    }
  } catch { iconUrl.value = '' }

  try {
    // 加载背景
    const bgResp = await fetch(`/api/themes/${props.packId}/assets/bg.png`)
    if (bgResp.ok) {
      bgUrl.value = `/api/themes/${props.packId}/assets/bg.png?t=${Date.now()}`
      localStorage.setItem('bg-ts', Date.now())
    } else {
      bgUrl.value = ''
    }
  } catch { bgUrl.value = '' }

  try {
    // 加载参考音频
    const audioExts = ['wav', 'mp3', 'm4a', 'ogg']
    audioUrl.value = ''
    for (const ext of audioExts) {
      const resp = await fetch(`/api/themes/${props.packId}/assets/ref_audio.${ext}`)
      if (resp.ok) {
        audioUrl.value = `/api/themes/${props.packId}/assets/ref_audio.${ext}?t=${Date.now()}`
        break
      }
    }
  } catch { audioUrl.value = '' }
}

function triggerIconUpload() { iconInput.value?.click() }
function triggerBgUpload() { bgInput.value?.click() }
function triggerAudioUpload() { audioInput.value?.click() }

async function handleIconUpload(event) {
  const file = event.target.files?.[0]
  if (!file || !props.packId) return
  const formData = new FormData()
  formData.append('file', file, 'icon.png')
  const resp = await fetch(`/api/themes/${props.packId}/upload`, { method: 'POST', body: formData })
  if (resp.ok) {
    iconUrl.value = `/api/themes/${props.packId}/assets/icon.png?t=${Date.now()}`
    emit('icon-uploaded')
  } else {
    alert('图标上传失败')
  }
}

async function handleBgUpload(event) {
  const file = event.target.files?.[0]
  if (!file || !props.packId) return
  const formData = new FormData()
  formData.append('file', file, 'bg.png')
  const resp = await fetch(`/api/themes/${props.packId}/upload`, { method: 'POST', body: formData })
  if (resp.ok) {
    bgUrl.value = `/api/themes/${props.packId}/assets/bg.png?t=${Date.now()}`
    localStorage.setItem('bg-ts', Date.now())
  } else {
    alert('背景上传失败')
  }
}

function clearIcon() { iconUrl.value = '' }
function clearBg() { bgUrl.value = '' }

async function handleAudioUpload(event) {
  const file = event.target.files?.[0]
  if (!file || !props.packId) return
  // 重命名为 ref_audio + 原始扩展名
  const ext = file.name.split('.').pop() || 'wav'
  const formData = new FormData()
  formData.append('file', file, `ref_audio.${ext}`)
  const resp = await fetch(`/api/themes/${props.packId}/upload`, { method: 'POST', body: formData })
  if (resp.ok) {
    audioUrl.value = `/api/themes/${props.packId}/assets/ref_audio.${ext}?t=${Date.now()}`
  }
}

function clearAudio() { audioUrl.value = '' }
</script>

<style scoped>
.asset-uploader { padding: 16px; }
.section { margin-bottom: 24px; }
.section h3 { font-size: 15px; margin-bottom: 4px; color: var(--text-primary); }
.hint { font-size: 12px; color: var(--text-secondary); margin-bottom: 10px; }

.icon-preview {
  width: 64px; height: 64px;
  border: 2px dashed rgba(255,255,255,0.2);
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; overflow: hidden;
  margin-bottom: 8px;
  background: rgba(255,255,255,0.04);
}
.icon-img { width: 100%; height: 100%; object-fit: cover; }
.icon-placeholder { font-size: 24px; color: var(--text-secondary); }

.bg-preview {
  width: 100%; height: 120px;
  border: 2px dashed rgba(255,255,255,0.2);
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; overflow: hidden;
  margin-bottom: 8px;
  background: rgba(255,255,255,0.04);
}
.bg-img { width: 100%; height: 100%; object-fit: cover; }
.bg-placeholder { font-size: 14px; color: var(--text-secondary); }

.actions { display: flex; gap: 8px; }
.btn-upload {
  padding: 6px 16px; background: var(--primary); color: white;
  border: none; border-radius: 6px; cursor: pointer; font-size: 13px;
}
.btn-clear {
  padding: 6px 16px; background: transparent;
  border: 1px solid rgba(255,255,255,0.15); color: var(--text-secondary);
  border-radius: 6px; cursor: pointer; font-size: 13px;
}
.opacity-control { margin-top: 12px; }
.opacity-control label { font-size: 13px; color: var(--text-secondary); display: flex; justify-content: space-between; }
.opacity-control input[type="range"] { width: 100%; margin-top: 4px; accent-color: var(--primary); }

.audio-preview {
  margin-bottom: 8px;
}
.audio-player {
  width: 100%;
  height: 36px;
  border-radius: 8px;
}
.audio-empty {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  border: 2px dashed rgba(255,255,255,0.15);
  border-radius: 8px;
  color: var(--text-secondary);
  font-size: 13px;
  margin-bottom: 8px;
  background: rgba(255,255,255,0.03);
}
.audio-icon { font-size: 20px; }
</style>
