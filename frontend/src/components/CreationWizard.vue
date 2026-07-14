<template>
  <div v-if="visible" class="wizard-overlay" @click.self="visible = false">
    <div class="wizard-modal">
      <!-- 步骤指示器 -->
      <div class="step-indicator">
        <div v-for="n in 4" :key="n" class="step-item">
          <div class="step-circle" :class="{ active: step === n, done: step > n }">
            <span v-if="step > n">✓</span>
            <span v-else>{{ n }}</span>
          </div>
          <div v-if="n < 4" class="step-line" :class="{ filled: step > n }"></div>
        </div>
      </div>

      <div class="step-labels">
        <span v-for="(label, idx) in stepLabels" :key="idx" class="step-label" :class="{ active: step === idx + 1 }">{{ label }}</span>
      </div>

      <!-- 步骤 1：选择角色 -->
      <div v-if="step === 1" class="wizard-body">
        <h2 class="wizard-title">选择角色</h2>
        <p class="wizard-desc">选择一个 AI 角色开始对话</p>
        <div class="card-grid">
          <div
            v-for="p in personas"
            :key="p.id"
            class="wizard-card"
            :class="{ selected: selectedPersona === p.id }"
            @click="selectedPersona = p.id"
          >
            <div class="card-avatar">{{ p.name?.charAt(0) || '?' }}</div>
            <div class="card-info">
              <div class="card-name">{{ p.name }}</div>
              <div class="card-desc">{{ p.description }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 步骤 2：选择主题 -->
      <div v-if="step === 2" class="wizard-body">
        <h2 class="wizard-title">选择主题</h2>
        <p class="wizard-desc">选择一个视觉主题</p>
        <div class="card-grid">
          <div
            v-for="t in themes"
            :key="t.id"
            class="wizard-card theme-card"
            :class="{ selected: selectedTheme === t.id }"
            @click="selectedTheme = t.id"
          >
            <div class="theme-preview" :style="{ background: previewColors[t.id] || 'var(--primary)' }"></div>
            <div class="card-info">
              <div class="card-name">{{ t.name }}</div>
              <div class="card-desc">{{ t.description || t.id }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 步骤 3：上传素材 -->
      <div v-if="step === 3" class="wizard-body">
        <h2 class="wizard-title">上传素材</h2>
        <p class="wizard-desc">自定义聊天界面素材（可跳过）</p>
        <div class="asset-diagram">
          <div class="diagram-wrapper">
            <svg viewBox="0 0 360 200" class="diagram-svg">
              <!-- 简化聊天界面示意 -->
              <rect x="10" y="10" width="340" height="180" rx="8" fill="var(--bg-primary)" stroke="var(--border)" stroke-width="1"/>
              <!-- ① 背景区域标注 -->
              <rect x="12" y="12" width="336" height="176" rx="7" fill="none" stroke="var(--primary)" stroke-width="1" stroke-dasharray="4,2" opacity="0.4"/>
              <text x="30" y="30" class="diagram-label" fill="var(--primary)">① 聊天背景</text>
              <!-- ② 头像 -->
              <circle cx="50" cy="80" r="18" fill="var(--bg-secondary)" stroke="var(--primary)" stroke-width="1.5"/>
              <text x="50" y="84" text-anchor="middle" class="diagram-icon" fill="var(--primary)">😊</text>
              <text x="50" y="110" text-anchor="middle" class="diagram-label" fill="var(--text-secondary)">② 头像</text>
              <!-- ③ 头像框 -->
              <circle cx="50" cy="80" r="22" fill="none" stroke="var(--accent)" stroke-width="2" stroke-dasharray="3,2"/>
              <text x="50" y="125" text-anchor="middle" class="diagram-label" fill="var(--text-secondary)">③ 头像框</text>
              <!-- ④ 用户气泡 -->
              <rect x="200" y="55" width="130" height="30" rx="12" fill="var(--primary)" opacity="0.3"/>
              <text x="265" y="74" text-anchor="middle" class="diagram-label" fill="var(--text-primary)">用户消息</text>
              <text x="335" y="74" class="diagram-label" fill="var(--primary)">④</text>
              <!-- ⑤ Agent气泡 -->
              <rect x="80" y="140" width="130" height="30" rx="12" fill="var(--bg-secondary)" stroke="var(--border)" stroke-width="1"/>
              <text x="145" y="159" text-anchor="middle" class="diagram-label" fill="var(--text-primary)">Agent回复</text>
              <text x="215" y="159" class="diagram-label" fill="var(--primary)">⑤</text>
            </svg>
          </div>
        </div>
        <div class="asset-grid">
          <div
            v-for="(asset, key) in assetList"
            :key="key"
            class="asset-slot"
            :class="{ uploaded: uploadedAssets[key] }"
            @click="uploadAsset(key)"
          >
            <div class="asset-num">{{ asset.num }}</div>
            <div class="asset-label">{{ asset.label }}</div>
            <div class="asset-status">
              <span v-if="uploadedAssets[key]" class="status-ok">✓ 已上传</span>
              <span v-else class="status-empty">点击上传</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 步骤 4：完成 -->
      <div v-if="step === 4" class="wizard-body finish-step">
        <h2 class="wizard-title">准备就绪</h2>
        <p class="wizard-desc">确认以下配置</p>
        <div class="summary-card">
          <div class="summary-row">
            <span class="summary-label">角色</span>
            <span class="summary-value">{{ personaName }}</span>
          </div>
          <div class="summary-row">
            <span class="summary-label">主题</span>
            <span class="summary-value">{{ themeName }}</span>
          </div>
          <div class="summary-row">
            <span class="summary-label">自定义素材</span>
            <span class="summary-value">{{ uploadedCount }} / 5</span>
          </div>
        </div>
      </div>

      <!-- 底部按钮 -->
      <div class="wizard-footer">
        <button v-if="step > 1" class="btn-prev" @click="step--">上一步</button>
        <div class="footer-spacer"></div>
        <button v-if="step === 3" class="btn-skip" @click="step++">跳过</button>
        <button v-if="step < 4" class="btn-next" :disabled="!canNext" @click="step++">下一步</button>
        <button v-if="step === 4" class="btn-finish" @click="finish">开始聊天</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { useThemeStore } from '../stores/theme'
import { usePersonaStore } from '../stores/persona'

const themeStore = useThemeStore()
const personaStore = usePersonaStore()

const visible = ref(false)
const step = ref(1)
const personas = ref([])
const themes = ref([])
const selectedPersona = ref('')
const selectedTheme = ref('')
const uploadedAssets = reactive({})

const emit = defineEmits(['complete'])

const stepLabels = ['选择角色', '选择主题', '上传素材', '完成']

const previewColors = {
  default: '#7c5cfc',
  miku: '#39C5BB',
  sakura: '#FFB7C5',
  cyber: '#00f0ff',
  forest: '#2ecc71',
}

const assetList = {
  bg: { num: '①', label: '聊天背景' },
  avatar: { num: '②', label: '角色头像' },
  'avatar-frame': { num: '③', label: '头像框' },
  'bubble-user': { num: '④', label: '用户气泡装饰' },
  'bubble-agent': { num: '⑤', label: 'Agent气泡装饰' },
}

const canNext = computed(() => {
  if (step.value === 1) return !!selectedPersona.value
  if (step.value === 2) return !!selectedTheme.value
  return true
})

const personaName = computed(() => {
  const p = personas.value.find(p => p.id === selectedPersona.value)
  return p ? p.name : selectedPersona.value
})

const themeName = computed(() => {
  const t = themes.value.find(t => t.id === selectedTheme.value)
  return t ? t.name : selectedTheme.value
})

const uploadedCount = computed(() => Object.keys(uploadedAssets).length)

function show() {
  visible.value = true
  step.value = 1
  selectedPersona.value = ''
  selectedTheme.value = ''
  Object.keys(uploadedAssets).forEach(k => delete uploadedAssets[k])
  loadPersonas()
  loadThemes()
}

async function loadPersonas() {
  try {
    const resp = await fetch('/api/personas')
    personas.value = await resp.json()
  } catch (e) {
    console.error('Failed to load personas:', e)
    personas.value = personaStore.personas || []
  }
}

async function loadThemes() {
  try {
    const resp = await fetch('/api/themes')
    themes.value = await resp.json()
  } catch (e) {
    console.error('Failed to load themes:', e)
    themes.value = themeStore.themes || []
  }
}

async function uploadAsset(key) {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*'
  input.onchange = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    const targetName = `${key}.png`
    const renamedFile = new File([file], targetName, { type: file.type })
    const formData = new FormData()
    formData.append('file', renamedFile)
    try {
      const resp = await fetch(`/api/themes/${selectedTheme.value}/upload`, { method: 'POST', body: formData })
      if (resp.ok) uploadedAssets[key] = true
    } catch (e) {
      console.error('Upload failed:', e)
    }
  }
  input.click()
}

function finish() {
  themeStore.applyTheme(selectedTheme.value)
  personaStore.switchPersona(selectedPersona.value)
  visible.value = false
  emit('complete', { personaId: selectedPersona.value, themeId: selectedTheme.value })
}

defineExpose({ show })
</script>

<style scoped>
.wizard-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(4px);
}

