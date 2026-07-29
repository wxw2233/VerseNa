<template>
  <div class="image-msg" ref="containerRef">
    <img
      v-if="shouldLoad"
      :src="src"
      :alt="filename"
      @click="openPreview"
      @load="onLoad"
      @error="onError"
      :class="{ loading: isLoading, error: hasError }"
    />
    <div v-else class="image-placeholder">
      <span class="placeholder-icon">🖼️</span>
    </div>
    <div v-if="isLoading && shouldLoad" class="image-loading">
      <span class="spinner">⏳</span>
    </div>
    <div v-if="hasError" class="image-error">
      <span>❌</span>
      <span>加载失败</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  src: {
    type: String,
    required: true
  },
  filename: {
    type: String,
    default: '图片'
  }
})

const containerRef = ref(null)
const shouldLoad = ref(false)
const isLoading = ref(true)
const hasError = ref(false)
let observer = null

const onLoad = () => {
  isLoading.value = false
  hasError.value = false
}

const onError = () => {
  isLoading.value = false
  hasError.value = true
}

onMounted(() => {
  // 使用 IntersectionObserver 实现懒加载
  if ('IntersectionObserver' in window) {
    observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            shouldLoad.value = true
            observer.unobserve(entry.target)
          }
        })
      },
      { threshold: 0.1, rootMargin: '50px' }
    )

    if (containerRef.value) {
      observer.observe(containerRef.value)
    }
  } else {
    // 降级：直接加载
    shouldLoad.value = true
  }
})

onUnmounted(() => {
  if (observer) {
    observer.disconnect()
  }
})

const openPreview = () => {
  // 打开图片预览
  const modal = document.createElement('div')
  modal.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.9);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
    cursor: pointer;
  `

  const img = document.createElement('img')
  img.src = props.src
  img.style.cssText = `
    max-width: 90%;
    max-height: 90%;
    object-fit: contain;
    border-radius: 8px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
  `

  modal.appendChild(img)
  document.body.appendChild(modal)

  modal.onclick = () => {
    document.body.removeChild(modal)
  }

  // ESC 键关闭
  const handler = (e) => {
    if (e.key === 'Escape') {
      document.body.removeChild(modal)
      document.removeEventListener('keydown', handler)
    }
  }
  document.addEventListener('keydown', handler)
}
</script>

<style scoped>
.image-msg {
  position: relative;
  display: inline-block;
  max-width: 300px;
  max-height: 300px;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  background: rgba(255, 255, 255, 0.05);
}

.image-msg img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: opacity 0.3s, transform 0.3s;
}

.image-msg img:hover {
  transform: scale(1.02);
}

.image-msg img.loading {
  opacity: 0.5;
}

.image-msg img.error {
  opacity: 0.3;
}

.image-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 150px;
  background: rgba(255, 255, 255, 0.05);
}

.placeholder-icon {
  font-size: 32px;
  opacity: 0.5;
}

.image-loading, .image-error {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 12px;
}

.spinner {
  font-size: 24px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 移动端样式 */
@media (max-width: 767px) {
  .image-msg {
    max-width: 250px;
    max-height: 250px;
  }
}
</style>
