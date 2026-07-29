<template>
  <div class="empty-state">
    <Sparkles class="empty-mark" :size="58" :stroke-width="1.6" aria-hidden="true" />
    <h3 class="empty-title gradient-text">{{ title }}</h3>
    <button
      v-if="actionText"
      class="empty-action btn btn-primary"
      @click="$emit('action')"
    >
      <MessageCirclePlus :size="18" aria-hidden="true" />
      <span>{{ actionText }}</span>
    </button>
  </div>
</template>

<script setup>
import { MessageCirclePlus, Sparkles } from 'lucide-vue-next'

defineProps({
  title: {
    type: String,
    default: 'VerseNa'
  },
  actionText: {
    type: String,
    default: ''
  }
})

defineEmits(['action'])
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
  min-height: 320px;
  margin: auto;
  padding: 40px 20px;
  text-align: center;
  animation: empty-enter var(--motion-base) var(--ease-emphasized) both;
}

.empty-mark {
  color: var(--primary);
  filter: drop-shadow(0 4px 16px color-mix(in srgb, var(--primary) 35%, transparent));
  animation: mark-enter var(--motion-slow) var(--ease-emphasized) 60ms both;
}

.empty-title {
  margin: 0;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 0;
}

.empty-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 42px;
  padding: 10px 24px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  transition: transform var(--motion-fast) var(--ease-standard), filter var(--motion-fast) var(--ease-standard), box-shadow var(--motion-fast) var(--ease-standard);
}

.empty-action:hover {
  transform: translateY(-1px);
  filter: brightness(1.08);
  box-shadow: 0 6px 18px color-mix(in srgb, var(--primary) 28%, transparent);
}

@keyframes empty-enter {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes mark-enter {
  from { opacity: 0; transform: translateY(6px) scale(0.92); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

@media (max-width: 767px) {
  .empty-state {
    min-height: 260px;
    padding: 32px 16px;
  }

  .empty-title {
    font-size: 24px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .empty-state,
  .empty-mark {
    animation: none;
  }
}
</style>
