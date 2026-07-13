<template>
  <div class="session-panel">
    <div class="session-header">
      <span>对话</span>
      <button @click="showNewDialog = true" class="new-btn">+</button>
    </div>

    <div class="session-items">
      <template v-for="(group, persona) in groupedSessions" :key="persona">
        <div class="group-header" @click="toggleGroup(persona)">
          <span class="group-arrow">{{ collapsedGroups[persona] ? '▶' : '▼' }}</span>
          <span class="group-name">{{ personaName(persona) }}</span>
          <span class="group-count">{{ group.length }}</span>
        </div>
        <div v-show="!collapsedGroups[persona]">
          <div
            v-for="s in group"
            :key="s.id"
            class="session-item"
            :class="{ active: sessionStore.currentSessionId === s.id }"
            @click="handleSwitch(s.id)"
          >
            <template v-if="renamingId === s.id">
              <input
                v-model="newName"
                @keydown.enter="confirmRename(s.id)"
                @keydown.escape="renamingId = ''"
                @blur="confirmRename(s.id)"
                class="rename-input"
                autofocus
              />
            </template>
            <template v-else>
              <div class="session-name">{{ s.id }}</div>
              <div class="session-meta">{{ s.msg_count }}条</div>
              <div class="session-actions">
                <button class="action-btn" @click.stop="startRename(s.id)" title="重命名">✏️</button>
                <button class="action-btn delete" @click.stop="handleDelete(s.id)" title="删除">×</button>
              </div>
            </template>
          </div>
        </div>
      </template>
      <div v-if="Object.keys(groupedSessions).length === 0" class="empty">暂无对话</div>
    </div>

    <!-- 新建对话弹窗 -->
    <div v-if="showNewDialog" class="modal-overlay" @click.self="showNewDialog = false">
      <div class="modal">
        <div class="modal-title">新建对话</div>

        <div class="modal-section">
          <div class="modal-label">选择角色</div>
          <div class="modal-grid">
            <div
              v-for="p in personaStore.personas"
              :key="p.id"
              class="modal-card"
              :class="{ selected: newPersona === p.id }"
              @click="newPersona = p.id"
            >
              <div class="card-name">{{ p.name }}</div>
              <div class="card-desc">{{ p.description }}</div>
            </div>
          </div>
        </div>

        <div class="modal-section">
          <div class="modal-label">选择主题</div>
          <div class="modal-grid theme-grid">
            <div
              v-for="t in themeStore.themes"
              :key="t.id"
              class="modal-card theme-mini"
              :class="{ selected: newTheme === t.id }"
              @click="newTheme = t.id"
            >
              <div class="theme-dot" :style="{ background: previewColors[t.id] || '#888' }"></div>
              <span>{{ t.name }}</span>
            </div>
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn-cancel" @click="showNewDialog = false">取消</button>
          <button class="btn-create" @click="createWithSelection">创建</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useSessionStore } from '../stores/session'
import { useChatStore } from '../stores/chat'
import { usePersonaStore } from '../stores/persona'
import { useThemeStore } from '../stores/theme'

const sessionStore = useSessionStore()
const chatStore = useChatStore()
const personaStore = usePersonaStore()
const themeStore = useThemeStore()

const renamingId = ref('')
const newName = ref('')
const showNewDialog = ref(false)
const newPersona = ref('default')
const newTheme = ref('default')
const collapsedGroups = reactive({})

const previewColors = { default: '#7c5cfc', miku: '#39C5BB' }

const groupedSessions = computed(() => {
  const groups = {}
  for (const s of sessionStore.sessions) {
    const p = s.persona || 'default'
    if (!groups[p]) groups[p] = []
    groups[p].push(s)
  }
  return groups
})

function personaName(id) {
  const p = personaStore.personas.find(p => p.id === id)
  return p ? p.name : id
}

function toggleGroup(persona) {
  collapsedGroups[persona] = !collapsedGroups[persona]
}

onMounted(() => {
  sessionStore.fetchSessions()
  personaStore.fetchPersonas()
  themeStore.fetchThemes()
})

async function createWithSelection() {
  showNewDialog.value = false
  personaStore.switchPersona(newPersona.value)
  if (newTheme.value !== themeStore.current) {
    await themeStore.applyTheme(newTheme.value)
  }
  await sessionStore.createSession()
  chatStore.clearMessages()
  newPersona.value = 'default'
  newTheme.value = 'default'
}

async function handleSwitch(id) {
  sessionStore.switchSession(id)
  const resp = await fetch(`/api/sessions/${id}/history`)
  const history = await resp.json()
  chatStore.clearMessages()
  for (const msg of history) {
    if (msg.role === 'user') chatStore.addUserMessage(msg.content)
    else if (msg.role === 'assistant') chatStore.messages.push({ role: 'assistant', content: msg.content, streaming: false })
  }
}

