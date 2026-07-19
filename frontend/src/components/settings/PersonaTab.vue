<template>
  <div class="tab-content">
    <h2>次元设置</h2>
    <button class="btn-new" @click="createNewPack">+ 新建主题包</button>

    <div class="pack-grid">
      <div
        v-for="pack in themePacks"
        :key="pack.id"
        class="pack-card"
        :class="{ selected: editingPackId === pack.id }"
        @click="openEditor(pack.id)"
      >
        <div class="pack-preview">
          <img v-if="packIconUrl(pack.id)" :src="packIconUrl(pack.id)" class="pack-icon" />
          <div v-else class="pack-icon-fallback" :style="{ background: pack.theme?.colors?.primary || '#7c5cfc' }"></div>
        </div>
        <div class="pack-info">
          <div class="pack-name">{{ pack.name || pack.id }}</div>
          <div class="pack-meta">
            <span v-if="pack.character?.name">🎭 {{ pack.character.name }}</span>
            <span v-if="pack.theme?.name">🎨 {{ pack.theme.name }}</span>
          </div>
        </div>
      </div>
      <div v-if="themePacks.length === 0" class="empty-hint">暂无主题包，点击上方按钮创建</div>
    </div>

    <!-- Inline Editor -->
    <div v-if="editingPackId && editingPack" class="pack-editor">
      <h3>编辑主题包：{{ editingPack.name || editingPackId }}</h3>

      <div class="editor-tabs">
        <button
          v-for="tab in editorTabs"
          :key="tab.id"
          class="tab-btn"
          :class="{ active: editorTab === tab.id }"
          @click="editorTab = tab.id"
        >{{ tab.icon }} {{ tab.label }}</button>
      </div>

      <!-- 角色标签 -->
      <div v-if="editorTab === 'character'" class="tab-panel">
        <div class="form-group">
          <label>角色名称</label>
          <input v-model="editingPack.character.name" placeholder="角色显示名" />
        </div>
        <div class="form-group">
          <label>描述</label>
          <input v-model="editingPack.character.description" placeholder="一句话简介" />
        </div>
        <div class="form-group">
          <label>人设 Prompt</label>
          <textarea v-model="editingPack.character.prompt" rows="5" placeholder="角色的系统提示词……"></textarea>
        </div>
        <fieldset class="form-group">
          <legend>情感权重</legend>
          <div v-for="key in emotionKeys" :key="key" class="slider-row">
            <span class="slider-label">{{ emotionLabels[key] }}</span>
            <input type="range" min="0" max="1" step="0.1" v-model.number="editingPack.character.emotion_weights[key]" />
            <span class="slider-val">{{ (editingPack.character.emotion_weights[key] ?? 0).toFixed(1) }}</span>
          </div>
          <div class="slider-row" style="margin-top: 8px;">
            <span class="slider-label">🌡️温度</span>
            <input type="range" min="0" max="2" step="0.1" v-model.number="editingPack.character.temperature" />
            <span class="slider-val">{{ (editingPack.character.temperature ?? 0.8).toFixed(1) }}</span>
            <span class="slider-hint">越低越确定，越高越随机</span>
          </div>
          <div class="slider-row">
            <span class="slider-label">🎯Top-p</span>
            <input type="range" min="0.1" max="1" step="0.05" v-model.number="editingPack.character.top_p" />
            <span class="slider-val">{{ (editingPack.character.top_p ?? 0.9).toFixed(2) }}</span>
            <span class="slider-hint">核采样阈值，控制候选范围</span>
          </div>
        </fieldset>
        <fieldset class="form-group">
          <legend>说话风格</legend>
          <div class="form-group">
            <label>语气</label>
            <input v-model="editingPack.character.speech_style.tone" placeholder="如：活泼、温柔、冷酷" />
          </div>
          <div class="form-group">
            <label>口头禅</label>
            <input v-model="editingPack.character.speech_style.catchphrase" placeholder="如：だよね～" />
          </div>
          <div class="form-group">
            <label>表情频率</label>
            <select v-model="editingPack.character.speech_style.emoji_frequency">
              <option value="low">低</option>
              <option value="medium">中</option>
              <option value="high">高</option>
            </select>
          </div>
          <div class="form-group">
            <label>正式度</label>
            <select v-model="editingPack.character.speech_style.formality">
              <option value="casual">随意</option>
              <option value="polite">礼貌</option>
              <option value="formal">正式</option>
            </select>
          </div>
        </fieldset>
      </div>

      <!-- 主题标签 -->
      <div v-if="editorTab === 'theme'" class="tab-panel">
        <div class="sub-tab-bar">
          <button
            v-for="st in themeSubTabs"
            :key="st.id"
            class="sub-tab-btn"
            :class="{ active: themeSubTab === st.id }"
            @click="themeSubTab = st.id"
          >{{ st.icon }} {{ st.label }}</button>
        </div>

        <!-- 颜色子标签 -->
        <div v-if="themeSubTab === 'colors'" class="sub-panel">
          <div class="color-grid">
            <div class="color-item" v-for="c in colorDefs" :key="c.var">
              <label>{{ c.label }}</label>
              <div class="color-input">
                <input type="color" :value="toHex(editingPack.theme.colors[c.var])" @input="onColorChange(c.var, $event.target.value)" />
                <span class="color-val">{{ editingPack.theme.colors[c.var] }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 字体子标签 -->
        <div v-if="themeSubTab === 'fonts'" class="sub-panel">
          <div class="param-row">
            <label>字体族</label>
            <select v-model="editingPack.theme.fonts.family">
              <option v-for="f in fontFamilies" :key="f.value" :value="f.value">{{ f.label }}</option>
            </select>
          </div>
          <div class="param-row"><label>正文字号 <span class="val-badge">{{ editingPack.theme.fonts.sizeBase }}px</span></label><input type="range" min="12" max="20" step="1" v-model.number="editingPack.theme.fonts.sizeBase" /></div>
          <div class="param-row"><label>小字字号 <span class="val-badge">{{ editingPack.theme.fonts.sizeSmall }}px</span></label><input type="range" min="10" max="16" step="1" v-model.number="editingPack.theme.fonts.sizeSmall" /></div>
          <div class="param-row"><label>行高 <span class="val-badge">{{ editingPack.theme.fonts.lineHeight.toFixed(1) }}</span></label><input type="range" min="1.2" max="2.0" step="0.1" v-model.number="editingPack.theme.fonts.lineHeight" /></div>
        </div>
      </div>

      <!-- 素材标签 -->
      <div v-if="editorTab === 'assets'" class="tab-panel">
        <AssetUploader :pack-id="editingPackId" @icon-uploaded="$emit('pack-changed')" />
      </div>

      <div class="actions">
        <button class="btn-save" @click="savePack">保存</button>
        <button class="btn-cancel" @click="cancelEdit">取消</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useThemeStore } from '../../stores/theme'
