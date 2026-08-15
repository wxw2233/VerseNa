<template>
  <Teleport to="body">
    <div class="toast-container">
      <TransitionGroup name="toast">
        <div
          v-for="t in toasts"
          :key="t.id"
          class="toast-item"
          :class="[t.type, { leaving: t.leaving }]"
          @click="dismiss(t.id)"
        >
          <span class="toast-icon">{{ icons[t.type] }}</span>
          <span class="toast-msg">{{ t.message }}</span>
          <div class="toast-progress" :class="t.type"></div>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup>
import { useToast } from '../composables/useToast'
const { toasts, dismiss } = useToast()
const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' }
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 16px;
  left: 50%;
  width: min(420px, calc(100vw - 120px));
  transform: translateX(-50%);
  z-index: 99999;
  display: flex;
  align-items: center;
  flex-direction: column;
  gap: 10px;
  pointer-events: none;
}

.toast-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  border-radius: 12px;
  font-size: 14px;
  color: #fff;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  pointer-events: auto;
  cursor: pointer;
  width: fit-content;
  max-width: 100%;
  box-sizing: border-box;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.toast-item:hover {
  transform: translateX(-4px);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
}

.toast-item.success {
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.9), rgba(22, 163, 74, 0.9));
}

.toast-item.error {
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.9), rgba(220, 38, 38, 0.9));
}

.toast-item.warning {
  background: linear-gradient(135deg, rgba(234, 179, 8, 0.9), rgba(202, 138, 4, 0.9));
}

.toast-item.info {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.9), rgba(37, 99, 235, 0.9));
}

.toast-icon {
  font-size: 18px;
  font-weight: 700;
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
}

.toast-msg {
  line-height: 1.5;
  word-break: break-word;
  flex: 1;
}

.toast-progress {
  position: absolute;
  bottom: 0;
  left: 0;
  height: 3px;
  background: rgba(255, 255, 255, 0.5);
  animation: toast-progress 3s linear forwards;
}

.toast-progress.success { width: 100%; }
.toast-progress.error { width: 100%; }
.toast-progress.warning { width: 100%; }
.toast-progress.info { width: 100%; }

@keyframes toast-progress {
  from { width: 100%; }
  to { width: 0%; }
}

/* Transitions */
.toast-enter-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.toast-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(80px) scale(0.8);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(80px) scale(0.8);
}

.toast-move {
  transition: transform 0.3s ease;
}

@media (max-width: 767px) {
  .toast-container {
    top: 64px;
    width: calc(100vw - 32px);
  }

  .toast-item {
    width: 100%;
  }
}
</style>
