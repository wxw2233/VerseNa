<template>
  <div class="settings-layout">
    <!-- Sidebar Menu -->
    <aside class="sidebar">
      <div
        v-for="item in menuItems"
        :key="item.id"
        class="menu-item"
        :class="{ active: activeTab === item.id }"
        @click="activeTab = item.id"
      >
        <span class="menu-icon">{{ item.icon }}</span>
        <span class="menu-label">{{ item.label }}</span>
      </div>
    </aside>

    <!-- Content Area -->
    <section class="content">
      <!-- 次元设置 (Persona) — 以主题包为核心 -->
      <div v-if="activeTab === 'persona'" class="tab-content">
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
            <div class="pack-preview" :style="{ background: pack.theme?.colors?.primary || '#7c5cfc' }"></div>
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
            <AssetUploader />
          </div>

          <div class="actions">
            <button class="btn-save" @click="savePack">保存</button>
            <button class="btn-cancel" @click="cancelEdit">取消</button>
          </div>
        </div>
      </div>

      <!-- 主题包管理 (Theme Pack) — 列表+操作 -->
      <div v-if="activeTab === 'themepack'" class="tab-content">
        <h2>主题包管理</h2>
        <p class="hint">导出/导入/管理完整主题包（包含颜色、素材、角色配置）</p>

        <div class="tp-grid">
          <div v-for="pack in themePacks" :key="pack.id" class="tp-card">
            <div class="tp-preview" :style="{ background: pack.theme?.colors?.primary || '#7c5cfc' }"></div>
            <div class="tp-info">
              <div class="tp-name">{{ pack.name || pack.id }}</div>
              <div class="tp-meta">
                <span v-if="pack.character?.name">🎭 {{ pack.character.name }}</span>
                <span v-if="pack.theme?.name">🎨 {{ pack.theme.name }}</span>
              </div>
            </div>
            <div class="tp-actions">
              <button class="btn-sm" @click="exportPack(pack.id)" title="导出">📦</button>
              <button class="btn-sm" @click="applyPack(pack.id)" title="一键更新关联会话">⚡</button>
              <button class="btn-sm btn-sm-danger" @click="deletePack(pack.id)" title="删除">🗑</button>
            </div>
          </div>
          <div v-if="themePacks.length === 0" class="empty-hint">暂无主题包</div>
        </div>

        <div class="package-actions">
          <label class="btn-action">
            导入主题包（zip）
            <input type="file" accept=".zip" @change="importPack" style="display:none" />
          </label>
        </div>
      </div>

      <!-- 模型配置 (Model) -->
      <div v-if="activeTab === 'model'" class="tab-content">
        <h2>模型配置</h2>
        <div class="form-group">
          <label>API Base URL</label>
          <input v-model="form_model.base_url" placeholder="https://api.deepseek.com/v1" />
        </div>
        <div class="form-group">
          <label>API Key</label>
          <input v-model="form_model.api_key" type="password" placeholder="sk-..." />
        </div>
        <div class="form-group">
          <label>模型名称</label>
          <input v-model="form_model.model_name" placeholder="deepseek-chat" />
        </div>
        <button class="btn-save" @click="saveModel">保存</button>
      </div>

      <!-- 通道管理 (Channel) -->
      <div v-if="activeTab === 'channel'" class="tab-content">
        <h2>通道管理</h2>
        <QQBotConfig />
      </div>

      <!-- 插件管理 (Plugin) -->
      <div v-if="activeTab === 'plugin'" class="tab-content">
        <h2>插件管理</h2>
        <div class="empty-state">
          <div class="empty-icon">🔌</div>
          <div class="empty-title">暂无插件</div>
          <div class="empty-desc">将插件文件夹放入 <code>plugins/</code> 目录即可自动加载</div>
        </div>
      </div>

      <!-- 技能 (Skill) -->
      <div v-if="activeTab === 'skill'" class="tab-content">
        <h2>技能</h2>
        <div class="empty-state">
          <div class="empty-icon">⚡</div>
          <div class="empty-title">技能管理</div>
          <div class="empty-desc">自定义技能编排与热加载功能即将推出</div>
        </div>
      </div>

      <!-- 工具 (Tool) -->
      <div v-if="activeTab === 'tool'" class="tab-content">
        <h2>工具</h2>
        <div class="tool-list">
          <div class="tool-card">
            <div class="tool-icon">🔍</div>
            <div class="tool-info">
              <div class="tool-name">web_search</div>
              <div class="tool-desc">联网搜索工具，支持通过搜索引擎查询实时信息</div>
            </div>
            <span class="tool-badge builtin">内置</span>
          </div>
          <div class="tool-card">
            <div class="tool-icon">💻</div>
            <div class="tool-info">
              <div class="tool-name">code_exec</div>
              <div class="tool-desc">代码执行工具，支持在沙箱环境中运行 Python 代码</div>
            </div>
            <span class="tool-badge builtin">内置</span>
          </div>
          <div class="tool-card">
            <div class="tool-icon">📁</div>
            <div class="tool-info">
              <div class="tool-name">file_manager</div>
              <div class="tool-desc">文件管理器，支持读取、写入、搜索、编辑、复制、移动、删除等操作</div>
            </div>
            <span class="tool-badge builtin">内置</span>
          </div>
        </div>

        <hr class="divider" />
        <h3>信任模式</h3>
        <div class="trust-mode-row">
          <div class="trust-info">
            <div class="trust-label">🔒 信任模式</div>
            <div class="trust-desc">开启后，除系统核心文件外，所有文件操作无需确认直接执行。</div>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" v-model="trustMode" @change="saveTrustMode" />
            <span class="toggle-slider"></span>
          </label>
        </div>
      </div>

      <!-- 记忆管理 (Memory) -->
      <div v-if="activeTab === 'memory'" class="tab-content">
        <h2>记忆管理</h2>
        <p class="tab-desc">Agent 会自动记住用户偏好，也可手动添加/编辑/删除。</p>

        <!-- 分类筛选 -->
        <div class="memory-filters">
          <button v-for="cat in ['all', 'preference', 'fact', 'instruction', 'general']"
                  :key="cat"
                  :class="{ active: memoryFilter === cat }"
                  @click="memoryFilter = cat; loadMemories()">
            {{ memoryLabel(cat) }}
          </button>
        </div>

        <!-- 搜索 -->
        <input type="text" v-model="memorySearch" placeholder="搜索记忆..." class="memory-search" />

        <!-- 添加记忆 -->
        <div class="memory-add">
          <input type="text" v-model="newMemoryContent" placeholder="添加新记忆..." />
          <select v-model="newMemoryCategory">
            <option value="preference">偏好</option>
            <option value="fact">事实</option>
            <option value="instruction">指令</option>
            <option value="general">通用</option>
          </select>
          <button @click="addMemory">添加</button>
        </div>

        <!-- 记忆列表 -->
        <div class="memory-list">
          <div v-for="mem in filteredMemories" :key="mem.id" class="memory-card">
            <div class="memory-content" v-if="editingMemoryId !== mem.id">
              {{ mem.content }}
            </div>
            <input v-else type="text" v-model="editingMemoryContent" @keyup.enter="saveEditMemory(mem.id)" />
            <div class="memory-meta">
              <span class="memory-category" :class="mem.category">{{ memoryLabel(mem.category) }}</span>
              <span class="memory-source">{{ mem.source === 'auto' ? '自动' : '手动' }}</span>
              <span class="memory-time">{{ formatTime(mem.created_at) }}</span>
            </div>
            <div class="memory-actions">
              <button v-if="editingMemoryId !== mem.id" @click="startEditMemory(mem)">编辑</button>
              <button v-else @click="saveEditMemory(mem.id)">保存</button>
              <button @click="deleteMemory(mem.id)" class="btn-danger">删除</button>
            </div>
          </div>
        </div>
      </div>

      <!-- 监控 (Monitor) -->
      <div v-if="activeTab === 'monitor'" class="tab-content">
        <h2>运行监控</h2>
        <div class="monitor-toolbar">
          <button @click="fetchLogs" class="monitor-btn">🔄 刷新</button>
          <button @click="clearLogs" class="monitor-btn btn-danger">🗑 清空日志</button>
          <label class="monitor-auto">
            <input type="checkbox" v-model="autoRefresh" /> 自动刷新（3s）
          </label>
          <span class="monitor-count">共 {{ logLines.length }} 行</span>
        </div>
        <div class="monitor-log">
          <div v-for="(line, i) in logLines" :key="i" class="log-line" :class="logLevel(line)">
            {{ line }}
          </div>
          <div v-if="!logLines.length" class="log-empty">暂无日志</div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useThemeStore } from '../stores/theme'
