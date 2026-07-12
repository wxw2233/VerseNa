<template>
  <div class="persona-switcher">
    <div
      v-for="p in personaStore.personas"
      :key="p.id"
      class="persona-card"
      :class="{ active: personaStore.current === p.id }"
      @click="personaStore.switchPersona(p.id)"
    >
      <div class="persona-name">{{ p.name }}</div>
      <div class="persona-desc">{{ p.description }}</div>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { usePersonaStore } from '../stores/persona'
const personaStore = usePersonaStore()
onMounted(() => personaStore.fetchPersonas())
</script>

<style scoped>
.persona-switcher {
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  overflow-x: auto;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border);
}
.persona-card {
  padding: 8px 14px;
  border-radius: 10px;
  border: 1px solid var(--border);
  cursor: pointer;
  min-width: 100px;
  flex-shrink: 0;
  transition: all 0.2s;
}
.persona-card:hover {
  border-color: var(--primary);
}
.persona-card.active {
  background: var(--primary);
  border-color: var(--primary);
}
.persona-card.active .persona-desc {
  color: rgba(255,255,255,0.8);
}
.persona-name {
  font-size: 14px;
  font-weight: 600;
}
.persona-desc {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
}
</style>
