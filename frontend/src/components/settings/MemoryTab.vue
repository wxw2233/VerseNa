<template>
  <div class="tab-content">
    <h2>记忆管理</h2>
    <p class="tab-desc">Agent 会自动记住用户偏好，也可手动添加/编辑/删除。</p>

    <!-- 分类筛选 -->
    <div class="memory-filters">
      <button v-for="cat in ['all', 'preference', 'fact', 'instruction', 'general']"
              :key="cat"
              :class="{ active: memoryFilter === cat }"
              @click="memoryFilter = cat; loadMemories()">
        {{ memoryLabel(cat) }}
      </button>
    </div>

    <!-- 搜索 -->
    <input type="text" @input="e => debouncedSearch(e.target.value)" placeholder="搜索记忆..." class="memory-search" />

    <!-- 添加记忆 -->
    <div class="memory-add">
      <input type="text" v-model="newMemoryContent" placeholder="添加新记忆..." />
      <select v-model="newMemoryCategory">
        <option value="preference">偏好</option>
        <option value="fact">事实</option>
        <option value="instruction">指令</option>
        <option value="general">通用</option>
      </select>
      <button @click="addMemory">添加</button>
    </div>

    <!-- 记忆列表 -->
    <div class="memory-list">
      <!-- Loading skeleton -->
      <template v-if="loading">
        <div v-for="i in 3" :key="i" class="memory-card skeleton">
          <div class="skeleton-line w80"></div>
          <div class="skeleton-line w60"></div>
        </div>
      </template>
      <template v-else>
        <div v-for="mem in filteredMemories" :key="mem.id" class="memory-card">
          <div class="memory-content" v-if="editingMemoryId !== mem.id">
            {{ mem.content }}
          </div>
          <input v-else type="text" v-model="editingMemoryContent" @keyup.enter="saveEditMemory(mem.id)" />
          <div class="memory-meta">
            <span class="memory-category" :class="mem.category">{{ memoryLabel(mem.category) }}</span>
            <span class="memory-source">{{ mem.source === 'auto' ? '自动' : '手动' }}</span>
            <span class="memory-time">{{ formatTime(mem.created_at) }}</span>
          </div>
          <div class="memory-actions">
            <button v-if="editingMemoryId !== mem.id" @click="startEditMemory(mem)">编辑</button>
            <button v-else @click="saveEditMemory(mem.id)">保存</button>
            <button @click="deleteMemory(mem.id)" class="btn-danger">删除</button>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useDebounce } from '../../composables/usePerformance'

const memories = ref([])
const memoryFilter = ref('all')
const memorySearch = ref('')
const newMemoryContent = ref('')
const newMemoryCategory = ref('preference')
const editingMemoryId = ref(null)
const editingMemoryContent = ref('')
const loading = ref(false)

// 防抖搜索
const { debouncedFn: debouncedSearch } = useDebounce((val) => {
  memorySearch.value = val
}, 300)

const filteredMemories = computed(() => {
  let list = memories.value
  if (memorySearch.value) {
    const q = memorySearch.value.toLowerCase()
    list = list.filter(m => m.content.toLowerCase().includes(q))
  }
  return list
})

function memoryLabel(cat) {
  const labels = { all: '全部', preference: '偏好', fact: '事实', instruction: '指令', general: '通用' }
  return labels[cat] || cat
}

async function loadMemories() {
  loading.value = true
  try {
    const url = memoryFilter.value === 'all' ? '/api/memories' : `/api/memories?category=${memoryFilter.value}`
    const resp = await fetch(url)
    memories.value = await resp.json()
  } catch {
    memories.value = []
  } finally {
    loading.value = false
  }
}

async function addMemory() {
  if (!newMemoryContent.value.trim()) return
  await fetch('/api/memories', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: newMemoryContent.value, category: newMemoryCategory.value })
  })
  newMemoryContent.value = ''
  await loadMemories()
}

function startEditMemory(mem) {
  editingMemoryId.value = mem.id
  editingMemoryContent.value = mem.content
}

async function saveEditMemory(id) {
  await fetch(`/api/memories/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: editingMemoryContent.value })
  })
  editingMemoryId.value = null
  await loadMemories()
}

async function deleteMemory(id) {
  await fetch(`/api/memories/${id}`, { method: 'DELETE' })
  await loadMemories()
}

function formatTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleString('zh-CN')
}

onMounted(() => loadMemories())
</script>

<style scoped>
.tab-desc { font-size: 13px; color: var(--text-secondary); margin-bottom: 16px; }
.memory-filters { display: flex; gap: 8px; margin-bottom: 12px; }
.memory-filters button {
  padding: 4px 12px;
  border-radius: 12px;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
  background: rgba(20, 20, 40, 0.60);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 12px;
  border: none;
  transition: filter 0.2s, transform 0.2s;
}
.memory-filters button.active {
  background: var(--primary);
  color: white;
  box-shadow: none;
}
.memory-filters button:hover:not(.active) {
  filter: brightness(1.08);
  transform: translateY(-1px);
}
.memory-search {
  width: 100%;
  padding: 8px 12px;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
  border-radius: 6px;
  background: rgba(20, 20, 40, 0.60);
  color: var(--text-primary);
  margin-bottom: 12px;
  border: none;
}
.memory-add { display: flex; gap: 8px; margin-bottom: 16px; }
.memory-add input {
  flex: 1;
  padding: 8px 12px;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
  border-radius: 6px;
  background: rgba(20, 20, 40, 0.60);
  color: var(--text-primary);
  border: none;
}
.memory-add select {
  padding: 8px;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
  border-radius: 6px;
  background: rgba(20, 20, 40, 0.60);
  color: var(--text-primary);
  border: none;
}
.memory-add button {
  padding: 8px 16px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: white;
  cursor: pointer;
  transition: filter 0.2s, transform 0.2s;
}
.memory-add button:hover {
  filter: brightness(1.08);
  transform: translateY(-1px);
}
.memory-list { display: flex; flex-direction: column; gap: 8px; }
.memory-card {
  padding: 12px;
  background: rgba(20, 20, 40, 0.60);
  border-radius: var(--radius);
  box-shadow: var(--ui-border);
}
.memory-content { font-size: 14px; color: var(--text-primary); margin-bottom: 8px; }
.memory-meta { display: flex; gap: 8px; font-size: 11px; color: var(--text-secondary); margin-bottom: 8px; }
.memory-category { padding: 2px 6px; border-radius: 4px; }
.memory-category.preference { background: rgba(59,130,246,0.15); color: #3b82f6; }
.memory-category.fact { background: rgba(34,197,94,0.15); color: #22c55e; }
.memory-category.instruction { background: rgba(239,68,68,0.15); color: #ef4444; }
.memory-category.general { background: rgba(136,136,170,0.15); color: #8888aa; }
.memory-actions { display: flex; gap: 8px; }
.memory-actions button {
  padding: 4px 8px;
  border: none;
  border-radius: 4px;
  background: rgba(20, 20, 40, 0.60);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 12px;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
  transition: filter 0.2s;
}
.memory-actions button:hover {
  filter: brightness(1.1);
}
.memory-actions .btn-danger { color: #ef4444; }

/* Skeleton loading */
.skeleton { animation: pulse 1.5s infinite; }
.skeleton-line {
  height: 14px;
  border-radius: 4px;
  background: rgba(255,255,255,0.08);
  margin-bottom: 8px;
}
.skeleton-line.w80 { width: 80%; }
.skeleton-line.w60 { width: 60%; }
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

input, select {
  outline: none;
  font-size: 14px;
}
</style>
