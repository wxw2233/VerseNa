<template>
  <div class="theme-switcher">
    <h3>主题</h3>
    <div class="theme-list">
      <div
        v-for="t in themeStore.themes"
        :key="t.id"
        class="theme-card"
        :class="{ active: themeStore.current === t.id }"
        @click="themeStore.applyTheme(t.id)"
      >
        <div class="theme-dot" :style="{ background: getPreviewColor(t.id) }"></div>
        <span>{{ t.name }}</span>
        <div class="card-actions">
          <button
            class="edit-btn"
            @click.stop="editTheme(t.id)"
            title="编辑主题"
          >&#9998;</button>
          <button
            class="reset-btn"
            @click.stop="resetTheme(t.id)"
            title="重置主题"
          >&#8634;</button>
          <button
            v-if="t.id !== 'default'"
            class="delete-btn"
            @click.stop="deleteTheme(t.id)"
            title="删除主题"
          >&times;</button>
        </div>
      </div>
    </div>

    <!-- Inline Theme Editor -->
    <div v-if="editingTheme" class="theme-editor-inline">
      <h3>编辑主题 — {{ editingTheme }}</h3>
      <div class="form-row">
        <label>主题名称</label>
        <input v-model="themeForm.name" placeholder="主题名称" />
      </div>
      <div class="color-grid">
        <div class="color-item" v-for="key in colorKeys" :key="key.key">
          <label>{{ key.label }}</label>
          <div class="color-input">
            <input type="color" v-model="themeForm[key.key]" />
            <span>{{ themeForm[key.key] }}</span>
          </div>
        </div>
      </div>
      <div class="form-row">
        <label>字体</label>
        <input v-model="themeForm.font" placeholder="Noto Sans SC" />
      </div>
      <div class="btn-row">
        <button class="btn-save" @click="saveEditTheme">保存</button>
        <button class="btn-cancel" @click="editingTheme = null">取消</button>
      </div>
      <div v-if="editMsg" class="msg">{{ editMsg }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useThemeStore } from '../stores/theme'
const themeStore = useThemeStore()

const previewColors = { default: '#7c5cfc', miku: '#39C5BB' }
function getPreviewColor(id) { return previewColors[id] || '#888' }

const colorKeys = [
  { key: 'primary', label: '主色调' },
  { key: 'bg_primary', label: '主背景' },
  { key: 'bg_secondary', label: '次背景' },
  { key: 'text_primary', label: '主文字' },
  { key: 'text_secondary', label: '次文字' },
  { key: 'border', label: '边框' },
]

const defaultThemeValues = {
  name: 'Default',
  primary: '#7c5cfc',
  bg_primary: '#0f0f1a',
  bg_secondary: '#1a1a2e',
  text_primary: '#e8e8f0',
  text_secondary: '#8888aa',
  border: '#2a2a40',
  font: 'Noto Sans SC',
}

const editingTheme = ref(null)
const editMsg = ref('')
const themeForm = reactive({
  name: '',
  primary: '#7c5cfc',
  bg_primary: '#0f0f1a',
  bg_secondary: '#1a1a2e',
  text_primary: '#e8e8f0',
  text_secondary: '#8888aa',
  border: '#2a2a40',
  font: 'Noto Sans SC',
})

async function editTheme(id) {
  editMsg.value = ''
  editingTheme.value = id
  try {
    const resp = await fetch(`/api/themes/${id}/full`)
    if (!resp.ok) throw new Error('Failed to load theme')
    const data = await resp.json()
    const cfg = data.config || {}
    const colors = cfg.colors || {}
    themeForm.name = cfg.name || id
    themeForm.primary = colors.primary || '#7c5cfc'
    themeForm.bg_primary = colors['bg-primary'] || '#0f0f1a'
    themeForm.bg_secondary = colors['bg-secondary'] || '#1a1a2e'
    themeForm.text_primary = colors['text-primary'] || '#e8e8f0'
    themeForm.text_secondary = colors['text-secondary'] || '#8888aa'
    themeForm.border = colors.border || '#2a2a40'
    themeForm.font = cfg.font || 'Noto Sans SC'
  } catch {
    editMsg.value = '加载主题失败'
  }
}

