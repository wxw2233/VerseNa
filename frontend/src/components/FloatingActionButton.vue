<template>
  <div class="fab-container">
    <button
      class="fab-main"
      :class="{ active: isOpen }"
      @click="isOpen = !isOpen"
    >
      <span class="fab-icon" :class="{ rotated: isOpen }">{{ isOpen ? '✕' : '⚡' }}</span>
    </button>

    <Transition name="fab">
      <div v-if="isOpen" class="fab-menu">
        <button
          v-for="(action, index) in actions"
          :key="action.id"
          class="fab-item"
          :style="{ '--delay': `${index * 0.05}s` }"
          @click="handleAction(action)"
        >
          <span class="fab-item-icon">{{ action.icon }}</span>
          <span class="fab-item-label">{{ action.label }}</span>
        </button>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  actions: {
    type: Array,
    default: () => [
      { id: 'new', icon: '💬', label: '新对话' },
      { id: 'search', icon: '🔍', label: '搜索' },
      { id: 'settings', icon: '⚙️', label: '设置' }
    ]
  }
})

const emit = defineEmits(['action'])
const isOpen = ref(false)

function handleAction(action) {
  emit('action', action)
  isOpen.value = false
}
</script>

<style scoped>
.fab-container {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 1000;
}

.fab-main {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--primary);
  color: white;
  border: none;
  cursor: pointer;
  font-size: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(124, 92, 252, 0.4);
  transition: all 0.3s ease;
}

.fab-main:hover {
  transform: scale(1.1);
  box-shadow: 0 6px 20px rgba(124, 92, 252, 0.5);
}

.fab-main.active {
  background: #ff4757;
}

.fab-icon {
  transition: transform 0.3s ease;
}

.fab-icon.rotated {
  transform: rotate(90deg);
}

.fab-menu {
  position: absolute;
  bottom: 70px;
  right: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.fab-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(20, 20, 40, 0.9);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  color: var(--text-primary);
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s ease;
  animation: fab-item-in 0.3s ease backwards;
  animation-delay: var(--delay);
}

.fab-item:hover {
  background: rgba(124, 92, 252, 0.2);
  border-color: var(--primary);
  transform: translateX(-4px);
}

.fab-item-icon {
  font-size: 18px;
}

.fab-item-label {
  font-size: 14px;
}

@keyframes fab-item-in {
  from {
    opacity: 0;
    transform: translateX(20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.fab-enter-active,
.fab-leave-active {
  transition: all 0.3s ease;
}

.fab-enter-from,
.fab-leave-to {
  opacity: 0;
  transform: translateY(20px);
}
</style>
