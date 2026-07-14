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
      <!-- 次元设置 (Persona) -->
      <div v-if="activeTab === 'persona'" class="tab-content">
        <h2>角色管理</h2>
        <div class="persona-section">
          <div class="current-persona-label">当前角色：{{ currentPersonaName }} ✓</div>
          <div class="persona-grid">
            <div
              v-for="p in personas"
              :key="p.id"
              class="persona-card"
              :class="{ selected: selectedId === p.id, current: personaStore.current === p.id }"
              @click="handleCardClick(p.id)"
            >
              <div class="card-name">
                {{ p.name }}
                <span v-if="personaStore.current === p.id" class="current-badge">✓</span>
              </div>
              <div class="card-desc">{{ p.description || '—' }}</div>
            </div>
          </div>
          <div v-if="personas.length === 0" class="empty-hint">暂无角色</div>
        </div>

        <!-- Inline Editor -->
        <div v-if="selectedId && form" class="persona-editor-inline">
          <h3>编辑角色 — {{ form.name }}</h3>
          <div class="form-group">
            <label>名称</label>
            <input v-model="form.name" placeholder="角色显示名" />
          </div>
          <div class="form-group">
            <label>描述</label>
            <input v-model="form.description" placeholder="一句话简介" />
          </div>
          <div class="form-group">
            <label>人设 Prompt</label>
            <textarea v-model="form.prompt" rows="5" placeholder="角色的系统提示词……"></textarea>
          </div>
          <fieldset class="form-group">
            <legend>情感权重</legend>
            <div v-for="key in emotionKeys" :key="key" class="slider-row">
              <span class="slider-label">{{ emotionLabels[key] }}</span>
              <input type="range" min="0" max="1" step="0.1" v-model.number="form.emotion_weights[key]" />
              <span class="slider-val">{{ form.emotion_weights[key].toFixed(1) }}</span>
            </div>
          </fieldset>
          <fieldset class="form-group">
            <legend>说话风格</legend>
            <div class="form-group">
              <label>语气</label>
              <input v-model="form.speech_style.tone" placeholder="如：活泼、温柔、冷酷" />
            </div>
            <div class="form-group">
              <label>口头禅</label>
              <input v-model="form.speech_style.catchphrase" placeholder="如：だよね～" />
            </div>
            <div class="form-group">
              <label>表情频率</label>
              <select v-model="form.speech_style.emoji_frequency">
                <option value="low">低</option>
                <option value="medium">中</option>
                <option value="high">高</option>
              </select>
            </div>
            <div class="form-group">
              <label>正式度</label>
              <select v-model="form.speech_style.formality">
                <option value="casual">随意</option>
                <option value="polite">礼貌</option>
                <option value="formal">正式</option>
              </select>
            </div>
          </fieldset>
          <div class="form-group">
            <label>主题绑定</label>
            <select v-model="form.theme_binding">
              <option value="default">default</option>
              <option v-for="t in themes" :key="t" :value="t">{{ t }}</option>
            </select>
          </div>
          <div class="actions">
            <button class="btn-save" @click="savePersona">保存</button>
            <button class="btn-reset" @click="resetToDefault">重置为默认</button>
            <button v-if="form.id !== 'default'" class="btn-delete" @click="removePersona">删除</button>
          </div>
        </div>

        <hr class="divider" />
        <h3>主题管理</h3>
        <ThemeSwitcher />
        <ThemeCreator />
        <AssetUploader />
      </div>

      <!-- 主题包 (Theme Pack) -->
      <div v-if="activeTab === 'themepack'" class="tab-content">
        <h2>主题包</h2>
        <p class="hint">导出/导入完整主题包（包含颜色、素材、角色配置）</p>
        <div class="themepack-grid">
          <div v-for="t in themes" :key="t.id" class="themepack-card" :class="{ active: themeStore.current === t.id }">
            <div class="themepack-preview" :style="{ background: t.colors?.primary || '#7c5cfc' }"></div>
            <div class="themepack-info">
              <div class="themepack-name">{{ t.name }}</div>
              <div class="themepack-id">{{ t.id }}</div>
            </div>
            <div class="themepack-actions">
              <button class="btn-sm" @click="exportTheme(t.id)" title="导出">📦</button>
              <button class="btn-sm" @click="themeStore.applyTheme(t.id)" title="应用">✓</button>
            </div>
          </div>
        </div>
        <div class="package-actions">
          <label class="btn-action">
            导入主题包（zip）
            <input type="file" accept=".zip" @change="importTheme" style="display:none" />
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
        <PluginManager />
      </div>

      <!-- 技能 (Skill) -->
      <div v-if="activeTab === 'skill'" class="tab-content">
        <h2>技能</h2>
        <div class="placeholder">
          <span class="placeholder-icon">⚡</span>
          <p>技能管理功能即将推出</p>
          <p class="placeholder-sub">敬请期待自定义技能编排与热加载</p>
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
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useThemeStore } from '../stores/theme'
import { usePersonaStore } from '../stores/persona'
import ThemeSwitcher from '../components/ThemeSwitcher.vue'
import ThemeCreator from '../components/ThemeCreator.vue'
import AssetUploader from '../components/AssetUploader.vue'
import PluginManager from '../components/PluginManager.vue'
import QQBotConfig from '../components/QQBotConfig.vue'

