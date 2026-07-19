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
  top: 12px;
  right: 12px;
  z-index: 99999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}

.toast-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  border-radius: 10px;
  font-size: 13px;
  color: #fff;
  backdrop-filter: blur(12px);
  pointer-events: auto;
  cursor: pointer;
  max-width: 340px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.3);
  transition: all 0.3s ease;
}

.toast-item.success { background: rgba(34,197,94,0.85); }
.toast-item.error { background: rgba(239,68,68,0.85); }
.toast-item.warning { background: rgba(234,179,8,0.85); }
.toast-item.info { background: rgba(59,130,246,0.85); }

.toast-icon {
  font-size: 15px;
  font-weight: 700;
  flex-shrink: 0;
}

.toast-msg {
  line-height: 1.4;
  word-break: break-word;
}

/* Transitions */
.toast-enter-active { transition: all 0.3s ease; }
.toast-leave-active { transition: all 0.3s ease; }
.toast-enter-from { opacity: 0; transform: translateX(40px); }
.toast-leave-to { opacity: 0; transform: translateX(40px); }
.toast-move { transition: transform 0.3s ease; }
</style>