import { usePersonaStore } from '../stores/persona'
import AssetUploader from '../components/AssetUploader.vue'
import QQBotConfig from '../components/QQBotConfig.vue'

const activeTab = ref('persona')
const themeStore = useThemeStore()
const personaStore = usePersonaStore()

const menuItems = [
  { id: 'persona', icon: '🎭', label: '次元设置' },
  { id: 'themepack', icon: '📦', label: '主题包' },
  { id: 'model', icon: '🤖', label: '模型配置' },
  { id: 'channel', icon: '📡', label: '通道管理' },
  { id: 'plugin', icon: '🔌', label: '插件管理' },
  { id: 'skill', icon: '⚡', label: '技能' },
  { id: 'tool', icon: '🔧', label: '工具' },
  { id: 'memory', icon: '🧠', label: '记忆' },
    { id: 'monitor', icon: '📊', label: '监控' },
  ]

// --- Model Config ---
const form_model = reactive({ api_key: '', base_url: '', model_name: '' })
const trustMode = ref(false)

async function loadTrustMode() {
  try {
    const resp = await fetch('/api/config/trust_mode')
    const data = await resp.json()
    trustMode.value = data.enabled === true || data.enabled === 'true'
  } catch { trustMode.value = false }
}

async function saveTrustMode() {
  try {
    await fetch('/api/config/trust_mode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: trustMode.value })
    })
  } catch {}
}