import { useToast } from '../../composables/useToast'
import AssetUploader from '../AssetUploader.vue'

const props = defineProps({
  themePacks: { type: Array, default: () => [] },
  packIcons: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['pack-changed'])

const themeStore = useThemeStore()
const toast = useToast()

function packIconUrl(packId) {
  return props.packIcons[packId] || null
}

// --- Editor state ---
const editingPackId = ref(null)
const editingPack = ref(null)
const editorTab = ref('character')
const themeSubTab = ref('colors')

const editorTabs = [
  { id: 'character', icon: '🎭', label: '角色' },
  { id: 'theme', icon: '🎨', label: '主题' },
  { id: 'assets', icon: '🖼', label: '素材' },
]

const themeSubTabs = [
  { id: 'colors', icon: '🎨', label: '颜色' },
  { id: 'fonts', icon: '🔤', label: '字体' },
]

const emotionKeys = ['cheerful', 'shy', 'curious', 'angry', 'sad']
const emotionLabels = {
  cheerful: '开朗',
  shy: '害羞',
  curious: '好奇',
  angry: '愤怒',
  sad: '悲伤',
}

const colorDefs = [
  { var: 'primary', label: '主色调', cssVar: '--primary' },
  { var: 'highlight', label: '高亮色', cssVar: '--highlight' },
  { var: 'textPrimary', label: '主文字', cssVar: '--text-primary' },
  { var: 'textSecondary', label: '次文字', cssVar: '--text-secondary' },
]

const fontFamilies = [
  { value: "'Noto Sans SC', sans-serif", label: 'Noto Sans SC' },
  { value: "'Noto Sans JP', sans-serif", label: 'Noto Sans JP' },
  { value: "system-ui, -apple-system, sans-serif", label: '系统默认' },
]

function toHex(val) {
  if (!val) return '#000000'
  if (val.startsWith('#') && val.length === 7) return val
  const m = val.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
  if (m) {
    const r = parseInt(m[1]).toString(16).padStart(2, '0')
    const g = parseInt(m[2]).toString(16).padStart(2, '0')
    const b = parseInt(m[3]).toString(16).padStart(2, '0')
    return '#' + r + g + b
  }
  return '#000000'
}

function onColorChange(varName, hexVal) {
  editingPack.value.theme.colors[varName] = hexVal
}

function makeEmptyPack() {
  return {
    id: '',
    name: '',
    character: {
      name: '',
      description: '',
      prompt: '',
      emotion_weights: { cheerful: 0.5, shy: 0.2, curious: 0.5, angry: 0.1, sad: 0.1 },
      speech_style: { tone: '友好', catchphrase: '', emoji_frequency: 'medium', formality: 'casual' },
      temperature: 0.8,
      top_p: 0.9,
    },
    theme: {
      name: '',
      colors: {
        'primary': '#7c5cfc',
        'highlight': '#7c5cfc',
        'bgPrimary': '#0f0f1a',
        'bgSecondary': '#1a1a2e',
        'textPrimary': '#e8e8f0',
        'textSecondary': '#8888aa',
        'border': '#2a2a40',
        'bubbleUser': 'rgba(124,92,252,0.15)',
        'bubbleAgent': 'rgba(30,30,50,0.9)',
      },
      fonts: { family: "'Noto Sans SC', sans-serif", sizeBase: 14, sizeSmall: 12, lineHeight: 1.6 },
      spacing: { bubbleRadius: 12, bubblePadding: '10px 14px', sidebarWidth: 220, inputRadius: 8 },
    },
  }
}

function normalizeColorKey(key) {
  let k = key.startsWith('--') ? key.slice(2) : key
  k = k.replace(/-([a-z])/g, (_, c) => c.toUpperCase())
  return k
}

function normalizeColors(raw) {
  if (!raw) return {}
  const out = {}
  for (const [k, v] of Object.entries(raw)) {
    if (!k.startsWith('--')) {
      out[normalizeColorKey(k)] = v
    }
  }
  for (const [k, v] of Object.entries(raw)) {
    if (k.startsWith('--')) {
      const nk = normalizeColorKey(k)
      if (!(nk in out)) out[nk] = v
    }
  }
  return out
}

function normalizePack(data) {
  const empty = makeEmptyPack()
  return {
    id: data.id || '',
    name: data.name || data.id || '',
    character: {
      name: data.character?.name || '',
      description: data.character?.description || '',
      prompt: data.character?.prompt || '',
      emotion_weights: { ...empty.character.emotion_weights, ...(data.character?.emotion_weights || {}) },
      speech_style: { ...empty.character.speech_style, ...(data.character?.speech_style || {}) },
      temperature: data.character?.temperature ?? 0.8,
      top_p: data.character?.top_p ?? 0.9,
    },
    theme: {
      name: data.theme?.name || '',
      colors: { ...empty.theme.colors, ...normalizeColors(data.theme?.colors) },
      fonts: { ...empty.theme.fonts, ...(data.theme?.fonts || {}) },
      spacing: { ...empty.theme.spacing, ...(data.theme?.spacing || {}) },
    },
  }
}

async function openEditor(packId) {
  editingPackId.value = packId
  editorTab.value = 'character'
  themeSubTab.value = 'colors'
  try {
    const resp = await fetch(`/api/themepacks/${packId}`)
    const data = await resp.json()
    editingPack.value = normalizePack(data)
  } catch {
    const pack = props.themePacks.find(p => p.id === packId)
    editingPack.value = normalizePack(pack || { id: packId })
  }
}

async function createNewPack() {
  const name = window.prompt('请输入主题包名称')
  if (!name) return
  const id = name.toLowerCase().replace(/[^a-z0-9一-鿿]/g, '_').replace(/_+/g, '_').slice(0, 32) || 'pack_' + Date.now()
  try {
    const resp = await fetch('/api/themepacks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, name, persona_ref: id, theme_ref: id })
    })
    if (resp.ok) {
      const data = await resp.json()
      emit('pack-changed')
      if (data.id) openEditor(data.id)
      toast.success('主题包创建成功')
    } else {
      const err = await resp.json()
      toast.error(err.detail || '创建失败')
    }
  } catch (e) {
    toast.error('创建失败: ' + e.message)
  }
}

