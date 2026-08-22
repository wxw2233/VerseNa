<template>
  <div class="tab-content">
    <h2>记忆管理</h2>
    <p class="tab-desc">管理 Agent 保存的偏好、事实和指令。工作区记忆只会在对应工作目录中生效。</p>

    <div class="memory-filters">
      <button
        v-for="filter in categoryFilters"
        :key="filter.value"
        type="button"
        :class="{ active: memoryFilter === filter.value }"
        @click="memoryFilter = filter.value; loadMemories()"
      >{{ filter.label }}</button>
      <span class="filter-divider"></span>
      <button
        v-for="filter in scopeFilters"
        :key="filter.value"
        type="button"
        :class="{ active: scopeFilter === filter.value }"
        @click="scopeFilter = filter.value; loadMemories()"
      >{{ filter.label }}</button>
    </div>

    <div class="workspace-note" v-if="workspace">
      当前工作区：<code :title="workspace">{{ workspace }}</code>
    </div>

    <input
      type="text"
      @input="e => debouncedSearch(e.target.value)"
      placeholder="搜索记忆..."
      class="memory-search"
    />

    <div class="memory-add">
      <input type="text" v-model="newMemoryContent" placeholder="添加新记忆..." @keyup.enter="addMemory" />
      <select v-model="newMemoryCategory">
        <option value="preference">偏好</option>
        <option value="fact">事实</option>
        <option value="instruction">指令</option>
        <option value="general">通用</option>
      </select>
      <select v-model="newMemoryScope">
        <option value="global">全局</option>
        <option value="workspace">当前工作区</option>
      </select>
      <label class="memory-auto-apply">
        <input type="checkbox" v-model="newMemoryAutoApply" /> 自动参考
      </label>
      <button type="button" @click="addMemory">添加</button>
    </div>

    <div class="memory-list">
      <template v-if="loading">
        <div v-for="i in 3" :key="i" class="memory-card skeleton">
          <div class="skeleton-line w80"></div>
          <div class="skeleton-line w60"></div>
        </div>
      </template>
      <template v-else>
        <div v-for="mem in filteredMemories" :key="mem.id" class="memory-card">
          <template v-if="editingMemoryId !== mem.id">
            <div class="memory-content">{{ mem.content }}</div>
          </template>
          <template v-else>
            <input class="edit-input" type="text" v-model="editingMemoryContent" @keyup.enter="saveEditMemory(mem.id)" />
            <div class="edit-options">
              <select v-model="editingMemoryCategory">
                <option value="preference">偏好</option>
                <option value="fact">事实</option>
                <option value="instruction">指令</option>
                <option value="general">通用</option>
              </select>
              <select v-model="editingMemoryScope">
                <option value="global">全局</option>
                <option value="workspace">当前工作区</option>
              </select>
              <label class="memory-auto-apply">
                <input type="checkbox" v-model="editingMemoryAutoApply" /> 自动参考
              </label>
            </div>
          </template>

          <div class="memory-meta">
            <span class="memory-category" :class="mem.category">{{ memoryLabel(mem.category) }}</span>
            <span class="memory-scope" :class="mem.scope === 'workspace' ? 'workspace' : 'global'">
              {{ mem.scope === 'workspace' ? '工作区' : '全局' }}
            </span>
            <span class="memory-source">{{ mem.source === 'auto' ? '自动' : '手动' }}</span>
            <span class="memory-auto-state" :class="{ enabled: mem.auto_apply }">
              {{ mem.auto_apply ? '自动参考' : '仅供参考' }}
            </span>
            <span class="memory-id">#{{ mem.id }}</span>
            <span class="memory-usage">命中 {{ mem.use_count || 0 }} 次</span>
            <span v-if="mem.verified_at" class="memory-verified" :title="formatTime(mem.verified_at)">已验证</span>
            <span class="memory-time">{{ formatTime(mem.created_at) }}</span>
          </div>
          <div v-if="mem.scope === 'workspace' && mem.workspace_path" class="memory-path" :title="mem.workspace_path">
            {{ mem.workspace_path }}
          </div>
          <div class="memory-actions">
            <button v-if="editingMemoryId !== mem.id" type="button" @click="startEditMemory(mem)">编辑</button>
            <button v-else type="button" @click="saveEditMemory(mem.id)">保存</button>
            <button v-if="editingMemoryId !== mem.id" type="button" @click="verifyMemory(mem.id)">确认有效</button>
            <button type="button" @click="deleteMemory(mem.id)" class="btn-danger">删除</button>
          </div>
        </div>
        <div v-if="!filteredMemories.length" class="empty-hint">暂无匹配记忆</div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useDebounce } from '../../composables/usePerformance'

