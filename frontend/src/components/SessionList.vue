<template>
  <div class="session-panel" :style="sidebarBgStyle">
    <div class="session-header">
      <span>对话</span>
      <button @click="handleNew" class="new-btn">+</button>
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
              <div class="session-name">{{ s.name && s.name !== s.id ? s.name : s.id.replace('session_', '').slice(0, 12) }}</div>
              <div class="session-meta">{{ s.msg_count }}条</div>
              <div class="session-actions">
                <button class="action-btn" @click.stop="startEdit(s)" title="编辑">✏️</button>
                <button class="action-btn delete" @click.stop="handleDelete(s.id)" title="删除">×</button>
              </div>
            </template>
          </div>
        </div>
      </template>
      <div v-if="Object.keys(groupedSessions).length === 0" class="empty">暂无对话</div>
    </div>

    <!-- 新建会话：选择主题包 -->
    <div v-if="showNewDialog" class="modal-overlay" @click.self="showNewDialog = false">
      <div class="modal">
        <div class="modal-title">选择主题包</div>
        <div class="pack-list">
          <div v-for="pack in themepacks" :key="pack.id" class="pack-card" @click="createWithPack(pack.id)">
            <div class="pack-name">{{ pack.name }}</div>
            <div class="pack-info">角色: {{ pack.persona_ref || '默认' }} | 主题: {{ pack.theme_ref || '默认' }}</div>
          </div>
        </div>
        <button class="btn-cancel" @click="showNewDialog = false">取消</button>
      </div>
    </div>

    <!-- 编辑会话：重命名 + 更改主题包 -->
    <div v-if="showEditDialog" class="modal-overlay" @click.self="showEditDialog = false">
      <div class="modal">
        <div class="modal-title">编辑会话</div>
        <div class="edit-field">
          <label>会话名称</label>
          <input v-model="editName" class="rename-input" placeholder="会话名称" />
        </div>
        <div class="edit-field">
          <label>主题包</label>
          <select v-model="editPackId" class="pack-select">
            <option value="">无主题包</option>
            <option v-for="pack in themepacks" :key="pack.id" :value="pack.id">{{ pack.name }}</option>
          </select>
        </div>
        <div class="modal-actions">
          <button class="btn-cancel" @click="showEditDialog = false">取消</button>
          <button class="btn-save" @click="saveEdit">保存</button>
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

const themeId = computed(() => themeStore.current)

const sidebarBgStyle = computed(() => {
  return {
    backgroundImage: `url(/api/themes/${themeId.value}/assets/sidebar-bg.png)`,
    backgroundSize: 'cover',
    backgroundPosition: 'center',
  }
})

const renamingId = ref('')
const newName = ref('')
const collapsedGroups = reactive({})
const showNewDialog = ref(false)
const showEditDialog = ref(false)
const themepacks = ref([])
const editSessionId = ref('')
const editName = ref('')
const editPackId = ref('')

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

async function fetchThemepacks() {
  try {
    const resp = await fetch('/api/themepacks')
    if (resp.ok) {
      themepacks.value = await resp.json()
    }
  } catch (e) {
    console.error('Failed to fetch themepacks:', e)
  }
}

function handleNew() {
  fetchThemepacks()
  showNewDialog.value = true
}

async function createWithPack(packId) {
  showNewDialog.value = false

  // 获取主题包详情
  const packResp = await fetch(`/api/themepacks/${packId}`)
  const pack = await packResp.json()

  // 应用主题和角色
  if (pack.theme_ref) themeStore.applyTheme(pack.theme_ref)
  if (pack.persona_ref) personaStore.switchPersona(pack.persona_ref)

  // 创建会话（传入 theme_pack_id）
  const resp = await fetch('/api/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ theme_pack_id: packId })
  })
  const data = await resp.json()
  sessionStore.switchSession(data.session_id)

  // 设置元数据
  await fetch(`/api/sessions/${data.session_id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ theme_pack_id: packId })
  })

  chatStore.clearMessages()
  await sessionStore.fetchSessions()
}

onMounted(() => {
  sessionStore.fetchSessions()
  personaStore.fetchPersonas()
  themeStore.fetchThemes()
  fetchThemepacks()
})

async function handleSwitch(id) {
  sessionStore.switchSession(id)

  // 获取会话元数据
  const sessions = sessionStore.sessions
  const session = sessions.find(s => s.id === id)

  // 如果有绑定的主题包，应用它
  if (session && session.theme_pack_id && session.theme_pack_id !== 'default_pack') {
    const packResp = await fetch(`/api/themepacks/${session.theme_pack_id}`)
    if (packResp.ok) {
      const pack = await packResp.json()
      if (pack.theme_ref) themeStore.applyTheme(pack.theme_ref)
      if (pack.persona_ref) personaStore.switchPersona(pack.persona_ref)
    }
  }

  // 加载历史
  const resp = await fetch(`/api/sessions/${id}/history`)
  const history = await resp.json()
  chatStore.clearMessages()
  for (const msg of history) {
    if (msg.role === 'user') chatStore.addUserMessage(msg.content)
    else if (msg.role === 'assistant') {
      const m = { role: 'assistant', streaming: false }
      if (msg.segments && msg.segments.length > 0) {
        // 把 content 文本作为第一个 text 段加在前面
        if (msg.content && msg.segments.every(s => s.type !== 'text')) {
          m.segments = [...msg.segments, { type: 'text', content: msg.content }]
        } else {
          m.segments = msg.segments
        }
        m.version = msg.version || 2
        m.expandedTools = {}
      } else {
        m.content = msg.content || ''
      }
      if (msg.emoji) m.emoji = msg.emoji
      chatStore.messages.push(m)
    }
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

function startEdit(session) {
  editSessionId.value = session.id
  editName.value = session.id
  editPackId.value = session.theme_pack_id || ''
  fetchThemepacks()
  showEditDialog.value = true
}

async function saveEdit() {
  const id = editSessionId.value
  const name = editName.value.trim()
  try {
    await fetch(`/api/sessions/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name || undefined,
        theme_pack_id: editPackId.value || null
      })
    })
    await sessionStore.fetchSessions()
  } catch (e) { console.error(e) }
  showEditDialog.value = false
}
</script>

