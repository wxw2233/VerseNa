<template>
  <div class="theme-editor">
    <h3>主题编辑器</h3>
    <div class="tab-bar">
      <button v-for="tab in tabs" :key="tab.id" class="tab-btn" :class="{ active: activeTab === tab.id }" @click="activeTab = tab.id">{{ tab.icon }} {{ tab.label }}</button>
    </div>
    <div v-if="activeTab === 'colors'" class="tab-panel">
      <div class="color-grid">
        <div class="color-item" v-for="c in colorDefs" :key="c.var">
          <label>{{ c.label }}</label>
          <div class="color-input">
            <input type="color" :value="toHex(colors[c.var])" @input="onColorChange(c.var, $event.target.value)" />
            <span class="color-val">{{ colors[c.var] }}</span>
          </div>
        </div>
      </div>
    </div>
    <div v-if="activeTab === 'fonts'" class="tab-panel">
      <div class="param-row">
        <label>字体族</label>
        <select v-model="fonts.family" @change="applyVar('--font-family', fonts.family)">
          <option v-for="f in fontFamilies" :key="f.value" :value="f.value">{{ f.label }}</option>
        </select>
      </div>
      <div class="param-row"><label>正文字号 <span class="val-badge">{{ fonts.sizeBase }}px</span></label><input type="range" min="12" max="20" step="1" v-model.number="fonts.sizeBase" @input="applyVar('--font-size-base', fonts.sizeBase + 'px')" /></div>
      <div class="param-row"><label>小字字号 <span class="val-badge">{{ fonts.sizeSmall }}px</span></label><input type="range" min="10" max="16" step="1" v-model.number="fonts.sizeSmall" @input="applyVar('--font-size-small', fonts.sizeSmall + 'px')" /></div>
      <div class="param-row"><label>行高 <span class="val-badge">{{ fonts.lineHeight.toFixed(1) }}</span></label><input type="range" min="1.2" max="2.0" step="0.1" v-model.number="fonts.lineHeight" @input="applyVar('--line-height', fonts.lineHeight.toFixed(1))" /></div>
    </div>
    <div v-if="activeTab === 'spacing'" class="tab-panel">
      <div class="param-row"><label>气泡圆角 <span class="val-badge">{{ spacing.bubbleRadius }}px</span></label><input type="range" min="0" max="24" step="1" v-model.number="spacing.bubbleRadius" @input="applyVar('--bubble-radius', spacing.bubbleRadius + 'px')" /></div>
      <div class="param-row"><label>气泡内距</label><input type="text" v-model="spacing.bubblePadding" @input="applyVar('--bubble-padding', spacing.bubblePadding)" placeholder="10px 14px" /></div>
      <div class="param-row"><label>侧栏宽度 <span class="val-badge">{{ spacing.sidebarWidth }}px</span></label><input type="range" min="160" max="320" step="10" v-model.number="spacing.sidebarWidth" @input="applyVar('--sidebar-width', spacing.sidebarWidth + 'px')" /></div>
      <div class="param-row"><label>输入框圆角 <span class="val-badge">{{ spacing.inputRadius }}px</span></label><input type="range" min="0" max="16" step="1" v-model.number="spacing.inputRadius" @input="applyVar('--input-radius', spacing.inputRadius + 'px')" /></div>
    </div>
    <div class="btn-row">
      <button class="btn-apply" @click="apply">应用</button>
      <button class="btn-reset" @click="resetDefaults">重置为默认</button>
    </div>
    <div v-if="msg" class="msg">{{ msg }}</div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useThemeStore } from '../stores/theme'

const themeStore = useThemeStore()
const msg = ref('')
const activeTab = ref('colors')

const tabs = [
  { id: 'colors', icon: '🎨', label: '颜色' },
  { id: 'fonts', icon: '🔤', label: '字体' },
  { id: 'spacing', icon: '📐', label: '间距' },
]

const defaultColors = {
  '--primary': '#7c5cfc',
  '--bg-primary': '#0f0f1a',
  '--bg-secondary': '#1a1a2e',
  '--text-primary': '#e8e8f0',
  '--text-secondary': '#8888aa',
  '--border': '#2a2a40',
  '--bubble-user': 'rgba(124,92,252,0.15)',
  '--bubble-agent': 'rgba(30,30,50,0.9)',
}

const colorDefs = [
  { var: '--primary', label: '主色调' },
  { var: '--bg-primary', label: '主背景' },
  { var: '--bg-secondary', label: '次背景' },
  { var: '--text-primary', label: '主文字' },
  { var: '--text-secondary', label: '次文字' },
  { var: '--border', label: '边框色' },
  { var: '--bubble-user', label: '用户气泡' },
  { var: '--bubble-agent', label: 'Agent气泡' },
]

