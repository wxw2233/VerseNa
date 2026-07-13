<template>
  <div class="session-panel">
    <div class="session-header">
      <span>对话列表</span>
      <button @click="handleNew" class="new-btn">+ 新对话</button>
    </div>
    <div class="session-items">
      <template v-for="(sessions, persona) in groupedSessions" :key="persona">
        <div class="persona-group-title">{{ persona }}</div>
        <div
          v-for="s in sessions"
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
            <div class="session-meta">{{ s.msg_count }} 条消息</div>
            <div class="session-actions">
              <button class="action-btn rename-btn" @click.stop="startRename(s.id)" title="重命名">✏️</button>
              <button class="action-btn delete-btn" @click.stop="handleDelete(s.id)" title="删除">×</button>
            </div>
          </template>
        </div>
      </template>
      <div v-if="Object.keys(groupedSessions).length === 0" class="empty">暂无对话</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useSessionStore } from '../stores/session'
import { useChatStore } from '../stores/chat'

const sessionStore = useSessionStore()
const chatStore = useChatStore()

const renamingId = ref('')
const newName = ref('')

const groupedSessions = computed(() => {
  const groups = {}
  for (const s of sessionStore.sessions) {
    const p = s.persona || 'default'
    if (!groups[p]) groups[p] = []
    groups[p].push(s)
  }
  return groups
})

onMounted(() => sessionStore.fetchSessions())

async function handleNew() {
  await sessionStore.createSession()
  chatStore.clearMessages()
}

async function handleSwitch(id) {
  sessionStore.switchSession(id)
  const resp = await fetch(`/api/sessions/${id}/history`)
  const history = await resp.json()
  chatStore.clearMessages()
  for (const msg of history) {
    if (msg.role === 'user') {
      chatStore.addUserMessage(msg.content)
    } else if (msg.role === 'assistant') {
      chatStore.messages.push({ role: 'assistant', content: msg.content, streaming: false })
    }
  }
}

async function handleDelete(id) {
  if (confirm('确定删除这个对话吗？')) {
    await sessionStore.deleteSession(id)
    if (sessionStore.currentSessionId === id) {
      chatStore.clearMessages()
    }
  }
}

function startRename(id) {
  renamingId.value = id
  newName.value = id
}

async function confirmRename(id) {
  const name = newName.value.trim()
  if (!name || name === id) {
    renamingId.value = ''
    return
  }
  try {
    await fetch(`/api/sessions/${id}/rename`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    })
    renamingId.value = ''
    sessionStore.fetchSessions()
  } catch (e) {
    console.error('Rename failed:', e)
    renamingId.value = ''
  }
}
</script>

<style scoped>
.session-panel {
  width: 240px;
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
  color: var(--text-primary);
}
.new-btn {
  padding: 4px 10px;
  background: var(--primary);
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
}
.session-items {
  flex: 1;
  overflow-y: auto;
}
.persona-group-title {
  padding: 8px 12px 4px;
  font-size: 11px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}
.session-item {
  padding: 10px 12px;
  cursor: pointer;
  border-bottom: 1px solid var(--border);
  position: relative;
}
.session-item:hover {
  background: rgba(255,255,255,0.03);
}
.session-item.active {
  background: rgba(124, 92, 252, 0.1);
  border-left: 3px solid var(--primary);
}
.session-name {
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 20px;
}
.session-meta {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
}
.rename-input {
  width: 100%;
  font-size: 13px;
  color: var(--text-primary);
  background: var(--bg-primary);
  border: 1px solid var(--primary);
  border-radius: 4px;
  padding: 4px 6px;
  outline: none;
}
.session-actions {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}
.session-item:hover .session-actions {
  opacity: 1;
}
.action-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  padding: 2px;
  line-height: 1;
  color: var(--text-secondary);
}
.action-btn.rename-btn:hover {
  color: var(--primary);
}
.action-btn.delete-btn:hover {
  color: #ff4757;
}
.empty {
  padding: 20px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 13px;
}
</style>
