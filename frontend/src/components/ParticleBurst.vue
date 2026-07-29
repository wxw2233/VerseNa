<template>
  <div class="particle-burst-container" v-if="active">
    <div
      v-for="particle in particles"
      :key="particle.id"
      class="particle"
      :style="particle.style"
    ></div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  trigger: {
    type: Boolean,
    default: false
  },
  color: {
    type: String,
    default: '#7c5cfc'
  },
  count: {
    type: Number,
    default: 12
  }
})

const active = ref(false)
const particles = ref([])

function createParticles() {
  const newParticles = []
  for (let i = 0; i < props.count; i++) {
    const angle = (360 / props.count) * i
    const velocity = 50 + Math.random() * 50
    const size = 4 + Math.random() * 6
    const duration = 0.6 + Math.random() * 0.4
    const delay = Math.random() * 0.1

    newParticles.push({
      id: i,
      style: {
        '--angle': `${angle}deg`,
        '--velocity': `${velocity}px`,
        '--size': `${size}px`,
        '--duration': `${duration}s`,
        '--delay': `${delay}s`,
        '--color': props.color,
        width: `${size}px`,
        height: `${size}px`,
        background: props.color,
        borderRadius: '50%',
        position: 'absolute',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        animation: `particle-fly ${duration}s ease-out ${delay}s forwards`
      }
    })
  }
  particles.value = newParticles
}

watch(() => props.trigger, (newVal) => {
  if (newVal) {
    active.value = true
    createParticles()
    setTimeout(() => {
      active.value = false
      particles.value = []
    }, 1000)
  }
})
</script>

<style scoped>
.particle-burst-container {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 9999;
}

@keyframes particle-fly {
  0% {
    transform: translate(-50%, -50%) scale(1);
    opacity: 1;
  }
  100% {
    transform: translate(
      calc(-50% + cos(var(--angle)) * var(--velocity)),
      calc(-50% + sin(var(--angle)) * var(--velocity))
    ) scale(0);
    opacity: 0;
  }
}
</style>