loadTrustMode()

onMounted(async () => {
  const resp = await fetch('/api/config/model')
  const data = await resp.json()
  form_model.base_url = data.base_url || ''
  form_model.model_name = data.model_name || ''
  form_model.api_key = data.api_key || ''
  await loadThemePacks()
      // 重新应用主题 CSS
      await themeStore.applyTheme(editingPackId.value)
  await loadMemories()
})

async function saveModel() {
  await fetch('/api/config/model', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(form_model)
  })
  alert('保存成功')
}

// --- Theme Packs (shared between persona & themepack tabs) ---
const themePacks = ref([])

async function loadThemePacks() {
  try {
    const resp = await fetch('/api/themepacks')
    const data = await resp.json()
    themePacks.value = Array.isArray(data) ? data : []
  } catch {
    themePacks.value = []
  }
}

// --- 次元设置 tab: Editor state ---
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

// Color definitions (same as ThemeCreator)
const colorDefs = [
  { var: 'primary', label: '主色调', cssVar: '--primary' },
  { var: 'bgPrimary', label: '主背景', cssVar: '--bg-primary' },
  { var: 'bgSecondary', label: '次背景', cssVar: '--bg-secondary' },
  { var: 'textPrimary', label: '主文字', cssVar: '--text-primary' },
  { var: 'textSecondary', label: '次文字', cssVar: '--text-secondary' },
  { var: 'border', label: '边框色', cssVar: '--border' },
  { var: 'bubbleUser', label: '用户气泡', cssVar: '--bubble-user' },
  { var: 'bubbleAgent', label: 'Agent气泡', cssVar: '--bubble-agent' },
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
  if (varName === 'bubbleUser') {
    const r = parseInt(hexVal.slice(1, 3), 16)
    const g = parseInt(hexVal.slice(3, 5), 16)
    const b = parseInt(hexVal.slice(5, 7), 16)
    editingPack.value.theme.colors[varName] = 'rgba(' + r + ',' + g + ',' + b + ',0.15)'
  } else if (varName === '--bubble-agent') {
    const r = parseInt(hexVal.slice(1, 3), 16)
    const g = parseInt(hexVal.slice(3, 5), 16)
    const b = parseInt(hexVal.slice(5, 7), 16)
    editingPack.value.theme.colors[varName] = 'rgba(' + r + ',' + g + ',' + b + ',0.9)'
  } else {
    editingPack.value.theme.colors[varName] = hexVal
  }
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
    },
    theme: {
      name: '',
      colors: {
        '--primary': '#7c5cfc',
        '--bg-primary': '#0f0f1a',
        '--bg-secondary': '#1a1a2e',
        '--text-primary': '#e8e8f0',
        '--text-secondary': '#8888aa',
        '--border': '#2a2a40',
        '--bubble-user': 'rgba(124,92,252,0.15)',
        '--bubble-agent': 'rgba(30,30,50,0.9)',
      },
      fonts: { family: "'Noto Sans SC', sans-serif", sizeBase: 14, sizeSmall: 12, lineHeight: 1.6 },
      spacing: { bubbleRadius: 12, bubblePadding: '10px 14px', sidebarWidth: 220, inputRadius: 8 },
    },
  }
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
    },
    theme: {
      name: data.theme?.name || '',
      colors: { ...empty.theme.colors, ...(data.theme?.colors || {}) },
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
    // If detail endpoint not available, use list data
    const pack = themePacks.value.find(p => p.id === packId)
    editingPack.value = normalizePack(pack || { id: packId })
  }
}