const activeTab = ref('persona')

const menuItems = [
  { id: 'persona', icon: '🎭', label: '次元设置' },
  { id: 'themepack', icon: '📦', label: '主题包' },
  { id: 'model', icon: '🤖', label: '模型配置' },
  { id: 'channel', icon: '📡', label: '通道管理' },
  { id: 'plugin', icon: '🔌', label: '插件管理' },
  { id: 'skill', icon: '⚡', label: '技能' },
  { id: 'tool', icon: '🔧', label: '工具' },
]

// --- Model Config ---
const themeStore = useThemeStore()
const personaStore = usePersonaStore()
const form_model = reactive({ api_key: '', base_url: '', model_name: '' })

onMounted(async () => {
  const resp = await fetch('/api/config/model')
  const data = await resp.json()
  form_model.base_url = data.base_url || ''
  form_model.model_name = data.model_name || ''
  form_model.api_key = data.api_key || ''
  await loadPersonas()
  await loadThemes()
})

async function saveModel() {
  await fetch('/api/config/model', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(form_model)
  })
  alert('保存成功')
}

// --- Persona Editor (from PersonaEditorView) ---
const personas = ref([])
const themes = ref([])
const selectedId = ref(null)
const isCreate = ref(false)
const form = ref(null)

const emotionKeys = ['cheerful', 'shy', 'curious', 'angry', 'sad']
const emotionLabels = {
  cheerful: '开朗',
  shy: '害羞',
  curious: '好奇',
  angry: '愤怒',
  sad: '悲伤',
}

async function loadPersonas() {
  const resp = await fetch('/api/personas')
  personas.value = await resp.json()
}

async function loadThemes() {
  try {
    const resp = await fetch('/api/themes')
    const data = await resp.json()
    if (Array.isArray(data)) {
      themes.value = data.map(t => typeof t === 'string' ? { id: t, name: t } : t)
    } else if (data.themes) {
      themes.value = data.themes
    } else {
      themes.value = []
    }
  } catch {
    themes.value = []
  }
}

async function selectPersona(name) {
  selectedId.value = name
  isCreate.value = false
  const resp = await fetch(`/api/personas/${name}/full`)
  const data = await resp.json()
  form.value = {
    id: data.id,
    name: data.config.name || '',
    description: data.config.description || '',
    prompt: data.prompt || '',
    emotion_weights: {
      cheerful: data.config.emotion_weights?.cheerful ?? 0.5,
      shy: data.config.emotion_weights?.shy ?? 0.2,
      curious: data.config.emotion_weights?.curious ?? 0.5,
      angry: data.config.emotion_weights?.angry ?? 0.1,
      sad: data.config.emotion_weights?.sad ?? 0.1,
    },
    speech_style: {
      tone: data.config.speech_style?.tone ?? '友好',
      catchphrase: data.config.speech_style?.catchphrase ?? '',
      emoji_frequency: data.config.speech_style?.emoji_frequency ?? 'medium',
      formality: data.config.speech_style?.formality ?? 'casual',
    },
    theme_binding: data.config.theme_binding ?? 'default',
  }
}

