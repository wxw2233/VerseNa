<template>
  <div
    class="hover-card"
    :class="{ 'hover-card--active': isActive }"
    :style="cardStyle"
    @mousemove="handleMouseMove"
    @mouseleave="handleMouseLeave"
    @mouseenter="handleMouseEnter"
  >
    <div class="hover-card__shine" :style="shineStyle"></div>
    <div class="hover-card__content">
      <slot></slot>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  intensity: {
    type: Number,
    default: 15,
    validator: (val) => val >= 0 && val <= 45
  },
  shine: {
    type: Boolean,
    default: true
  },
  scale: {
    type: Number,
    default: 1.02
  }
})

const isActive = ref(false)
const mouseX = ref(0)
const mouseY = ref(0)
const cardRect = ref(null)

const rotateX = computed(() => {
  if (!isActive.value) return 0
  const centerY = cardRect.value ? cardRect.value.height / 2 : 0
  return ((mouseY.value - centerY) / centerY) * -props.intensity
})

const rotateY = computed(() => {
  if (!isActive.value) return 0
  const centerX = cardRect.value ? cardRect.value.width / 2 : 0
  return ((mouseX.value - centerX) / centerX) * props.intensity
})

const cardStyle = computed(() => ({
  transform: isActive.value
    ? `perspective(1000px) rotateX(${rotateX.value}deg) rotateY(${rotateY.value}deg) scale(${props.scale})`
    : 'perspective(1000px) rotateX(0) rotateY(0) scale(1)'
}))

const shineStyle = computed(() => {
  if (!isActive.value || !props.shine) return { opacity: 0 }

  const x = cardRect.value ? (mouseX.value / cardRect.value.width) * 100 : 50
  const y = cardRect.value ? (mouseY.value / cardRect.value.height) * 100 : 50

  return {
    opacity: 0.15,
    background: `radial-gradient(circle at ${x}% ${y}%, rgba(255, 255, 255, 0.8) 0%, transparent 60%)`
  }
})

function handleMouseEnter(e) {
  isActive.value = true
  cardRect.value = e.currentTarget.getBoundingClientRect()
}

function handleMouseMove(e) {
  if (!cardRect.value) return
  mouseX.value = e.clientX - cardRect.value.left
  mouseY.value = e.clientY - cardRect.value.top
}

function handleMouseLeave() {
  isActive.value = false
  mouseX.value = 0
  mouseY.value = 0
  cardRect.value = null
}
</script>

<style scoped>
.hover-card {
  position: relative;
  border-radius: 16px;
  overflow: hidden;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
  transform-style: preserve-3d;
  will-change: transform;
}

.hover-card--active {
  box-shadow:
    0 20px 60px rgba(0, 0, 0, 0.3),
    0 0 30px rgba(124, 92, 252, 0.1);
}

.hover-card__shine {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 10;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.hover-card__content {
  position: relative;
  z-index: 1;
}
</style>