async function createNewPack() {
  const name = window.prompt('请输入主题包名称')
  if (!name) return
  const id = name.toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]/g, '_').replace(/_+/g, '_').slice(0, 32) || 'pack_' + Date.now()
  try {
    const resp = await fetch('/api/themepacks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, name })
    })
    if (resp.ok) {
      const data = await resp.json()
      await loadThemePacks()
      // 重新加载编辑的主题 CSS
      await themeStore.applyTheme(editingPackId.value)
      if (data.id) openEditor(data.id)
    } else {
      const err = await resp.json()
      alert(err.detail || '创建失败')
    }
  } catch (e) {
    alert('创建失败: ' + e.message)
  }
}

async function savePack() {
  if (!editingPackId.value || !editingPack.value) return
  try {
    const resp = await fetch(`/api/themepacks/${editingPackId.value}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editingPack.value)
    })
    if (resp.ok) {
      // 重新加载主题
      await themeStore.applyTheme(editingPackId.value)
      alert('保存成功')
      await loadThemePacks()
    } else {
      const err = await resp.json()
      alert(err.detail || '保存失败')
    }
  } catch (e) {
    alert('保存失败: ' + e.message)
  }
}

function cancelEdit() {
  editingPackId.value = null
  editingPack.value = null
}

// --- 主题包管理 tab: Actions ---
async function exportPack(packId) {
  try {
    const resp = await fetch(`/api/themepacks/${packId}/export`)
    if (resp.ok) {
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${packId}-themepack.zip`
      a.click()
      URL.revokeObjectURL(url)
    } else {
      alert('导出失败')
    }
  } catch (e) {
    alert('导出失败: ' + e.message)
  }
}

async function deletePack(packId) {
  if (!confirm(`确定删除主题包「${packId}」？`)) return
  try {
    const resp = await fetch(`/api/themepacks/${packId}`, { method: 'DELETE' })
    if (resp.ok) {
      await loadThemePacks()
      // 重新加载编辑的主题 CSS
      await themeStore.applyTheme(editingPackId.value)
      if (editingPackId.value === packId) cancelEdit()
    } else {
      const err = await resp.json()
      alert(err.detail || '删除失败')
    }
  } catch (e) {
    alert('删除失败: ' + e.message)
  }
}

async function applyPack(packId) {
  if (!confirm(`确定一键更新关联会话「${packId}」？`)) return
  try {
    const resp = await fetch(`/api/themepacks/${packId}/apply`, { method: 'POST' })
    if (resp.ok) {
      alert('已更新关联会话')
    } else {
      const err = await resp.json()
      alert(err.detail || '更新失败')
    }
  } catch (e) {
    alert('更新失败: ' + e.message)
  }
}

