<template>
  <div class="bubble-row" :class="msg.role">
    <!-- Agent 头像（左侧） -->
    <div v-if="msg.role === 'assistant'" class="avatar-wrapper">
      <img v-if="agentAvatar" :src="agentAvatar" class="avatar" @error="$event.target.style.display='none'" />
      <div v-else class="avatar avatar-default">🤖</div>
      <img v-if="agentFrame" :src="agentFrame" class="avatar-frame" @error="$event.target.style.display='none'" />
    </div>

    <!-- 气泡 -->
    <div class="bubble" :class="[msg.role, { streaming: msg.streaming }]">
      <div class="bubble-content">{{ msg.content }}</div>
      <div v-if="msg.emoji" class="bubble-emoji">{{ msg.emoji }}</div>
      <!-- 气泡装饰 -->
      <img v-if="decoration" :src="decoration" class="bubble-decoration" :class="msg.role" @error="$event.target.style.display='none'" />
    </div>

    <!-- 用户头像（右侧） -->
    <div v-if="msg.role === 'user'" class="avatar-wrapper">
      <img v-if="userAvatar" :src="userAvatar" class="avatar" @error="$event.target.style.display='none'" />
      <div v-else class="avatar avatar-default">👤</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useThemeStore } from '../stores/theme'

const props = defineProps({ msg: Object })
const themeStore = useThemeStore()

const themeId = computed(() => themeStore.current)

const agentAvatar = computed(() => {
  return `/api/themes/${themeId.value}/assets/avatar.png`
})

const agentFrame = computed(() => {
  return `/api/themes/${themeId.value}/assets/avatar-frame.png`
})

const userAvatar = computed(() => {
  return `/api/themes/${themeId.value}/assets/user-avatar.png`
})

const decoration = computed(() => {
  if (props.msg.role === 'user') {
    return `/api/themes/${themeId.value}/assets/bubble-user.png`
  }
  return `/api/themes/${themeId.value}/assets/bubble-agent.png`
})
</script>

<style scoped>
.bubble-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  margin: 6px 0;
}
.bubble-row.user {
  flex-direction: row-reverse;
}

.avatar-wrapper {
  position: relative;
  width: 36px;
  height: 36px;
  flex-shrink: 0;
}
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  object-fit: cover;
}
.avatar-default {
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-secondary);
  font-size: 18px;
}
.avatar-frame {
  position: absolute;
  top: -4px;
  left: -4px;
  width: 44px;
  height: 44px;
  pointer-events: none;
}

.bubble {
  max-width: 75%;
  padding: var(--bubble-padding);
  border-radius: var(--bubble-radius);
  line-height: var(--line-height);
  white-space: pre-wrap;
  word-break: break-word;
  box-shadow: var(--bubble-shadow);
  border: var(--bubble-border);
  position: relative;
}
.bubble.user {
  background: var(--bubble-user);
  border-bottom-right-radius: 4px;
}
.bubble.assistant {
  background: var(--bubble-agent);
  border-bottom-left-radius: 4px;
}
.bubble.streaming::after {
  content: '▊';
  animation: blink 0.8s infinite;
}

.bubble-emoji {
  font-size: 18px;
  margin-top: 4px;
  text-align: right;
}

.bubble-decoration {
  position: absolute;
  width: 24px;
  height: 24px;
  opacity: 0.8;
  pointer-events: none;
}
.bubble-decoration.user {
  top: -8px;
  right: -8px;
}
.bubble-decoration.assistant {
  bottom: -8px;
  left: -8px;
}

@keyframes blink {
  50% { opacity: 0; }
}
</style>
