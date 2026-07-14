<template>
  <div class="chat-view">
    <SessionList />
    <div class="chat-main">
      <div class="bg-layer" :style="bgStyle"></div>
      <div class="messages" ref="messagesRef">
        <ChatBubble v-for="(msg, i) in store.messages" :key="i" :msg="msg" />
        <div v-if="store.messages.length === 0" class="empty">
          <p>✨ 次元人格 ✨</p>
          <p class="sub">点击「+ 新对话」开始聊天</p>
        </div>
      </div>
      <ChatInput @send="handleSend" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { useChatStore } from '../stores/chat'
import { useWebSocket } from '../composables/useWebSocket'
import { usePersonaStore } from '../stores/persona'
import { useSessionStore } from '../stores/session'
import { useThemeStore } from '../stores/theme'
import ChatBubble from '../components/ChatBubble.vue'
import ChatInput from '../components/ChatInput.vue'
import SessionList from '../components/SessionList.vue'

const store = useChatStore()
const personaStore = usePersonaStore()
const sessionStore = useSessionStore()
const themeStore = useThemeStore()
const messagesRef = ref(null)
const { connect, send, onMessage } = useWebSocket()

const bgStyle = computed(() => {
  const themeId = themeStore.current
  return {
    backgroundImage: `url(/api/themes/${themeId}/assets/bg.png)`,
    backgroundSize: 'cover',
    backgroundPosition: 'center',
    backgroundRepeat: 'no-repeat',
    opacity: store.bgOpacity ?? 0.3,
  }
})

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

// 消息变化时自动滚到底部
watch(() => store.messages.length, () => scrollToBottom())

// 组件挂载时滚到底部
onMounted(() => {
  connect()
  scrollToBottom()
  onMessage.value = (msg) => {
    if (msg.type === 'answer') {
      store.appendAgentChunk(msg.content)
    } else if (msg.type === 'done') {
      store.finishStreaming()
      if (msg.emoji) {
        const last = store.messages[store.messages.length - 1]
        if (last) last.emoji = msg.emoji
      }
    } else if (msg.type === 'error') {
      store.appendAgentChunk(`\n[错误] ${msg.content}`)
      store.finishStreaming()
    }
    scrollToBottom()
  }
})

function handleSend(content) {
  store.addUserMessage(content)
  store.isStreaming = true
  scrollToBottom()
  send({
    session_id: sessionStore.currentSessionId,
    content,
    persona: personaStore.current,
    system_prompt: ''
  })
}
</script>

<style scoped>
.chat-view {
  display: flex;
  height: calc(100vh - 52px);
}
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
  overflow: hidden;
}
.bg-layer {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  z-index: 0;
  pointer-events: none;
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 1;
}
.empty {
  margin: auto;
  text-align: center;
  color: var(--text-secondary);
}
.empty p { font-size: 24px; }
.empty .sub { font-size: 14px; margin-top: 8px; }
</style>