async function importPack(e) {
  const file = e.target.files[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  try {
    const resp = await fetch('/api/themepacks/import', { method: 'POST', body: formData })
    if (resp.ok) {
      const data = await resp.json()
      await loadThemePacks()
      // 重新加载编辑的主题 CSS
      await themeStore.applyTheme(editingPackId.value)
      alert(`导入成功！主题包: ${data.name || data.id || '已导入'}`)
    } else {
      const err = await resp.json()
      alert(err.detail || '导入失败')
    }
  } catch (e) {
    alert('导入失败: ' + e.message)
  }
}

// --- 记忆管理 (Memory) ---
const memories = ref([])
const memoryFilter = ref('all')
const memorySearch = ref('')
const newMemoryContent = ref('')
const newMemoryCategory = ref('preference')
const editingMemoryId = ref(null)
const editingMemoryContent = ref('')

const filteredMemories = computed(() => {
  let list = memories.value
  if (memorySearch.value) {
    const q = memorySearch.value.toLowerCase()
    list = list.filter(m => m.content.toLowerCase().includes(q))
  }
  return list
})

function memoryLabel(cat) {
  const labels = { all: '全部', preference: '偏好', fact: '事实', instruction: '指令', general: '通用' }
  return labels[cat] || cat
}

async function loadMemories() {
  try {
    const url = memoryFilter.value === 'all' ? '/api/memories' : `/api/memories?category=${memoryFilter.value}`
    const resp = await fetch(url)
    memories.value = await resp.json()
  } catch {
    memories.value = []
  }
}

async function addMemory() {
  if (!newMemoryContent.value.trim()) return
  await fetch('/api/memories', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: newMemoryContent.value, category: newMemoryCategory.value })
  })
  newMemoryContent.value = ''
  await loadMemories()
}

function startEditMemory(mem) {
  editingMemoryId.value = mem.id
  editingMemoryContent.value = mem.content
}