async function saveEditTheme() {
  if (!themeForm.name) { editMsg.value = '请输入主题名称'; return }
  editMsg.value = ''
  const body = {
    id: editingTheme.value,
    name: themeForm.name,
    primary: themeForm.primary,
    bg_primary: themeForm.bg_primary,
    bg_secondary: themeForm.bg_secondary,
    text_primary: themeForm.text_primary,
    text_secondary: themeForm.text_secondary,
    border: themeForm.border,
    font: themeForm.font,
  }
  const resp = await fetch(`/api/themes/${editingTheme.value}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (resp.ok) {
    editMsg.value = '保存成功！'
    editingTheme.value = null
    await themeStore.fetchThemes()
    if (themeStore.current === body.id) {
      await themeStore.applyTheme(body.id)
    }
  } else {
    const err = await resp.json()
    editMsg.value = err.detail || '保存失败'
  }
}

async function resetTheme(id) {
  if (!confirm(`确定要重置主题「${id}」为默认值？`)) return
  if (id === 'default') {
    // Reset default theme to original values
    const body = { id: 'default', ...defaultThemeValues }
    const resp = await fetch('/api/themes/default', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (resp.ok) {
      await themeStore.fetchThemes()
      if (themeStore.current === 'default') {
        await themeStore.applyTheme('default')
      }
    } else {
      const err = await resp.json()
      alert(err.detail || '重置失败')
    }
  } else {
    // Custom theme: delete and reload
    const resp = await fetch(`/api/themes/${id}`, { method: 'DELETE' })
    if (resp.ok) {
      if (editingTheme.value === id) editingTheme.value = null
      await themeStore.fetchThemes()
    } else {
      const err = await resp.json()
      alert(err.detail || '重置失败')
    }
  }
}

async function deleteTheme(id) {
  if (!confirm(`确定要删除主题 "${id}" 吗？`)) return
  const resp = await fetch(`/api/themes/${id}`, { method: 'DELETE' })
  if (resp.ok) {
    if (editingTheme.value === id) editingTheme.value = null
    await themeStore.fetchThemes()
  } else {
    const err = await resp.json()
    alert(err.detail || '删除失败')
  }
}
</script>

<style scoped>
.theme-switcher { margin-bottom: 24px; }
.theme-switcher h3 { font-size: 16px; margin-bottom: 12px; color: var(--text-primary); }
.theme-list { display: flex; gap: 12px; flex-wrap: wrap; }
.theme-card {
  position: relative;
  display: flex; align-items: center; gap: 8px;
  padding: 10px 16px; border-radius: 10px;
  border: 1px solid var(--border); cursor: pointer; transition: all 0.2s;
}
.theme-card:hover { border-color: var(--primary); }
.theme-card.active { background: var(--primary); border-color: var(--primary); }
.theme-dot { width: 16px; height: 16px; border-radius: 50%; }
.card-actions {
  display: none;
  position: absolute; top: -8px; right: -8px;
  display: flex; gap: 3px;
}
.edit-btn, .reset-btn, .delete-btn {
  display: none;
  width: 20px; height: 20px; border-radius: 50%;
  color: white; border: none;
  font-size: 12px; line-height: 20px; text-align: center;
  cursor: pointer; padding: 0;
}
.edit-btn { background: var(--primary); }
.edit-btn:hover { background: #6a4fe0; }
.reset-btn { background: #f39c12; }
.reset-btn:hover { background: #e67e22; }
.delete-btn { background: #e74c3c; }
.delete-btn:hover { background: #c0392b; }
.theme-card:hover .edit-btn,
.theme-card:hover .reset-btn,
.theme-card:hover .delete-btn { display: block; }
.card-actions { position: absolute; top: -8px; right: -8px; gap: 3px; }

/* Inline theme editor */
.theme-editor-inline {
  background: var(--bg-secondary, #1a1a2e);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
  margin-top: 16px;
}
.theme-editor-inline h3 {
  font-size: 15px;
  margin-bottom: 14px;
  color: var(--text-primary);
}
.form-row { margin-bottom: 10px; }
.form-row label { display: block; font-size: 13px; color: var(--text-secondary); margin-bottom: 4px; }
.form-row input {
  width: 100%; padding: 8px; border: 1px solid var(--border); border-radius: 6px;
  background: var(--bg-primary); color: var(--text-primary); font-size: 13px;
}
.color-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin: 12px 0; }
.color-item label { font-size: 12px; color: var(--text-secondary); }
.color-input { display: flex; align-items: center; gap: 6px; }
.color-input input[type="color"] { width: 32px; height: 32px; border: none; cursor: pointer; }
.color-input span { font-size: 11px; color: var(--text-secondary); }
.btn-row { display: flex; gap: 10px; margin-top: 12px; }
.btn-save {
  padding: 8px 20px; background: var(--primary); color: white; border: none;
  border-radius: 6px; cursor: pointer; font-size: 13px;
}
.btn-cancel {
  padding: 8px 20px; background: transparent; color: var(--text-secondary);
  border: 1px solid var(--border); border-radius: 6px; cursor: pointer; font-size: 13px;
}
.btn-cancel:hover { border-color: var(--primary); }
.msg { margin-top: 8px; font-size: 13px; color: var(--primary); }
</style>
