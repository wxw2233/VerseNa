<template>
  <div
    class="glow-cursor"
    :style="cursorStyle"
    v-if="isVisible"
  ></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  color: {
    type: String,
    default: '#7c5cfc'
  },
  size: {
    type: Number,
    default: 200
  }
})

const cursorStyle = ref({})
const isVisible = ref(false)

let animationId = null
let mouseX = 0
let mouseY = 0
let currentX = 0
let currentY = 0

function handleMouseMove(e) {
  mouseX = e.clientX
  mouseY = e.clientY
  isVisible.value = true
}

function handleMouseLeave() {
  isVisible.value = false
}

function animate() {
  // 平滑跟随
  currentX += (mouseX - currentX) * 0.1
  currentY += (mouseY - currentY) * 0.1

  cursorStyle.value = {
    left: `${currentX}px`,
    top: `${currentY}px`,
    width: `${props.size}px`,
    height: `${props.size}px`,
    background: `radial-gradient(circle, ${props.color}33 0%, transparent 70%)`,
    transform: 'translate(-50%, -50%)'
  }

  animationId = requestAnimationFrame(animate)
}

onMounted(() => {
  document.addEventListener('mousemove', handleMouseMove)
  document.addEventListener('mouseleave', handleMouseLeave)
  animate()
})

onUnmounted(() => {
  document.removeEventListener('mousemove', handleMouseMove)
  document.removeEventListener('mouseleave', handleMouseLeave)
  if (animationId) {
    cancelAnimationFrame(animationId)
  }
})
</script>

<style scoped>
.glow-cursor {
  position: fixed;
  pointer-events: none;
  z-index: 9998;
  border-radius: 50%;
  mix-blend-mode: screen;
  transition: opacity 0.3s;
}
</style>