const colors = reactive({ ...defaultColors })

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
  if (varName === '--bubble-user') {
    const r = parseInt(hexVal.slice(1, 3), 16)
    const g = parseInt(hexVal.slice(3, 5), 16)
    const b = parseInt(hexVal.slice(5, 7), 16)
    colors[varName] = 'rgba(' + r + ',' + g + ',' + b + ',0.15)'
  } else if (varName === '--bubble-agent') {
    const r = parseInt(hexVal.slice(1, 3), 16)
    const g = parseInt(hexVal.slice(3, 5), 16)
    const b = parseInt(hexVal.slice(5, 7), 16)
    colors[varName] = 'rgba(' + r + ',' + g + ',' + b + ',0.9)'
  } else {
    colors[varName] = hexVal
  }
  document.documentElement.style.setProperty(varName, colors[varName])
}

const defaultFonts = { family: "'Noto Sans SC', sans-serif", sizeBase: 14, sizeSmall: 12, lineHeight: 1.6 }
const fonts = reactive({ ...defaultFonts })

const fontFamilies = [
  { value: "'Noto Sans SC', sans-serif", label: 'Noto Sans SC' },
  { value: "'Noto Sans JP', sans-serif", label: 'Noto Sans JP' },
  { value: "system-ui, -apple-system, sans-serif", label: '系统默认' },
]

const defaultSpacing = { bubbleRadius: 12, bubblePadding: '10px 14px', sidebarWidth: 220, inputRadius: 8 }
const spacing = reactive({ ...defaultSpacing })

function applyVar(name, value) {
  document.documentElement.style.setProperty(name, value)
}

function apply() {
  const config = {
    ...colors,
    '--font-family': fonts.family,
    '--font-size-base': fonts.sizeBase + 'px',
    '--font-size-small': fonts.sizeSmall + 'px',
    '--line-height': fonts.lineHeight.toFixed(1),
    '--bubble-radius': spacing.bubbleRadius + 'px',
    '--bubble-padding': spacing.bubblePadding,
    '--sidebar-width': spacing.sidebarWidth + 'px',
    '--input-radius': spacing.inputRadius + 'px',
  }
  fetch('/api/themes/update', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: themeStore.current || 'default', config }),
  }).then(function(r) { msg.value = r.ok ? '已保存！' : '保存失败'; setTimeout(function() { msg.value = '' }, 2000) })
}

function resetDefaults() {
  Object.assign(colors, defaultColors)
  Object.assign(fonts, defaultFonts)
  Object.assign(spacing, defaultSpacing)
  for (const [k, v] of Object.entries(defaultColors)) document.documentElement.style.setProperty(k, v)
  applyVar('--font-family', defaultFonts.family)
  applyVar('--font-size-base', defaultFonts.sizeBase + 'px')
  applyVar('--font-size-small', defaultFonts.sizeSmall + 'px')
  applyVar('--line-height', defaultFonts.lineHeight.toFixed(1))
  applyVar('--bubble-radius', defaultSpacing.bubbleRadius + 'px')
  applyVar('--bubble-padding', defaultSpacing.bubblePadding)
  applyVar('--sidebar-width', defaultSpacing.sidebarWidth + 'px')
  applyVar('--input-radius', defaultSpacing.inputRadius + 'px')
  msg.value = '已重置'
  setTimeout(function() { msg.value = '' }, 2000)
}
</script>

<style scoped>
.theme-editor { margin-bottom: 24px; }
.theme-editor h3 { font-size: 16px; margin-bottom: 12px; color: var(--text-primary); }
.tab-bar { display: flex; gap: 4px; margin-bottom: 14px; }
.tab-btn { padding: 6px 16px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg-primary); color: var(--text-secondary); cursor: pointer; font-size: 13px; }
.tab-btn.active { background: var(--primary); color: #fff; border-color: var(--primary); }
.tab-btn:hover:not(.active) { border-color: var(--primary); }
.tab-panel { margin-bottom: 14px; }
.color-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.color-item label { font-size: 12px; color: var(--text-secondary); display: block; margin-bottom: 2px; }
.color-input { display: flex; align-items: center; gap: 6px; }
.color-input input[type="color"] { width: 32px; height: 32px; border: none; cursor: pointer; background: none; }
.color-val { font-size: 11px; color: var(--text-secondary); font-family: monospace; }
.param-row { margin-bottom: 12px; }
.param-row label { display: block; font-size: 13px; color: var(--text-secondary); margin-bottom: 4px; }
.param-row .val-badge { color: var(--primary); font-weight: 600; }
.param-row input[type="range"] { width: 100%; accent-color: var(--primary); }
.param-row select, .param-row input[type="text"] { width: 100%; padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg-primary); color: var(--text-primary); font-size: 13px; }
.btn-row { display: flex; gap: 10px; margin-top: 8px; }
.btn-apply { padding: 8px 20px; background: var(--primary); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; }
.btn-reset { padding: 8px 20px; background: var(--bg-secondary); color: var(--text-secondary); border: 1px solid var(--border); border-radius: 6px; cursor: pointer; font-size: 13px; }
.btn-reset:hover { border-color: var(--primary); }
.msg { margin-top: 8px; font-size: 13px; color: var(--primary); }
</style>
