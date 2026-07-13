<template>
  <div class="session-panel">
    <div class="session-header">
      <span>对话列表</span>
      <button @click="handleNew" class="new-btn">+ 新对话</button>
    </div>
    <div class="session-items">
      <div
        v-for="s in sessionStore.sessions"
        :key="s.id"
        class="session-item"
        :class="{ active: sessionStore.currentSessionId === s.id }"
        @click="handleSwitch(s.id)"
      >
        <div class="session-name">{{ s.id }}</div>
        <div class="session-meta">{{ s.msg_count }} 条消息</div>
        <button class="delete-btn" @click.stop="handleDelete(s.id)" title="删除">×</button>
      </div>
      <div v-if="sessionStore.sessions.length === 0" class="empty">暂无对话</div>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useSessionStore } from '../stores/session'
import { useChatStore } from '../stores/chat'

const sessionStore = useSessionStore()
const chatStore = useChatStore()

onMounted(() => sessionStore.fetchSessions())

async function handleNew() {
  await sessionStore.createSession()
  chatStore.clearMessages()
}

async function handleSwitch(id) {
  sessionStore.switchSession(id)
  // 加载该会话的历史
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
.delete-btn {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 16px;
  opacity: 0;
  transition: opacity 0.2s;
}
.session-item:hover .delete-btn {
  opacity: 1;
}
.delete-btn:hover {
  color: #ff4757;
}
.empty {
  padding: 20px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 13px;
}
</style>