const memories = ref([])
const workspace = ref('')
const memoryFilter = ref('all')
const scopeFilter = ref('all')
const memorySearch = ref('')
const newMemoryContent = ref('')
const newMemoryCategory = ref('preference')
const newMemoryScope = ref('global')
const newMemoryAutoApply = ref(true)
const editingMemoryId = ref(null)
const editingMemoryContent = ref('')
const editingMemoryCategory = ref('general')
const editingMemoryScope = ref('global')
const editingMemoryAutoApply = ref(true)
const loading = ref(false)

const categoryFilters = [
  { value: 'all', label: '全部' },
  { value: 'preference', label: '偏好' },
  { value: 'fact', label: '事实' },
  { value: 'instruction', label: '指令' },
  { value: 'general', label: '通用' },
]
const scopeFilters = [
  { value: 'all', label: '全部作用域' },
  { value: 'global', label: '全局' },
  { value: 'workspace', label: '当前工作区' },
]
const { debouncedFn: debouncedSearch } = useDebounce((value) => {
  memorySearch.value = value
}, 300)

const filteredMemories = computed(() => {
  const query = memorySearch.value.trim().toLowerCase()
  if (!query) return memories.value
  return memories.value.filter(memory => memory.content.toLowerCase().includes(query))
})

function memoryLabel(category) {
  return { preference: '偏好', fact: '事实', instruction: '指令', general: '通用' }[category] || category
}

async function loadWorkspace() {
  try {
    const response = await fetch('/api/tools/workspace')
    const data = await response.json()
    workspace.value = data.path || ''
  } catch {
    workspace.value = ''
  }
}

async function loadMemories() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (memoryFilter.value !== 'all') params.set('category', memoryFilter.value)
    if (scopeFilter.value !== 'all') params.set('scope', scopeFilter.value)
    if (scopeFilter.value === 'workspace' && workspace.value) params.set('workspace_path', workspace.value)
    const response = await fetch(`/api/memories?${params.toString()}`)
    if (!response.ok) throw new Error('memory request failed')
    memories.value = await response.json()
  } catch {
    memories.value = []
  } finally {
    loading.value = false
  }
}

async function addMemory() {
  const content = newMemoryContent.value.trim()
  if (!content || (newMemoryScope.value === 'workspace' && !workspace.value)) return
  const response = await fetch('/api/memories', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content,
      category: newMemoryCategory.value,
      scope: newMemoryScope.value,
      auto_apply: newMemoryAutoApply.value,
    }),
  })
  if (response.ok) {
    newMemoryContent.value = ''
    await loadMemories()
  }
}

function startEditMemory(memory) {
  editingMemoryId.value = memory.id
  editingMemoryContent.value = memory.content
  editingMemoryCategory.value = memory.category || 'general'
  editingMemoryScope.value = memory.scope || 'global'
  editingMemoryAutoApply.value = Boolean(memory.auto_apply)
}

async function saveEditMemory(id) {
  const content = editingMemoryContent.value.trim()
  if (!content || (editingMemoryScope.value === 'workspace' && !workspace.value)) return
  const response = await fetch(`/api/memories/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content,
      category: editingMemoryCategory.value,
      scope: editingMemoryScope.value,
      auto_apply: editingMemoryAutoApply.value,
    }),
  })
  if (response.ok) {
    editingMemoryId.value = null
    await loadMemories()
  }
}

async function verifyMemory(id) {
  const response = await fetch(`/api/memories/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ verify: true }),
  })
  if (response.ok) await loadMemories()
}

async function deleteMemory(id) {
  const response = await fetch(`/api/memories/${id}`, { method: 'DELETE' })
  if (response.ok) await loadMemories()
}

