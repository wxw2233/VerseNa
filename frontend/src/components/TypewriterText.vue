<template>
  <span class="typewriter" :class="{ typing: isTyping }">
    <span class="typewriter-text">{{ displayedText }}</span>
    <span v-if="isTyping" class="typewriter-cursor">|</span>
  </span>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  text: {
    type: String,
    required: true
  },
  speed: {
    type: Number,
    default: 30
  },
  delay: {
    type: Number,
    default: 0
  },
  enableSound: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['complete'])

const displayedText = ref('')
const isTyping = ref(false)
let timeoutId = null
let currentIndex = 0

// 打字音效（使用 AudioContext 生成）
let audioContext = null

function playTickSound() {
  if (!props.enableSound) return

  try {
    if (!audioContext) {
      audioContext = new (window.AudioContext || window.webkitAudioContext)()
    }

    const oscillator = audioContext.createOscillator()
    const gainNode = audioContext.createGain()

    oscillator.connect(gainNode)
    gainNode.connect(audioContext.destination)

    oscillator.frequency.value = 800 + Math.random() * 400
    oscillator.type = 'sine'

    gainNode.gain.value = 0.02
    gainNode.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + 0.05)

    oscillator.start(audioContext.currentTime)
    oscillator.stop(audioContext.currentTime + 0.05)
  } catch (e) {
    // 静默失败
  }
}

function typeNextChar() {
  if (currentIndex < props.text.length) {
    displayedText.value += props.text[currentIndex]
    currentIndex++

    // 随机速度变化，更自然
    const variance = Math.random() * 20 - 10
    const nextSpeed = Math.max(10, props.speed + variance)

    // 标点符号后稍微停顿
    const char = props.text[currentIndex - 1]
    const pauseChars = ['.', '。', '!', '！', '?', '？', ',', '，', ';', '；']
    const pause = pauseChars.includes(char) ? 200 : 0

    playTickSound()

    timeoutId = setTimeout(typeNextChar, nextSpeed + pause)
  } else {
    isTyping.value = false
    emit('complete')
  }
}

function startTyping() {
  stopTyping()
  displayedText.value = ''
  currentIndex = 0
  isTyping.value = true

  timeoutId = setTimeout(typeNextChar, props.delay)
}

function stopTyping() {
  if (timeoutId) {
    clearTimeout(timeoutId)
    timeoutId = null
  }
  isTyping.value = false
}

function skipToEnd() {
  stopTyping()
  displayedText.value = props.text
  emit('complete')
}

watch(() => props.text, (newText) => {
  if (newText) {
    startTyping()
  }
}, { immediate: true })

onUnmounted(() => {
  stopTyping()
  if (audioContext) {
    audioContext.close()
  }
})

defineExpose({ startTyping, stopTyping, skipToEnd })
</script>

<style scoped>
.typewriter {
  display: inline;
}

.typewriter-cursor {
  display: inline-block;
  color: var(--primary);
  animation: cursor-blink 0.8s infinite;
  font-weight: 100;
  margin-left: 1px;
}

@keyframes cursor-blink {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}

.typewriter-text {
  white-space: pre-wrap;
}
</style>