function startCreate() {
  selectedId.value = null
  isCreate.value = true
  form.value = {
    id: '',
    name: '',
    description: '',
    prompt: '',
    emotion_weights: { cheerful: 0.5, shy: 0.2, curious: 0.5, angry: 0.1, sad: 0.1 },
    speech_style: { tone: '友好', catchphrase: '', emoji_frequency: 'medium', formality: 'casual' },
    theme_binding: 'default',
  }
}

async function savePersona() {
  if (!form.value.id) { alert('请输入 ID'); return }
  if (!form.value.name) { alert('请输入名称'); return }

  const body = {
    id: form.value.id,
    name: form.value.name,
    description: form.value.description,
    prompt: form.value.prompt,
    emotion_weights: { ...form.value.emotion_weights },
    speech_style: { ...form.value.speech_style },
    theme_binding: form.value.theme_binding,
  }

  let resp
  if (isCreate.value) {
    resp = await fetch('/api/personas/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } else {
    resp = await fetch(`/api/personas/${form.value.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  }

  if (!resp.ok) {
    const err = await resp.json()
    alert(err.detail || '保存失败')
    return
  }

  alert('保存成功')
  isCreate.value = false
  selectedId.value = form.value.id
  await loadPersonas()
}

async function removePersona() {
  if (!confirm(`确定删除角色「${form.value.id}」？`)) return
  const resp = await fetch(`/api/personas/${form.value.id}`, { method: 'DELETE' })
  if (!resp.ok) {
    const err = await resp.json()
    alert(err.detail || '删除失败')
    return
  }
  form.value = null
  selectedId.value = null
  await loadPersonas()
}

function cancelEdit() {
  form.value = null
  selectedId.value = null
}

function handleCardClick(id) {
  personaStore.switchPersona(id)
  selectPersona(id)
}

const currentPersonaName = computed(() => {
  const p = personas.value.find(x => x.id === personaStore.current)
  return p ? p.name : personaStore.current
})

async function resetToDefault() {
  if (!form.value || !selectedId.value) return
  await resetPersona(selectedId.value)
}

const defaultPersonaValues = {
  id: 'default',
  name: '默认助手',
  description: '一个友好的 AI 助手',
  prompt: '你是一个友好、乐于助人的 AI 助手。',
  emotion_weights: { cheerful: 0.5, shy: 0.2, curious: 0.5, angry: 0.1, sad: 0.1 },
  speech_style: { tone: '友好', catchphrase: '', emoji_frequency: 'medium', formality: 'casual' },
  theme_binding: 'default',
}

async function resetPersona(id) {
  if (!confirm(`确定要重置角色「${id}」为默认值？`)) return
  if (id === 'default') {
    // Reset default persona to original values
    const resp = await fetch('/api/personas/default', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(defaultPersonaValues),
    })
    if (resp.ok) {
      form.value = null
      selectedId.value = null
      await loadPersonas()
    } else {
      const err = await resp.json()
      alert(err.detail || '重置失败')
    }
  } else {
    // Custom persona: delete and reload
    const resp = await fetch(`/api/personas/${id}`, { method: 'DELETE' })
    if (resp.ok) {
      if (selectedId.value === id) {
        form.value = null
        selectedId.value = null
      }
      await loadPersonas()
    } else {
      const err = await resp.json()
      alert(err.detail || '重置失败')
    }
  }
}

async function exportTheme(themeId) {
  const resp = await fetch(`/api/themes/${themeId}/export`)
  if (resp.ok) {
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${themeId}-theme.zip`
    a.click()
    URL.revokeObjectURL(url)
  } else {
    alert('导出失败')
  }
}

async function importTheme(e) {
  const file = e.target.files[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  const resp = await fetch('/api/themes/import', { method: 'POST', body: formData })
  if (resp.ok) {
    const data = await resp.json()
    await themeStore.fetchThemes()
    alert(`导入成功！主题: ${data.theme_id}`)
  } else {
    const err = await resp.json()
    alert(err.detail || '导入失败')
  }
}
</script>

<style scoped>
.settings-layout {
  display: flex;
  height: calc(100vh - 49px);
  overflow: hidden;
}

/* Sidebar */
.sidebar {
  width: 180px;
  min-width: 180px;
  background: var(--bg-secondary, #1e1e2e);
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
  background: rgba(124, 92, 252, 0.15);
  color: var(--primary);
  border-left-color: var(--primary);
  font-weight: 600;
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

/* Persona cards */
.current-persona-label {
  font-size: 14px;
  color: var(--primary);
  font-weight: 600;
  margin-bottom: 12px;
}

.persona-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.persona-header h3 {
  font-size: 15px;
  color: var(--text-secondary);
}

.persona-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.persona-card {
  position: relative;
  padding: 14px 16px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 10px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.persona-card:hover {
  border-color: var(--primary);
}
.persona-card.selected {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px rgba(124, 92, 252, 0.2);
}
.persona-card.current {
  border-color: #7c5cfc;
  box-shadow: 0 0 0 2px rgba(124, 92, 252, 0.3);
}
.current-badge {
  color: #7c5cfc;
  font-weight: 700;
  margin-left: 4px;
}
.card-name {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 4px;
}
.card-desc {
  font-size: 12px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card-actions {
  position: absolute;
  top: -8px;
  right: -8px;
  display: flex;
  gap: 3px;
  opacity: 0;
  transition: opacity 0.15s;
}
.persona-card:hover .card-actions {
  opacity: 1;
}
.card-edit-btn, .card-reset-btn {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  color: white;
  border: none;
  font-size: 12px;
  line-height: 20px;
  text-align: center;
  cursor: pointer;
  padding: 0;
}
.card-edit-btn {
  background: var(--primary);
}
.card-edit-btn:hover {
  background: #6a4fe0;
}
.card-reset-btn {
  background: #f39c12;
}
.card-reset-btn:hover {
  background: #e67e22;
}

/* Inline persona editor */
.persona-editor-inline {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  margin: 20px 0;
}
.persona-editor-inline h3 {
  font-size: 16px;
  margin-bottom: 16px;
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
  padding: 5px 14px;
  font-size: 12px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}
.btn-save {
  padding: 10px 28px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
}
.btn-delete {
  padding: 10px 28px;
  background: #e74c3c;
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
}
.btn-reset {
  padding: 10px 28px;
  background: #f39c12;
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
}
.btn-cancel {
  padding: 10px 28px;
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
}
.actions {
  margin-top: 20px;
  display: flex;
  gap: 12px;
}

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
.package-actions {
  display: flex;
  gap: 10px;
  margin-top: 8px;
}
.btn-action {
  flex: 1;
  padding: 8px 16px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 6px;
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
.themepack-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}
.themepack-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  transition: all 0.15s;
}
.themepack-card:hover { border-color: var(--primary); }
.themepack-card.active { border-color: var(--primary); background: rgba(124,92,252,0.08); }
.themepack-preview {
  width: 36px; height: 36px; border-radius: 8px; flex-shrink: 0;
}
.themepack-info { flex: 1; min-width: 0; }
.themepack-name { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.themepack-id { font-size: 11px; color: var(--text-secondary); }
.themepack-actions { display: flex; gap: 4px; }
.btn-sm {
  width: 32px; height: 32px;
  background: transparent; border: 1px solid var(--border); border-radius: 6px;
  cursor: pointer; font-size: 14px; display: flex; align-items: center; justify-content: center;
}
.btn-sm:hover { border-color: var(--primary); }
</style>