async function handleDelete(id) {
  if (confirm('确定删除？')) {
    await sessionStore.deleteSession(id)
    if (sessionStore.currentSessionId === id) chatStore.clearMessages()
  }
}

function startRename(id) {
  renamingId.value = id
  newName.value = id
}

async function confirmRename(id) {
  const name = newName.value.trim()
  if (!name || name === id) { renamingId.value = ''; return }
  try {
    await fetch(`/api/sessions/${id}/rename`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) })
    await sessionStore.fetchSessions()
  } catch (e) { console.error(e) }
  renamingId.value = ''
}
</script>

<style scoped>
.session-panel {
  width: 220px;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  height: calc(100vh - 52px);
}
.session-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  border-bottom: 1px solid var(--border);
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.new-btn {
  width: 28px; height: 28px;
  background: var(--primary); color: white;
  border: none; border-radius: 6px;
  cursor: pointer; font-size: 16px;
  display: flex; align-items: center; justify-content: center;
}
.session-items { flex: 1; overflow-y: auto; }

/* 分组标题 */
.group-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px 6px;
  cursor: pointer;
  user-select: none;
}
.group-arrow {
  font-size: 10px;
  color: var(--primary);
  width: 12px;
}
.group-name {
  font-size: 12px;
  font-weight: 700;
  color: var(--primary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.group-count {
  font-size: 10px;
  color: var(--text-secondary);
  background: rgba(124, 92, 252, 0.15);
  padding: 1px 6px;
  border-radius: 8px;
}

/* 会话项 */
.session-item {
  padding: 8px 12px 8px 28px;
  cursor: pointer;
  position: relative;
  transition: background 0.15s;
}
.session-item:hover { background: rgba(255,255,255,0.03); }
.session-item.active {
  background: rgba(124, 92, 252, 0.1);
  border-left: 3px solid var(--primary);
}
.session-name {
  font-size: 13px; color: var(--text-primary);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  padding-right: 40px;
}
.session-meta { font-size: 10px; color: var(--text-secondary); margin-top: 1px; }
.session-actions {
  position: absolute; right: 6px; top: 50%; transform: translateY(-50%);
  display: flex; gap: 2px; opacity: 0; transition: opacity 0.15s;
}
.session-item:hover .session-actions { opacity: 1; }
.action-btn {
  background: none; border: none; cursor: pointer; font-size: 13px;
  padding: 2px; color: var(--text-secondary);
}
.action-btn:hover { color: var(--primary); }
.action-btn.delete:hover { color: #ff4757; }
.rename-input {
  width: 100%; font-size: 13px; color: var(--text-primary);
  background: var(--bg-primary); border: 1px solid var(--primary);
  border-radius: 4px; padding: 4px 6px; outline: none;
}
.empty { padding: 20px; text-align: center; color: var(--text-secondary); font-size: 13px; }

/* 新建对话弹窗 */
.modal-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.6); z-index: 100;
  display: flex; align-items: center; justify-content: center;
}
.modal {
  background: var(--bg-secondary); border: 1px solid var(--border);
  border-radius: 12px; padding: 20px; width: 380px; max-height: 80vh;
  overflow-y: auto;
}
.modal-title {
  font-size: 16px; font-weight: 700; color: var(--text-primary);
  margin-bottom: 16px; text-align: center;
}
.modal-section { margin-bottom: 16px; }
.modal-label { font-size: 12px; color: var(--text-secondary); margin-bottom: 8px; }
.modal-grid { display: flex; flex-direction: column; gap: 6px; }
.modal-card {
  padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px;
  cursor: pointer; transition: all 0.15s;
}
.modal-card:hover { border-color: var(--primary); }
.modal-card.selected { background: var(--primary); border-color: var(--primary); }
.modal-card.selected .card-desc { color: rgba(255,255,255,0.7); }
.card-name { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.card-desc { font-size: 11px; color: var(--text-secondary); margin-top: 1px; }
.theme-grid { flex-direction: row; flex-wrap: wrap; gap: 8px; }
.theme-mini {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 12px; min-width: auto;
}
.theme-dot { width: 12px; height: 12px; border-radius: 50%; }
.modal-actions { display: flex; gap: 10px; margin-top: 16px; }
.btn-cancel {
  flex: 1; padding: 8px; background: transparent;
  border: 1px solid var(--border); border-radius: 6px;
  color: var(--text-secondary); cursor: pointer; font-size: 13px;
}
.btn-cancel:hover { border-color: var(--primary); color: var(--text-primary); }
.btn-create {
  flex: 1; padding: 8px; background: var(--primary);
  border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 13px;
}
</style>
