<template>
  <div class="persona-switcher">
    <div class="switcher-header" @click="collapsed = !collapsed">
      <span class="current-name">{{ currentPersona?.name || '选择角色' }}</span>
      <span class="toggle-arrow">{{ collapsed ? '▼' : '▲' }}</span>
    </div>
    <div v-show="!collapsed" class="persona-list">
      <div
        v-for="p in personaStore.personas"
        :key="p.id"
        class="persona-card"
        :class="{ active: personaStore.current === p.id }"
        @click="selectPersona(p.id)"
      >
        <div class="persona-name">{{ p.name }}</div>
        <div class="persona-desc">{{ p.description }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { usePersonaStore } from '../stores/persona'
const personaStore = usePersonaStore()
const collapsed = ref(true)

const currentPersona = computed(() =>
  personaStore.personas.find(p => p.id === personaStore.current)
)

function selectPersona(id) {
  personaStore.switchPersona(id)
  collapsed.value = true
}

onMounted(() => personaStore.fetchPersonas())
</script>

<style scoped>
.persona-switcher {
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border);
}
.switcher-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  cursor: pointer;
  user-select: none;
}
.switcher-header:hover {
  background: rgba(255,255,255,0.02);
}
.current-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--primary);
}
.toggle-arrow {
  font-size: 10px;
  color: var(--text-secondary);
}
.persona-list {
  display: flex;
  gap: 8px;
  padding: 0 16px 10px;
  overflow-x: auto;
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