async function savePack() {
  if (!editingPackId.value || !editingPack.value) return
  const packData = JSON.parse(JSON.stringify(editingPack.value))
  if (packData.theme?.colors) {
    for (const key of Object.keys(packData.theme.colors)) {
      if (key.startsWith('--')) delete packData.theme.colors[key]
    }
  }
  try {
    const resp = await fetch(`/api/themepacks/${editingPackId.value}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(packData)
    })
    if (resp.ok) {
      await themeStore.applyTheme(editingPackId.value)
      const c = editingPack.value.theme.colors
      const cssVarMap = { primary: '--primary', highlight: '--highlight', textPrimary: '--text-primary', textSecondary: '--text-secondary' }
      const overrides = {}
      for (const [key, cssVar] of Object.entries(cssVarMap)) {
        if (c[key]) {
          document.documentElement.style.setProperty(cssVar, c[key])
          overrides[cssVar] = c[key]
        }
      }
      localStorage.setItem('theme-color-overrides', JSON.stringify(overrides))
      toast.success('保存成功')
      emit('pack-changed')
    } else {
      const err = await resp.json()
      toast.error(err.detail || '保存失败')
    }
  } catch (e) {
    toast.error('保存失败: ' + e.message)
  }
}

function cancelEdit() {
  editingPackId.value = null
  editingPack.value = null
}

defineExpose({ openEditor })
</script>

<style scoped>
.pack-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
  margin: 16px 0;
}

.pack-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: rgba(20, 20, 40, 0.60);
  box-shadow: var(--ui-border);
  border-radius: var(--radius);
  cursor: pointer;
  transition: filter 0.2s, transform 0.2s, box-shadow 0.2s;
}
.pack-card:hover {
  box-shadow: 0 0 0 1px var(--primary), var(--glow-inner);
  filter: brightness(1.05);
  transform: translateY(-1px);
}
.pack-card.selected {
  box-shadow: 0 0 0 2px var(--primary), var(--glow-inner);
}

.pack-preview {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  flex-shrink: 0;
  overflow: hidden;
}
.pack-icon {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.pack-icon-fallback {
  width: 100%;
  height: 100%;
}

.pack-info { flex: 1; min-width: 0; }
.pack-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pack-meta {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* Inline pack editor */
.pack-editor {
  background: rgba(20, 20, 40, 0.60);
  box-shadow: var(--ui-border);
  border-radius: var(--radius);
  padding: 24px;
  margin: 20px 0;
}
.pack-editor h3 {
  font-size: 16px;
  margin-bottom: 16px;
}

/* Editor tabs */
.editor-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 16px;
  padding-bottom: 10px;
}

.tab-btn {
  padding: 6px 18px;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
  border-radius: var(--radius-sm);
  background: rgba(20, 20, 40, 0.60);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 13px;
  border: none;
  transition: filter 0.2s, transform 0.2s, box-shadow 0.2s;
}
.tab-btn.active {
  background: var(--primary);
  color: #fff;
  box-shadow: none;
}
.tab-btn:hover:not(.active) {
  box-shadow: 0 0 0 1px var(--primary);
  filter: brightness(1.05);
  transform: translateY(-1px);
}

.tab-panel {
  margin-bottom: 14px;
}

/* Sub tabs for theme */
.sub-tab-bar {
  display: flex;
  gap: 4px;
  margin-bottom: 14px;
}
.sub-tab-btn {
  padding: 5px 14px;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
  border-radius: var(--radius-sm);
  background: rgba(20, 20, 40, 0.60);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 12px;
  border: none;
  transition: filter 0.2s, transform 0.2s, box-shadow 0.2s;
}
.sub-tab-btn.active {
  background: var(--primary);
  color: #fff;
  box-shadow: none;
}
.sub-tab-btn:hover:not(.active) {
  box-shadow: 0 0 0 1px var(--primary);
  filter: brightness(1.05);
  transform: translateY(-1px);
}

.sub-panel {
  margin-bottom: 10px;
}

/* Color grid */
.color-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.color-item label {
  font-size: 13px;
  color: var(--text-secondary);
  display: block;
  margin-bottom: 6px;
}
.color-input {
  display: flex;
  align-items: center;
  gap: 10px;
}
.color-input input[type="color"] {
  width: 48px;
  height: 48px;
  border: none;
  cursor: pointer;
  background: none;
  border-radius: 8px;
}
.color-val {
  font-size: 12px;
  color: var(--text-secondary);
  font-family: monospace;
}

/* Param rows */
.param-row {
  margin-bottom: 12px;
}
.param-row label {
  display: block;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}
.param-row .val-badge {
  color: var(--primary);
  font-weight: 600;
}
.param-row input[type="range"] {
  width: 100%;
  accent-color: var(--primary);
}
.param-row select,
.param-row input[type="text"] {
  width: 100%;
  padding: 6px 8px;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
  border-radius: 6px;
  background: rgba(20, 20, 40, 0.60);
  color: var(--text-primary);
  font-size: 13px;
  border: none;
}

/* Form */
.form-group {
  margin-bottom: 16px;
}
label {
  display: block;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}
input, textarea, select {
  width: 100%;
  padding: 8px 12px;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
  border-radius: var(--radius-sm);
  background: rgba(20, 20, 40, 0.60);
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
  border: none;
  transition: box-shadow 0.2s;
}
input:focus, textarea:focus, select:focus {
  box-shadow: 0 0 0 1px var(--primary);
}
textarea {
  resize: vertical;
  font-family: inherit;
}
select {
  max-width: 300px;
}
fieldset {
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
  border: none;
  border-radius: var(--radius);
  padding: 12px 16px;
}
legend {
  font-size: 13px;
  color: var(--text-secondary);
  padding: 0 6px;
}

/* Sliders */
.slider-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.slider-label {
  width: 56px;
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
  flex-shrink: 0;
}
.slider-row input[type="range"] {
  flex: 1;
  max-width: 300px;
  accent-color: var(--primary);
}
.slider-val {
  width: 28px;
  font-size: 13px;
  text-align: right;
}
.slider-hint {
  font-size: 11px;
  color: var(--text-secondary);
  opacity: 0.7;
  white-space: nowrap;
  min-width: 0;
}

/* Buttons */
.btn-new {
  padding: 8px 20px;
  font-size: 13px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: filter 0.2s, transform 0.2s;
}
.btn-new:hover {
  filter: brightness(1.08);
  transform: translateY(-1px);
}

.btn-save {
  padding: 10px 28px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 14px;
  transition: filter 0.2s, transform 0.2s;
}
.btn-save:hover {
  filter: brightness(1.08);
  transform: translateY(-1px);
}
.btn-cancel {
  padding: 10px 28px;
  background: rgba(20, 20, 40, 0.60);
  color: var(--text-secondary);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 14px;
  transition: filter 0.2s, transform 0.2s, box-shadow 0.2s;
}
.btn-cancel:hover {
  box-shadow: 0 0 0 1px var(--primary);
  filter: brightness(1.08);
  transform: translateY(-1px);
}
.actions {
  margin-top: 20px;
  display: flex;
  gap: 12px;
}

.empty-hint {
  text-align: center;
  padding: 24px;
  color: var(--text-secondary);
  font-size: 14px;
}
</style>