function formatTime(timestamp) {
  if (!timestamp) return ''
  return new Date(timestamp).toLocaleString('zh-CN')
}

onMounted(async () => {
  await loadWorkspace()
  await loadMemories()
})
</script>

<style scoped>
.tab-desc { font-size: 13px; color: var(--text-secondary); margin-bottom: 16px; }
.memory-filters { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 10px; }
.memory-filters button, .memory-add button, .memory-actions button {
  border: 0; border-radius: 6px; cursor: pointer; font-size: 12px;
}
.memory-filters button {
  padding: 5px 11px; color: var(--text-secondary); background: rgba(20, 20, 40, 0.60);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
}
.memory-filters button.active { background: var(--primary); color: #fff; box-shadow: none; }
.filter-divider { width: 1px; height: 20px; background: rgba(255,255,255,0.18); margin: 0 2px; }
.workspace-note { color: var(--text-secondary); font-size: 12px; margin: 0 0 12px; }
.workspace-note code, .memory-path { color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.memory-search, .memory-add input[type="text"], .memory-add select, .edit-input, .edit-options select {
  border: 0; outline: none; border-radius: 6px; color: var(--text-primary);
  background: rgba(20, 20, 40, 0.60); box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
}
.memory-search { width: 100%; padding: 8px 12px; margin-bottom: 12px; }
.memory-add { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.memory-add input[type="text"] { flex: 1 1 240px; padding: 8px 12px; }
.memory-add select, .edit-options select { padding: 8px; }
.memory-auto-apply { display: inline-flex; align-items: center; gap: 5px; padding: 0 3px; color: var(--text-secondary); font-size: 12px; white-space: nowrap; cursor: pointer; }
.memory-auto-apply input { accent-color: var(--primary); }
.memory-add button { padding: 8px 16px; background: var(--primary); color: #fff; }
.memory-list { display: flex; flex-direction: column; gap: 8px; }
.memory-card { padding: 12px; background: rgba(20, 20, 40, 0.60); border-radius: var(--radius); box-shadow: var(--ui-border); }
.memory-content { font-size: 14px; color: var(--text-primary); margin-bottom: 8px; white-space: pre-wrap; }
.edit-input { width: 100%; padding: 8px 10px; margin-bottom: 8px; }
.edit-options { display: flex; gap: 8px; margin-bottom: 8px; }
.memory-meta { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; font-size: 11px; color: var(--text-secondary); margin-bottom: 6px; }
.memory-category, .memory-scope { padding: 2px 6px; border-radius: 4px; }
.memory-category.preference { color: #60a5fa; background: rgba(59,130,246,0.15); }
.memory-category.fact { color: #4ade80; background: rgba(34,197,94,0.15); }
.memory-category.instruction { color: #f87171; background: rgba(239,68,68,0.15); }
.memory-category.general { color: #aaa; background: rgba(136,136,170,0.15); }
.memory-scope.global { color: #c4b5fd; background: rgba(124,92,252,0.15); }
.memory-scope.workspace { color: #67e8f9; background: rgba(34,211,238,0.15); }
.memory-auto-state { color: #a1a1aa; }
.memory-auto-state.enabled { color: #86efac; }
.memory-verified { color: #86efac; }
.memory-id { font-family: monospace; color: var(--text-secondary); }
.memory-path { font-size: 11px; margin-bottom: 8px; }
.memory-actions { display: flex; gap: 8px; }
.memory-actions button { padding: 4px 8px; color: var(--text-secondary); background: rgba(20,20,40,0.60); box-shadow: 0 0 0 1px rgba(255,255,255,0.20); }
.memory-actions .btn-danger { color: #ef4444; }
.empty-hint { text-align: center; padding: 28px; color: var(--text-secondary); font-size: 13px; }
.skeleton { animation: pulse 1.5s infinite; }
.skeleton-line { height: 14px; border-radius: 4px; background: rgba(255,255,255,0.08); margin-bottom: 8px; }
.skeleton-line.w80 { width: 80%; } .skeleton-line.w60 { width: 60%; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
@media (max-width: 640px) { .memory-add > * { flex: 1 1 100%; } .memory-add button { flex: 0 0 auto; } }
</style>