<style scoped>
/* L1: Sidebar — 12px blur, 0.75 opacity, inner glow, no hard right border */
.session-panel {
  width: var(--sidebar-width, 220px);
  background: transparent;
   

  box-shadow: none;
  display: flex;
  flex-direction: column;
  height: calc(100vh - 52px);
  position: relative;
  z-index: 2;
}
.session-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 12px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.new-btn {
  width: 28px; height: 28px;
  background: var(--primary); color: white;
  border: none; border-radius: 8px;
  cursor: pointer; font-size: 16px;
  display: flex; align-items: center; justify-content: center;
  transition: filter 0.2s, transform 0.2s;
}
.new-btn:hover {
  filter: brightness(1.08);
  transform: translateY(-1px);
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

/* 会话项 — subtle hover, no hard border */
.session-item {
  padding: 8px 12px 8px 24px;
  cursor: pointer;
  border: 1px solid rgba(255,255,255,0.10);
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
  position: relative;
  transition: background 0.15s, transform 0.15s;
}
.session-item:hover {
  background: rgba(255, 255, 255, 0.03);
}
/* Selected session: left border indicator */
.session-item.active {
  background: rgba(124, 92, 252, 0.12);
  border-left: 3px solid rgba(100,180,255,0.7);
  border: 1px solid rgba(255,255,255,0.10);
  border-radius: 0 8px 8px 0;
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
  background: var(--panel-l4);
  box-shadow: 0 0 0 1px var(--primary);
  border: none;
  border-radius: 4px; padding: 4px 6px; outline: none;
}
.empty { padding: 20px; text-align: center; color: var(--text-secondary); font-size: 13px; }

/* 弹窗 — L3 glass style */
.modal-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.5);
   

  display: flex;
  align-items: center; justify-content: center; z-index: 100;
}
.modal {
  background: var(--panel-l3);
   

  box-shadow: var(--border-subtle), var(--glow-inner);
  border-radius: var(--radius);
  padding: 20px; width: 340px; max-height: 70vh; overflow-y: auto;
}
.modal-title {
  font-size: 16px; font-weight: 600; color: var(--text-primary);
  margin-bottom: 16px; text-align: center;
}
.pack-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
/* Pack cards in modal: L3 style */
.pack-card {
  background: var(--panel-l3);
  box-shadow: var(--border-subtle);
  border-radius: var(--radius);
  padding: 12px; cursor: pointer;
  transition: filter 0.2s, transform 0.2s, box-shadow 0.2s;
}
.pack-card:hover {
  box-shadow: 0 0 0 1px var(--primary);
  filter: brightness(1.05);
  transform: translateY(-1px);
}
.pack-name { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.pack-info { font-size: 11px; color: var(--text-secondary); margin-top: 4px; }
.btn-cancel, .btn-save {
  padding: 6px 16px; border-radius: var(--radius-sm); cursor: pointer;
  font-size: 13px; border: none;
  transition: filter 0.2s, transform 0.2s;
}
.btn-cancel {
  background: var(--panel-l4);
  color: var(--text-secondary);
  box-shadow: var(--border-subtle);
}
.btn-save {
  background: var(--primary); color: white;
}
.btn-cancel:hover, .btn-save:hover {
  filter: brightness(1.08);
  transform: translateY(-1px);
}
.edit-field { margin-bottom: 12px; }
.edit-field label {
  display: block; font-size: 12px; color: var(--text-secondary);
  margin-bottom: 4px;
}
.pack-select {
  width: 100%; font-size: 13px; color: var(--text-primary);
  background: var(--panel-l4);
  box-shadow: var(--border-subtle);
  border: none;
  border-radius: 4px; padding: 6px 8px; outline: none;
}
.pack-select:focus {
  box-shadow: 0 0 0 1px var(--primary);
}
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
</style>
