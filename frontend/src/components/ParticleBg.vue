<template>
  <canvas ref="canvasRef" class="particle-bg"></canvas>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const canvasRef = ref(null)
let animationId = null
let particles = []

const props = defineProps({
  color: {
    type: String,
    default: '#7c5cfc'
  },
  count: {
    type: Number,
    default: 50
  },
  speed: {
    type: Number,
    default: 0.5
  }
})

class Particle {
  constructor(canvas, color) {
    this.canvas = canvas
    this.color = color
    this.reset()
  }

  reset() {
    this.x = Math.random() * this.canvas.width
    this.y = Math.random() * this.canvas.height
    this.size = Math.random() * 2 + 0.5
    this.speedX = (Math.random() - 0.5) * props.speed
    this.speedY = (Math.random() - 0.5) * props.speed
    this.opacity = Math.random() * 0.5 + 0.1
    this.fadeSpeed = Math.random() * 0.005 + 0.002
    this.growing = Math.random() > 0.5
  }

  update() {
    this.x += this.speedX
    this.y += this.speedY

    // 透明度渐变
    if (this.growing) {
      this.opacity += this.fadeSpeed
      if (this.opacity >= 0.6) this.growing = false
    } else {
      this.opacity -= this.fadeSpeed
      if (this.opacity <= 0.1) this.growing = true
    }

    // 边界检查
    if (this.x < 0 || this.x > this.canvas.width) this.speedX *= -1
    if (this.y < 0 || this.y > this.canvas.height) this.speedY *= -1
  }

  draw(ctx) {
    ctx.beginPath()
    ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2)
    ctx.fillStyle = this.color
    ctx.globalAlpha = this.opacity
    ctx.fill()
    ctx.globalAlpha = 1
  }
}

function initCanvas() {
  const canvas = canvasRef.value
  if (!canvas) return

  const ctx = canvas.getContext('2d')

  // 设置画布大小
  const resize = () => {
    canvas.width = window.innerWidth
    canvas.height = window.innerHeight
  }
  resize()
  window.addEventListener('resize', resize)

  // 创建粒子
  particles = []
  for (let i = 0; i < props.count; i++) {
    particles.push(new Particle(canvas, props.color))
  }

  // 动画循环
  function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // 绘制连接线
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x
        const dy = particles[i].y - particles[j].y
        const dist = Math.sqrt(dx * dx + dy * dy)

        if (dist < 150) {
          ctx.beginPath()
          ctx.strokeStyle = props.color
          ctx.globalAlpha = (1 - dist / 150) * 0.15
          ctx.lineWidth = 0.5
          ctx.moveTo(particles[i].x, particles[i].y)
          ctx.lineTo(particles[j].x, particles[j].y)
          ctx.stroke()
          ctx.globalAlpha = 1
        }
      }
    }

    // 更新和绘制粒子
    particles.forEach(p => {
      p.update()
      p.draw(ctx)
    })

    animationId = requestAnimationFrame(animate)
  }

  animate()
}

onMounted(() => {
  initCanvas()
})

onUnmounted(() => {
  if (animationId) {
    cancelAnimationFrame(animationId)
  }
})
</script>

<style scoped>
.particle-bg {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  pointer-events: none;
  opacity: 0.6;
}
</style>