async function saveEditMemory(id) {
  await fetch(`/api/memories/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: editingMemoryContent.value })
  })
  editingMemoryId.value = null
  await loadMemories()
}

async function deleteMemory(id) {
  await fetch(`/api/memories/${id}`, { method: 'DELETE' })
  await loadMemories()
}

function formatTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleString('zh-CN')
}

// --- Monitor ---
const logLines = ref([])
const autoRefresh = ref(false)
let monitorTimer = null

async function fetchLogs() {
  try {
    const resp = await fetch('/api/logs?lines=200')
    const data = await resp.json()
    logLines.value = data.lines || []
  } catch { logLines.value = [] }
}

async function clearLogs() {
  await fetch('/api/logs', { method: 'DELETE' })
  logLines.value = []
}

function logLevel(line) {
  if (line.includes('[ERROR]')) return 'log-error'
  if (line.includes('[WARN]')) return 'log-warn'
  return 'log-info'
}

watch(autoRefresh, (val) => {
  if (val) {
    fetchLogs()
    monitorTimer = setInterval(fetchLogs, 3000)
  } else {
    if (monitorTimer) clearInterval(monitorTimer)
  }
})

// 切换到监控 tab 时自动加载
watch(() => activeTab.value, (tab) => {
  if (tab === 'monitor') fetchLogs()
})
</script>

<style scoped>
.settings-layout {
  display: flex;
  height: calc(100vh - 49px);
  overflow: hidden;
}

/* Sidebar */
.sidebar {
  width: var(--sidebar-width, 180px);
  min-width: var(--sidebar-width, 180px);
  background: var(--sidebar-bg, var(--bg-secondary, #1e1e2e));
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding-top: 8px;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 18px;
  cursor: pointer;
  font-size: 14px;
  color: var(--text-secondary);
  transition: background 0.15s, color 0.15s;
  border-left: 3px solid transparent;
  user-select: none;
}

.menu-item:hover {
  background: rgba(124, 92, 252, 0.08);
  color: var(--text-primary);
}

.menu-item.active {
  background: linear-gradient(90deg, rgba(124, 92, 252, 0.25), rgba(124, 92, 252, 0.05));
  color: var(--primary);
  border-left-color: var(--primary);
  border-left-width: 4px;
  font-weight: 700;
  box-shadow: inset 3px 0 0 var(--primary), 0 0 12px rgba(160, 130, 255, 0.08);
}

.menu-icon {
  font-size: 16px;
  width: 20px;
  text-align: center;
}

/* Content Area */
.content {
  flex: 1;
  overflow-y: auto;
  padding: 28px 36px;
}

.tab-content h2 {
  font-size: 20px;
  margin-bottom: 20px;
}

/* Theme Pack Grid (shared) */
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
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 10px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.pack-card:hover {
  border-color: var(--primary);
}
.pack-card.selected {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px rgba(124, 92, 252, 0.2);
}

.pack-preview {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  flex-shrink: 0;
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
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 12px;
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
  border-bottom: 1px solid var(--border);
  padding-bottom: 10px;
}

.tab-btn {
  padding: 6px 18px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-primary);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.15s;
}
.tab-btn.active {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}
.tab-btn:hover:not(.active) {
  border-color: var(--primary);
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
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-primary);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 12px;
  transition: all 0.15s;
}
.sub-tab-btn.active {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}
.sub-tab-btn:hover:not(.active) {
  border-color: var(--primary);
}

.sub-panel {
  margin-bottom: 10px;
}

/* Color grid */
.color-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.color-item label {
  font-size: 12px;
  color: var(--text-secondary);
  display: block;
  margin-bottom: 2px;
}
.color-input {
  display: flex;
  align-items: center;
  gap: 6px;
}
.color-input input[type="color"] {
  width: 32px;
  height: 32px;
  border: none;
  cursor: pointer;
  background: none;
}
.color-val {
  font-size: 11px;
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
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 13px;
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
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
}
textarea {
  resize: vertical;
  font-family: inherit;
}
select {
  max-width: 300px;
}
fieldset {
  border: 1px solid var(--border);
  border-radius: 10px;
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
  width: 40px;
  font-size: 13px;
  color: var(--text-secondary);
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

/* Buttons */
.btn-new {
  padding: 8px 20px;
  font-size: 13px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: opacity 0.15s;
}
.btn-new:hover { opacity: 0.85; }

.btn-save {
  padding: 10px 28px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
}
.btn-cancel {
  padding: 10px 28px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
}
.btn-cancel:hover {
  border-color: var(--primary);
}
.actions {
  margin-top: 20px;
  display: flex;
  gap: 12px;
}

/* 主题包管理 tab */
.tp-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}
.tp-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  transition: all 0.15s;
  background: var(--bg-primary);
}
.tp-card:hover { border-color: var(--primary); }
.tp-preview {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  flex-shrink: 0;
}
.tp-info { flex: 1; min-width: 0; }
.tp-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.tp-meta {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
  display: flex;
  gap: 8px;
}
.tp-actions { display: flex; gap: 4px; }

.btn-sm {
  width: 36px;
  height: 36px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.btn-sm:hover { border-color: var(--primary); }
.btn-sm-danger:hover { border-color: #e74c3c; }

.package-actions {
  display: flex;
  gap: 10px;
  margin-top: 12px;
}
.btn-action {
  flex: 1;
  padding: 10px 16px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 13px;
  text-align: center;
  transition: all 0.2s;
}
.btn-action:hover {
  border-color: var(--primary);
  color: var(--primary);
}

/* Divider */
.divider {
  border: none;
  border-top: 1px solid var(--border);
  margin: 28px 0;
}

/* Tool list */
.tool-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.tool-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 20px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 10px;
}
.tool-icon {
  font-size: 24px;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-secondary);
  border-radius: 8px;
}
.tool-info {
  flex: 1;
}
.tool-name {
  font-size: 14px;
  font-weight: 600;
  font-family: monospace;
}
.tool-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 2px;
}
.tool-badge {
  font-size: 11px;
  padding: 2px 10px;
  border-radius: 10px;
  background: rgba(124, 92, 252, 0.12);
  color: var(--primary);
  font-weight: 600;
}

/* Placeholder */
.placeholder {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-secondary);
}
.placeholder-icon {
  font-size: 48px;
  display: block;
  margin-bottom: 16px;
}
.placeholder p {
  font-size: 16px;
  margin: 4px 0;
}
.placeholder-sub {
  font-size: 13px;
  opacity: 0.7;
}

/* Empty state */
.empty-state { text-align: center; padding: 60px 20px; }
.empty-icon { font-size: 48px; margin-bottom: 16px; }
.empty-title { font-size: 18px; font-weight: 600; color: var(--text-primary); margin-bottom: 8px; }
.empty-desc { color: var(--text-secondary); font-size: 14px; }
.empty-desc code { background: rgba(124,92,252,0.15); padding: 2px 6px; border-radius: 4px; font-size: 13px; }

.empty-hint {
  text-align: center;
  padding: 24px;
  color: var(--text-secondary);
  font-size: 14px;
}
.hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 12px;
}
.trust-mode-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  background: var(--bg-primary);
  border-radius: 8px;
  border: 1px solid var(--border);
}
.trust-label { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.trust-desc { font-size: 12px; color: var(--text-secondary); margin-top: 4px; }
.toggle-switch {
  position: relative;
  width: 44px;
  height: 24px;
  flex-shrink: 0;
}
.toggle-switch input { opacity: 0; width: 0; height: 0; }
.toggle-slider {
  position: absolute;
  cursor: pointer;
  top: 0; left: 0; right: 0; bottom: 0;
  background: var(--border);
  border-radius: 12px;
  transition: 0.2s;
}
.toggle-slider::before {
  content: '';
  position: absolute;
  height: 18px; width: 18px;
  left: 3px; bottom: 3px;
  background: white;
  border-radius: 50%;
  transition: 0.2s;
}
.toggle-switch input:checked + .toggle-slider { background: var(--primary); }
.toggle-switch input:checked + .toggle-slider::before { transform: translateX(20px); }

/* 记忆管理 */
.tab-desc { font-size: 13px; color: var(--text-secondary); margin-bottom: 16px; }
.memory-filters { display: flex; gap: 8px; margin-bottom: 12px; }
.memory-filters button { padding: 4px 12px; border-radius: 12px; border: 1px solid var(--border); background: transparent; color: var(--text-secondary); cursor: pointer; font-size: 12px; }
.memory-filters button.active { background: var(--primary); color: white; border-color: var(--primary); }
.memory-search { width: 100%; padding: 8px 12px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg-primary); color: var(--text-primary); margin-bottom: 12px; }
.memory-add { display: flex; gap: 8px; margin-bottom: 16px; }
.memory-add input { flex: 1; padding: 8px 12px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg-primary); color: var(--text-primary); }
.memory-add select { padding: 8px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg-primary); color: var(--text-primary); }
.memory-add button { padding: 8px 16px; border: none; border-radius: 6px; background: var(--primary); color: white; cursor: pointer; }
.memory-list { display: flex; flex-direction: column; gap: 8px; }
.memory-card { padding: 12px; background: var(--bg-primary); border-radius: 8px; border: 1px solid var(--border); }
.memory-content { font-size: 14px; color: var(--text-primary); margin-bottom: 8px; }
.memory-meta { display: flex; gap: 8px; font-size: 11px; color: var(--text-secondary); margin-bottom: 8px; }
.memory-category { padding: 2px 6px; border-radius: 4px; }
.memory-category.preference { background: rgba(59,130,246,0.15); color: #3b82f6; }
.memory-category.fact { background: rgba(34,197,94,0.15); color: #22c55e; }
.memory-category.instruction { background: rgba(239,68,68,0.15); color: #ef4444; }
.memory-category.general { background: rgba(136,136,170,0.15); color: #8888aa; }
.memory-actions { display: flex; gap: 8px; }
.memory-actions button { padding: 4px 8px; border: none; border-radius: 4px; background: var(--bg-secondary); color: var(--text-secondary); cursor: pointer; font-size: 12px; }
.memory-actions .btn-danger { color: #ef4444; }
.monitor-toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.monitor-btn { padding: 6px 12px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg-secondary); color: var(--text-primary); cursor: pointer; font-size: 12px; }
.monitor-btn:hover { background: var(--bg-primary); }
.monitor-auto { display: flex; align-items: center; gap: 4px; font-size: 12px; color: var(--text-secondary); cursor: pointer; }
.monitor-count { font-size: 12px; color: var(--text-secondary); margin-left: auto; }
.monitor-log { background: #0d1117; border-radius: 8px; padding: 12px; max-height: calc(100vh - 260px); overflow-y: auto; font-family: 'Cascadia Code', 'Fira Code', monospace; font-size: 12px; line-height: 1.6; }
.log-line { padding: 1px 0; white-space: pre-wrap; word-break: break-all; }
.log-info { color: #8b949e; }
.log-warn { color: #d29922; }
.log-error { color: #f85149; }
.log-empty { color: #484f58; text-align: center; padding: 40px; }
.pack-color-preview { width: 32px; height: 32px; border-radius: 6px; flex-shrink: 0; }
.empty-state { text-align: center; padding: 60px 20px; }
.empty-icon { font-size: 48px; margin-bottom: 16px; }
.empty-title { font-size: 18px; font-weight: 600; color: var(--text-primary); margin-bottom: 8px; }
.empty-desc { color: var(--text-secondary); font-size: 14px; }
.empty-desc code { background: rgba(124,92,252,0.15); padding: 2px 6px; border-radius: 4px; font-size: 13px; }
</style>
