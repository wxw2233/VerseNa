<template>
  <div class="persona-editor">
    <!-- Left: persona list -->
    <aside class="persona-list">
      <div class="list-header">
        <h3>角色列表</h3>
        <button class="btn-new" @click="startCreate">+ 新建</button>
      </div>
      <div
        v-for="p in personas"
        :key="p.name"
        class="list-item"
        :class="{ active: selectedId === p.name }"
        @click="selectPersona(p.name)"
      >
        <span class="item-name">{{ p.name }}</span>
        <span class="item-desc">{{ p.description || '—' }}</span>
      </div>
    </aside>

    <!-- Right: editor form -->
    <section class="editor-panel">
      <div v-if="!form" class="empty-hint">从左侧选择角色，或点击「新建」</div>

      <template v-else>
        <h2>{{ isCreate ? '新建角色' : '编辑角色 — ' + form.id }}</h2>

        <!-- ID -->
        <div class="form-group">
          <label>ID（英文标识）</label>
          <input v-model="form.id" :disabled="!isCreate" placeholder="e.g. my_character" />
        </div>

        <!-- Name -->
        <div class="form-group">
          <label>名称</label>
          <input v-model="form.name" placeholder="角色显示名" />
        </div>

        <!-- Description -->
        <div class="form-group">
          <label>描述</label>
          <input v-model="form.description" placeholder="一句话简介" />
        </div>

        <!-- Prompt -->
        <div class="form-group">
          <label>人设 Prompt</label>
          <textarea v-model="form.prompt" rows="6" placeholder="角色的系统提示词……"></textarea>
        </div>

        <!-- Emotion Weights -->
        <fieldset class="form-group">
          <legend>情感权重</legend>
          <div v-for="key in emotionKeys" :key="key" class="slider-row">
            <span class="slider-label">{{ emotionLabels[key] }}</span>
            <input type="range" min="0" max="1" step="0.1" v-model.number="form.emotion_weights[key]" />
            <span class="slider-val">{{ form.emotion_weights[key].toFixed(1) }}</span>
          </div>
        </fieldset>

        <!-- Speech Style -->
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

        <!-- Theme Binding -->
        <div class="form-group">
          <label>主题绑定</label>
          <select v-model="form.theme_binding">
            <option value="default">default</option>
            <option v-for="t in themes" :key="t" :value="t">{{ t }}</option>
          </select>
        </div>

        <!-- Actions -->
        <div class="actions">
          <button class="btn-save" @click="save">保存</button>
          <button v-if="!isCreate && form.id !== 'default'" class="btn-delete" @click="remove">删除</button>
          <button class="btn-cancel" @click="cancel">取消</button>
        </div>
      </template>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

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

onMounted(async () => {
  await loadPersonas()
  await loadThemes()
})

async function loadPersonas() {
  const resp = await fetch('/api/personas')
  personas.value = await resp.json()
}

async function loadThemes() {
  try {
    const resp = await fetch('/api/themes')
    const data = await resp.json()
    if (Array.isArray(data)) {
      themes.value = data.map(t => typeof t === 'string' ? t : t.id)
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

async function save() {
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

async function remove() {
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

function cancel() {
  form.value = null
  selectedId.value = null
}
</script>

<style scoped>
.persona-editor {
  display: flex;
  height: calc(100vh - 49px);
  overflow: hidden;
}

/* Sidebar */
.persona-list {
  width: 240px;
  min-width: 200px;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}
.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}
.list-header h3 {
  font-size: 14px;
  color: var(--text-secondary);
}
.btn-new {
  padding: 4px 10px;
  font-size: 12px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}
.list-item {
  padding: 10px 16px;
  cursor: pointer;
  border-bottom: 1px solid var(--border);
  transition: background 0.15s;
}
.list-item:hover {
  background: rgba(124, 92, 252, 0.08);
}
.list-item.active {
  background: rgba(124, 92, 252, 0.18);
  border-left: 3px solid var(--primary);
}
.item-name {
  display: block;
  font-size: 14px;
  font-weight: 600;
}
.item-desc {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Editor Panel */
.editor-panel {
  flex: 1;
  padding: 24px 32px;
  overflow-y: auto;
}
.editor-panel h2 {
  font-size: 20px;
  margin-bottom: 20px;
}
.empty-hint {
  color: var(--text-secondary);
  margin-top: 80px;
  text-align: center;
}

/* Form */
.form-group {
  margin-bottom: 16px;
}
.form-group label {
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

/* Actions */
.actions {
  margin-top: 24px;
  display: flex;
  gap: 12px;
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
.btn-cancel {
  padding: 10px 28px;
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
}
</style>