.wizard-modal {
  background: var(--bg-secondary, #1e1e2e);
  border: 1px solid var(--border, #333);
  border-radius: 16px;
  width: 560px;
  max-width: 92vw;
  max-height: 88vh;
  overflow-y: auto;
  padding: 28px 32px 20px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

/* 步骤指示器 */
.step-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  margin-bottom: 8px;
}

.step-item {
  display: flex;
  align-items: center;
}

.step-circle {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  border: 2px solid var(--border, #444);
  color: var(--text-secondary, #888);
  background: var(--bg-primary, #16161e);
  transition: all 0.25s;
}

.step-circle.active {
  border-color: var(--primary, #7c5cfc);
  color: white;
  background: var(--primary, #7c5cfc);
  box-shadow: 0 0 12px rgba(124, 92, 252, 0.4);
}

.step-circle.done {
  border-color: #4ade80;
  color: white;
  background: #4ade80;
}

.step-line {
  width: 60px;
  height: 2px;
  background: var(--border, #444);
  margin: 0 6px;
  transition: background 0.25s;
}

.step-line.filled {
  background: #4ade80;
}

.step-labels {
  display: flex;
  justify-content: center;
  gap: 32px;
  margin-bottom: 24px;
}

.step-label {
  font-size: 11px;
  color: var(--text-secondary, #888);
  width: 70px;
  text-align: center;
  transition: color 0.2s;
}

.step-label.active {
  color: var(--primary, #7c5cfc);
  font-weight: 600;
}

/* 向导主体 */
.wizard-body {
  min-height: 280px;
}

.wizard-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary, #fff);
  margin: 0 0 4px;
  text-align: center;
}

.wizard-desc {
  font-size: 13px;
  color: var(--text-secondary, #888);
  margin: 0 0 20px;
  text-align: center;
}

/* 卡片网格 */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
  max-height: 320px;
  overflow-y: auto;
  padding: 2px;
}

.wizard-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid var(--border, #333);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--bg-primary, #16161e);
}

.wizard-card:hover {
  border-color: var(--primary, #7c5cfc);
  background: rgba(124, 92, 252, 0.05);
}

.wizard-card.selected {
  border-color: var(--primary, #7c5cfc);
  background: rgba(124, 92, 252, 0.15);
  box-shadow: 0 0 12px rgba(124, 92, 252, 0.2);
}

.card-avatar {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: var(--primary, #7c5cfc);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
  flex-shrink: 0;
}

.card-info {
  min-width: 0;
}

.card-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #fff);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-desc {
  font-size: 11px;
  color: var(--text-secondary, #888);
  margin-top: 2px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 主题卡片 */
.theme-card {
  padding: 10px 14px;
}

.theme-preview {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  flex-shrink: 0;
}

/* 素材步骤 */
.asset-diagram {
  margin-bottom: 16px;
  display: flex;
  justify-content: center;
}

.diagram-wrapper {
  width: 360px;
  max-width: 100%;
  background: var(--bg-primary, #16161e);
  border: 1px solid var(--border, #333);
  border-radius: 10px;
  padding: 8px;
}

.diagram-svg {
  width: 100%;
  height: auto;
}

.diagram-label {
  font-size: 9px;
  font-family: sans-serif;
}

.diagram-icon {
  font-size: 14px;
}

.asset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 8px;
}

.asset-slot {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px 8px;
  border: 1px dashed var(--border, #444);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--bg-primary, #16161e);
}

.asset-slot:hover {
  border-color: var(--primary, #7c5cfc);
  background: rgba(124, 92, 252, 0.05);
}

.asset-slot.uploaded {
  border-color: #4ade80;
  border-style: solid;
  background: rgba(74, 222, 128, 0.05);
}

.asset-num {
  font-size: 18px;
  line-height: 1;
}

.asset-label {
  font-size: 12px;
  color: var(--text-primary, #fff);
  font-weight: 500;
}

.asset-status {
  font-size: 10px;
}

.status-ok {
  color: #4ade80;
}

.status-empty {
  color: var(--text-secondary, #888);
}

/* 完成步骤 */
.finish-step {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.summary-card {
  width: 100%;
  max-width: 360px;
  background: var(--bg-primary, #16161e);
  border: 1px solid var(--border, #333);
  border-radius: 12px;
  padding: 20px;
  margin-top: 8px;
}

.summary-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
}

.summary-row + .summary-row {
  border-top: 1px solid var(--border, #333);
}

.summary-label {
  font-size: 13px;
  color: var(--text-secondary, #888);
}

.summary-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #fff);
}

/* 底部按钮 */
.wizard-footer {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--border, #333);
}

.footer-spacer {
  flex: 1;
}

.btn-prev,
.btn-skip {
  padding: 8px 20px;
  background: transparent;
  border: 1px solid var(--border, #444);
  border-radius: 8px;
  color: var(--text-secondary, #888);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.15s;
}

.btn-prev:hover,
.btn-skip:hover {
  border-color: var(--primary, #7c5cfc);
  color: var(--text-primary, #fff);
}

.btn-next,
.btn-finish {
  padding: 8px 24px;
  background: var(--primary, #7c5cfc);
  border: none;
  border-radius: 8px;
  color: white;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  transition: all 0.15s;
}

.btn-next:hover,
.btn-finish:hover {
  opacity: 0.9;
  box-shadow: 0 4px 16px rgba(124, 92, 252, 0.3);
}

.btn-next:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-finish {
  background: #4ade80;
  color: #111;
}

.btn-finish:hover {
  box-shadow: 0 4px 16px rgba(74, 222, 128, 0.3);
}

/* 响应式 */
@media (max-width: 600px) {
  .wizard-modal {
    padding: 20px 16px 16px;
    border-radius: 12px;
  }
  .card-grid {
    grid-template-columns: 1fr;
  }
  .asset-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .step-line {
    width: 30px;
  }
  .step-labels {
    gap: 12px;
  }
}
</style>
