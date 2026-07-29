<template>
  <div class="session-panel">
    <div class="session-header">
      <div class="header-left">
        <router-link to="/" class="logo gradient-text">VerseNa</router-link>
        <span class="header-title">对话</span>
      </div>
      <div class="header-right">
        <button @click="handleNew" class="new-btn" title="新建对话" aria-label="新建对话">
          <Plus :size="17" aria-hidden="true" />
        </button>
        <router-link to="/settings" class="settings-btn" title="设置" aria-label="设置">
          <Settings :size="16" aria-hidden="true" />
        </router-link>
      </div>
    </div>

    <div class="session-items">
      <!-- Loading skeleton -->
      <template v-if="sessionStore.loading">
        <div v-for="i in 4" :key="i" class="session-item skeleton-item">
          <div class="skeleton-line"></div>
        </div>
      </template>
      <div v-else-if="sessionStore.error" class="session-load-error">
        <span>{{ sessionStore.error }}</span>
        <button class="session-retry-btn" @click="loadSessions" title="重新加载" aria-label="重新加载会话列表">
          <RefreshCcw :size="14" aria-hidden="true" />
        </button>
      </div>
      <template v-else>
        <template v-for="(group, persona) in groupedSessions" :key="persona">
          <div class="group-header" @click="toggleGroup(persona)">
            <ChevronRight
              class="group-arrow"
              :class="{ expanded: !collapsedGroups[persona] }"
              :size="14"
              aria-hidden="true"
            />
            <span class="group-name">{{ personaName(persona) }}</span>
            <span class="group-count">{{ group.length }}</span>
          </div>
          <Transition name="group-expand">
            <div v-show="!collapsedGroups[persona]" class="group-items">
              <div
                v-for="s in group"
                :key="s.id"
                class="session-item hover-lift"
                :class="{ active: sessionStore.currentSessionId === s.id, 'gradient-border': sessionStore.currentSessionId === s.id }"
                @click="handleSwitch(s.id)"
              >
                <template v-if="renamingId === s.id">
                  <input
                    v-model="newName"
                    @keydown.enter="confirmRename(s.id)"
                    @keydown.escape="renamingId = ''"
                    @blur="confirmRename(s.id)"
                    class="rename-input"
                    autofocus
                  />
                </template>
                <template v-else>
                  <div class="session-name">{{ s.name && s.name !== s.id ? s.name : s.id.replace('session_', '').slice(0, 12) }}</div>
                  <div class="session-actions">
                    <button class="action-btn" @click.stop="startEdit(s)" title="编辑" aria-label="编辑会话">
                      <Pencil :size="13" aria-hidden="true" />
                    </button>
                    <button class="action-btn delete" @click.stop="handleDelete(s.id)" title="删除" aria-label="删除会话">
                      <Trash2 :size="13" aria-hidden="true" />
                    </button>
                  </div>
                </template>
              </div>
            </div>
          </Transition>
        </template>
        <div v-if="Object.keys(groupedSessions).length === 0" class="empty">暂无对话</div>
      </template>
    </div>

    <!-- 新建会话：选择主题包 -->
    <div v-if="showNewDialog" class="modal-overlay" @click.self="showNewDialog = false">
      <section class="modal" role="dialog" aria-modal="true" aria-labelledby="new-session-title">
        <div class="modal-header">
          <div>
            <h2 id="new-session-title" class="modal-title">选择主题包</h2>
            <p class="modal-subtitle">角色、主题和语音配置会随会话保存</p>
          </div>
          <button class="modal-close" @click="showNewDialog = false" title="关闭" aria-label="关闭">
            <X :size="16" aria-hidden="true" />
          </button>
        </div>
        <div class="modal-body">
          <div v-if="themepacksLoading" class="modal-state">
            <LoaderCircle class="spin" :size="18" aria-hidden="true" />
            <span>正在加载主题包</span>
          </div>
          <div v-else-if="themepacksError" class="modal-state error-state">
            <span>{{ themepacksError }}</span>
            <button class="btn-inline" @click="fetchThemepacks">重试</button>
          </div>
          <div v-else-if="themepacks.length" class="pack-list">
            <button
              v-for="pack in themepacks"
              :key="pack.id"
              class="pack-card"
              :disabled="Boolean(creatingPackId)"
              @click="createWithPack(pack.id)"
            >
              <span class="pack-copy">
                <span class="pack-name">{{ pack.name }}</span>
                <span class="pack-info">角色: {{ pack.persona_ref || '默认' }} · 主题: {{ pack.theme_ref || '默认' }}</span>
              </span>
              <LoaderCircle v-if="creatingPackId === pack.id" class="spin" :size="16" aria-hidden="true" />
              <ChevronRight v-else :size="16" aria-hidden="true" />
            </button>
          </div>
          <div v-else class="modal-state">暂无可用主题包</div>
        </div>
        <div class="modal-actions">
          <button class="btn-cancel" @click="showNewDialog = false">取消</button>
        </div>
      </section>
    </div>

    <!-- 编辑会话：重命名 + 更改主题包 -->
    <div v-if="showEditDialog" class="modal-overlay" @click.self="showEditDialog = false">
      <section class="modal" role="dialog" aria-modal="true" aria-labelledby="edit-session-title">
        <div class="modal-header">
          <div>
            <h2 id="edit-session-title" class="modal-title">编辑会话</h2>
            <p class="modal-subtitle">调整名称或切换会话使用的主题包</p>
          </div>
          <button class="modal-close" @click="showEditDialog = false" title="关闭" aria-label="关闭">
            <X :size="16" aria-hidden="true" />
          </button>
        </div>
        <div class="modal-body">
          <div class="edit-field">
            <label for="session-name">会话名称</label>
            <input id="session-name" v-model="editName" class="rename-input modal-input" placeholder="会话名称" />
          </div>
          <div class="edit-field">
            <label for="session-pack">主题包</label>
            <select id="session-pack" v-model="editPackId" class="pack-select" :disabled="themepacksLoading">
              <option value="">无主题包</option>
              <option v-for="pack in themepacks" :key="pack.id" :value="pack.id">{{ pack.name }}</option>
            </select>
          </div>
        </div>
        <div class="modal-actions">
          <button class="btn-cancel" :disabled="editSaving" @click="showEditDialog = false">取消</button>
          <button class="btn-save" :disabled="editSaving || !editName.trim()" @click="saveEdit">
            <LoaderCircle v-if="editSaving" class="spin" :size="15" aria-hidden="true" />
            <span>{{ editSaving ? '保存中' : '保存' }}</span>
          </button>
        </div>
      </section>
    </div>

    <!-- 删除会话确认 -->
    <div v-if="showDeleteDialog" class="modal-overlay" @click.self="showDeleteDialog = false">
      <section class="modal modal-compact" role="alertdialog" aria-modal="true" aria-labelledby="delete-session-title">
        <div class="modal-header">
          <div class="danger-heading">
            <TriangleAlert :size="19" aria-hidden="true" />
            <h2 id="delete-session-title" class="modal-title">删除会话</h2>
          </div>
          <button class="modal-close" @click="showDeleteDialog = false" title="关闭" aria-label="关闭">
            <X :size="16" aria-hidden="true" />
          </button>
        </div>
        <div class="modal-body">
          <p class="delete-message">“{{ deleteSessionName }}”及其聊天记录将被永久删除。</p>
        </div>
        <div class="modal-actions">
          <button class="btn-cancel" :disabled="deleteSaving" @click="showDeleteDialog = false">取消</button>
          <button class="btn-danger" :disabled="deleteSaving" @click="confirmDelete">
            <LoaderCircle v-if="deleteSaving" class="spin" :size="15" aria-hidden="true" />
            <Trash2 v-else :size="15" aria-hidden="true" />
            <span>{{ deleteSaving ? '删除中' : '删除' }}</span>
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { ChevronRight, LoaderCircle, Pencil, Plus, RefreshCcw, Settings, Trash2, TriangleAlert, X } from 'lucide-vue-next'
import { useToast } from '../composables/useToast'
import { useSessionStore } from '../stores/session'
import { useChatStore } from '../stores/chat'
import { usePersonaStore } from '../stores/persona'
import { useThemeStore } from '../stores/theme'

const sessionStore = useSessionStore()
const chatStore = useChatStore()
const personaStore = usePersonaStore()
const themeStore = useThemeStore()
const toast = useToast()

const renamingId = ref('')
const newName = ref('')
const collapsedGroups = reactive({})
const showNewDialog = ref(false)
const showEditDialog = ref(false)
const showDeleteDialog = ref(false)
const themepacks = ref([])
const themepacksLoading = ref(false)
const themepacksError = ref('')
const creatingPackId = ref('')
const editSessionId = ref('')
const editName = ref('')
const editPackId = ref('')
const editSaving = ref(false)
const deleteSessionId = ref('')
const deleteSessionName = ref('')
const deleteSaving = ref(false)

const groupedSessions = computed(() => {
  const groups = {}
  for (const s of sessionStore.sessions) {
    const p = s.theme_pack_id || s.persona || 'default'
    if (!groups[p]) groups[p] = []
    groups[p].push(s)
  }
  return groups
})

function personaName(id) {
  // 先查主题包名称
  const pack = themepacks.value.find(p => p.id === id)
  if (pack) return pack.name || pack.id
  // 再查角色名称
  const p = personaStore.personas.find(p => p.id === id)
  return p ? p.name : id
}

function toggleGroup(persona) {
  collapsedGroups[persona] = !collapsedGroups[persona]
}

async function fetchThemepacks() {
  themepacksLoading.value = true
  themepacksError.value = ''
  try {
    const resp = await fetch('/api/themepacks')
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    themepacks.value = await resp.json()
  } catch (e) {
    console.error('Failed to fetch themepacks:', e)
    themepacksError.value = '主题包加载失败'
  } finally {
    themepacksLoading.value = false
  }
}

function handleNew() {
  fetchThemepacks()
  showNewDialog.value = true
}

async function createWithPack(packId) {
  if (creatingPackId.value) return
  creatingPackId.value = packId
  try {
    const packResp = await fetch(`/api/themepacks/${packId}`)
    if (!packResp.ok) throw new Error(`主题包读取失败: HTTP ${packResp.status}`)
    const pack = await packResp.json()

    if (pack.theme_ref) themeStore.applyTheme(pack.theme_ref)
    if (pack.persona_ref) personaStore.switchPersona(pack.persona_ref)

    const resp = await fetch('/api/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ theme_pack_id: packId })
    })
    if (!resp.ok) throw new Error(`会话创建失败: HTTP ${resp.status}`)
    const data = await resp.json()

    const metadataResp = await fetch(`/api/sessions/${data.session_id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ theme_pack_id: packId })
    })
    if (!metadataResp.ok) console.warn(`Session metadata update failed: HTTP ${metadataResp.status}`)

    sessionStore.switchSession(data.session_id)
    chatStore.clearMessages()
    await sessionStore.fetchSessions()
    showNewDialog.value = false
    toast.success('会话已创建')
  } catch (e) {
    toast.error(e.message || '会话创建失败')
  } finally {
    creatingPackId.value = ''
  }
}

// 暴露方法给父组件
defineExpose({
  handleNew
})

async function loadSessions() {
  try {
    await sessionStore.fetchSessions({ retries: 4, retryDelay: 250 })
  } catch (err) {
    console.error('Failed to fetch sessions:', err)
  }
}

onMounted(() => {
  fetchThemepacks()
  window.addEventListener('keydown', handleEscape)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleEscape)
})

function handleEscape(event) {
  if (event.key !== 'Escape') return
  if (showDeleteDialog.value && !deleteSaving.value) showDeleteDialog.value = false
  else if (showEditDialog.value && !editSaving.value) showEditDialog.value = false
  else if (showNewDialog.value && !creatingPackId.value) showNewDialog.value = false
}

const currentPackId = ref('')

async function handleSwitch(id) {
  const session = sessionStore.sessions.find(s => s.id === id)
  const newPackId = session?.theme_pack_id || ''

  // 只在主题包真正变化时才切换主题（避免背景重载）
  if (newPackId && newPackId !== currentPackId.value) {
    const packResp = await fetch(`/api/themepacks/${newPackId}`)
    if (packResp.ok) {
      const pack = await packResp.json()
      const themeId = pack.theme_ref || pack.id
      if (pack.persona_ref) personaStore.switchPersona(pack.persona_ref)
      const cssVarMap = { primary: '--primary', highlight: '--highlight', textPrimary: '--text-primary', textSecondary: '--text-secondary' }
      const colorOverrides = {}
      if (pack.theme?.colors) {
        for (const [key, cssVar] of Object.entries(cssVarMap)) {
          if (pack.theme.colors[key]) colorOverrides[cssVar] = pack.theme.colors[key]
        }
      }
      if (themeId) await themeStore.switchTheme(themeId, colorOverrides)
    }
    currentPackId.value = newPackId
  }

  // 加载历史
  const history = await fetch(`/api/sessions/${id}/history`).then(r => r.json())

  // 切换 session
  sessionStore.switchSession(id)

  // 等 Vue 完成 out 动画后清空并加载新消息
  await new Promise(r => setTimeout(r, 50))
  chatStore.loadHistory(history)
}

function handleDelete(id) {
  const session = sessionStore.sessions.find(s => s.id === id)
  deleteSessionId.value = id
  deleteSessionName.value = session?.name && session.name !== id
    ? session.name
    : id.replace('session_', '').slice(0, 12)
  showDeleteDialog.value = true
}

async function confirmDelete() {
  if (!deleteSessionId.value || deleteSaving.value) return
  deleteSaving.value = true
  try {
    const id = deleteSessionId.value
    const wasCurrentSession = sessionStore.currentSessionId === id
    await sessionStore.deleteSession(id)
    if (wasCurrentSession) chatStore.clearMessages()
    showDeleteDialog.value = false
    toast.success('会话已删除')
  } catch (e) {
    toast.error(e.message || '会话删除失败')
  } finally {
    deleteSaving.value = false
  }
}

function startRename(id) {
  renamingId.value = id
  newName.value = id
}

async function confirmRename(id) {
  const name = newName.value.trim()
  if (!name || name === id) { renamingId.value = ''; return }
  try {
    const resp = await fetch(`/api/sessions/${id}/rename`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    await sessionStore.fetchSessions()
  } catch (e) {
    toast.error('重命名失败')
  }
  renamingId.value = ''
}

function startEdit(session) {
  editSessionId.value = session.id
  editName.value = session.name && session.name !== session.id
    ? session.name
    : session.id.replace('session_', '').slice(0, 12)
  editPackId.value = session.theme_pack_id || ''
  fetchThemepacks()
  showEditDialog.value = true
}

async function saveEdit() {
  if (editSaving.value) return
  const id = editSessionId.value
  const name = editName.value.trim()
  editSaving.value = true
  try {
    const resp = await fetch(`/api/sessions/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name || undefined,
        theme_pack_id: editPackId.value || null
      })
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    await sessionStore.fetchSessions()
    showEditDialog.value = false
    toast.success('会话已保存')
  } catch (e) {
    toast.error('会话保存失败')
  } finally {
    editSaving.value = false
  }
}
</script>

<style scoped>
/* L1: Sidebar — 12px blur, 0.75 opacity, inner glow, no hard right border */
.session-panel {
  width: var(--sidebar-width, 220px);
  background: transparent;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  border-right: none;
  box-shadow: none;
  display: flex;
  flex-direction: column;
  height: 100vh;
  position: relative;
  z-index: 2;
}
.session-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 85%;
  margin: 12px 10px 8px;
  padding: 6px 8px 6px 12px;
  box-sizing: border-box;
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 999px;
  background: var(--surface-floating);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  animation: sidebar-control-enter var(--motion-base) var(--ease-emphasized) backwards;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.header-right {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  gap: 6px;
}

.logo {
  font-size: 18px;
  font-weight: bold;
  text-decoration: none;
  letter-spacing: 1px;
}

.header-title {
  font-size: 14px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.settings-btn {
  width: var(--control-icon-size);
  height: var(--control-icon-size);
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  color: var(--text-secondary);
  text-decoration: none;
  transition: color var(--motion-fast) var(--ease-standard), background var(--motion-fast) var(--ease-standard), transform var(--motion-fast) var(--ease-standard);
}

.settings-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
  transform: translateY(-1px);
}
.new-btn {
  width: var(--control-icon-size); height: var(--control-icon-size);
  background: transparent; color: var(--primary);
  border: none; border-radius: 8px;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: color var(--motion-fast) var(--ease-standard), background var(--motion-fast) var(--ease-standard), transform var(--motion-fast) var(--ease-standard);
}
.new-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
  transform: translateY(-1px);
}
.session-items { flex: 1; overflow-y: auto; padding: 4px 0; display: flex; flex-direction: column; gap: 3px; }

.session-load-error {
  width: 85%;
  min-height: 38px;
  margin: 10px;
  padding: 6px 7px 6px 12px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: var(--text-secondary);
  background: rgba(8, 18, 34, 0.24);
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 999px;
  font-size: 12px;
}
.session-retry-btn {
  width: 26px;
  height: 26px;
  flex: 0 0 26px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  color: var(--primary);
  background: transparent;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  transition: color var(--motion-fast) var(--ease-standard), background var(--motion-fast) var(--ease-standard), transform var(--motion-fast) var(--ease-standard);
}
.session-retry-btn:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.08);
  transform: rotate(30deg);
}

/* 分组标题 */
.group-header {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 85%;
  padding: 5px 9px;
  margin: 7px 10px 3px;
  box-sizing: border-box;
  background: rgba(8, 18, 34, 0.20);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  cursor: pointer;
  user-select: none;
  transition: background var(--motion-fast) var(--ease-standard), border-color var(--motion-fast) var(--ease-standard), transform var(--motion-fast) var(--ease-standard);
}
.group-arrow {
  color: var(--primary);
  flex: 0 0 14px;
  transition: transform var(--motion-fast) var(--ease-standard);
}
.group-arrow.expanded {
  transform: rotate(90deg);
}
.group-name {
  font-size: 12px;
  font-weight: 700;
  color: var(--primary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.group-count {
  font-size: 10px;
  color: var(--text-secondary);
  background: rgba(124, 92, 252, 0.15);
  padding: 1px 6px;
  border-radius: 8px;
  margin-left: auto;
}

/* 会话项 — 药丸形 */
.session-item {
  width: 85%;
  padding: 6px 52px 6px 12px;
  box-sizing: border-box;
  cursor: pointer;
  border: 1px solid rgba(255, 255, 255, 0.12) !important;
  box-shadow: none !important;
  border-radius: 999px;
  background: rgba(8, 18, 34, 0.24);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  position: relative;
  transition: background var(--motion-fast) var(--ease-standard), border-color var(--motion-fast) var(--ease-standard), transform var(--motion-fast) var(--ease-standard);
  margin: 2px 10px;
  animation: sidebar-control-enter var(--motion-base) var(--ease-emphasized) backwards;
}
.session-item:hover {
  background: rgba(18, 38, 62, 0.30);
  border-color: rgba(255, 255, 255, 0.26) !important;
  transform: translateX(2px);
}
/* Selected session */
.session-item.active {
  background: color-mix(in srgb, var(--highlight) 28%, rgba(8, 18, 34, 0.42));
  border-color: var(--highlight) !important;
  box-shadow: inset 2px 0 0 var(--highlight) !important;
}
.session-name {
  font-size: 13px; color: var(--text-primary);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.session-actions {
  position: absolute; right: 6px; top: 50%; transform: translateY(-50%);
  display: flex; gap: 2px; opacity: 0; transition: opacity var(--motion-fast) var(--ease-standard);
  padding: 3px;
  background: rgba(8, 18, 34, 0.46);
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 999px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}
.session-item:hover .session-actions { opacity: 1; }
.action-btn {
  width: 22px; height: 22px;
  display: flex; align-items: center; justify-content: center;
  background: none; border: none; cursor: pointer;
  padding: 0; color: var(--text-secondary);
  border-radius: 50%;
  transition: color var(--motion-fast) var(--ease-standard), background var(--motion-fast) var(--ease-standard);
}
.action-btn:hover { color: var(--primary); background: rgba(255, 255, 255, 0.08); }
.action-btn.delete:hover { color: #ff4757; background: rgba(255, 71, 87, 0.10); }
.rename-input {
  width: 100%; font-size: 13px; color: var(--text-primary);
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.20);
  border-radius: 4px; padding: 4px 6px; outline: none;
}
.rename-input:focus {
  border-color: var(--primary);
}
.empty { padding: 20px; text-align: center; color: var(--text-secondary); font-size: 13px; }

/* 分组展开/折叠动画 */
.group-items { overflow: hidden; }
.group-expand-enter-active { transition: all var(--motion-base) var(--ease-emphasized); }
.group-expand-leave-active { transition: all var(--motion-fast) var(--ease-standard); }
.group-expand-enter-from { opacity: 0; max-height: 0; }
.group-expand-enter-to { opacity: 1; max-height: 500px; }
.group-expand-leave-from { opacity: 1; max-height: 500px; }
.group-expand-leave-to { opacity: 0; max-height: 0; }

@keyframes sidebar-control-enter {
  from { opacity: 0; transform: translateY(5px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Skeleton loading */
.skeleton-item {
  pointer-events: none;
  animation: skeleton-pulse 1.5s infinite;
}
.skeleton-line {
  height: 14px;
  border-radius: 4px;
  background: rgba(255,255,255,0.08);
  width: 70%;
}
@keyframes skeleton-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* 会话弹窗 */
.modal-overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(0, 0, 0, 0.58);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  z-index: 1000;
  animation: overlay-enter var(--motion-fast) var(--ease-standard) both;
}
.modal {
  width: min(420px, 100%);
  max-height: min(72vh, 620px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--surface-modal);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 8px;
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.42);
  animation: modal-enter var(--motion-base) var(--ease-emphasized) both;
}
.modal-compact { width: min(380px, 100%); }
.modal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 18px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.modal-title {
  margin: 0;
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 650;
  line-height: 1.35;
}
.modal-subtitle {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}
.modal-close {
  width: var(--control-icon-size);
  height: var(--control-icon-size);
  flex: 0 0 var(--control-icon-size);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  color: var(--text-secondary);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: color var(--motion-fast) var(--ease-standard), background var(--motion-fast) var(--ease-standard);
}
.modal-close:hover { color: var(--text-primary); background: rgba(255, 255, 255, 0.08); }
.modal-body { padding: 16px 18px; overflow-y: auto; }
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 18px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}
.pack-list { display: flex; flex-direction: column; gap: 8px; }
.pack-card {
  width: 100%;
  min-height: 58px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  color: var(--text-primary);
  text-align: left;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--motion-fast) var(--ease-standard), border-color var(--motion-fast) var(--ease-standard), transform var(--motion-fast) var(--ease-standard);
}
.pack-card:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.10);
  border-color: color-mix(in srgb, var(--primary) 55%, transparent);
  transform: translateY(-1px);
}
.pack-card:disabled { cursor: wait; opacity: 0.65; }
.pack-copy { min-width: 0; display: flex; flex-direction: column; }
.pack-name { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.pack-info { margin-top: 3px; font-size: 11px; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.modal-state {
  min-height: 96px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 13px;
  text-align: center;
}
.error-state { flex-direction: column; color: #fca5a5; }
.btn-inline { padding: 4px 10px; color: var(--primary); background: transparent; border: 1px solid currentColor; border-radius: 6px; cursor: pointer; }
.btn-cancel,
.btn-save,
.btn-danger {
  min-width: 76px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 0 14px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
  transition: background var(--motion-fast) var(--ease-standard), border-color var(--motion-fast) var(--ease-standard), filter var(--motion-fast) var(--ease-standard);
}
.btn-cancel { background: rgba(255, 255, 255, 0.08); color: var(--text-secondary); border: 1px solid rgba(255, 255, 255, 0.14); }
.btn-save { background: var(--primary); color: white; border: 1px solid transparent; }
.btn-danger { background: #dc2626; color: white; border: 1px solid transparent; }
.btn-cancel:hover:not(:disabled) { background: rgba(255, 255, 255, 0.13); color: var(--text-primary); }
.btn-save:hover:not(:disabled), .btn-danger:hover:not(:disabled) { filter: brightness(1.08); }
.btn-cancel:disabled, .btn-save:disabled, .btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }
.edit-field + .edit-field { margin-top: 14px; }
.edit-field label { display: block; margin-bottom: 6px; color: var(--text-secondary); font-size: 12px; }
.modal-input,
.pack-select {
  width: 100%;
  min-height: 38px;
  padding: 8px 10px;
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: var(--radius-sm);
  outline: none;
  font: inherit;
  font-size: 13px;
}
.modal-input:focus, .pack-select:focus { border-color: var(--primary); }
.danger-heading { display: flex; align-items: center; gap: 8px; color: #f87171; }
.danger-heading .modal-title { color: inherit; }
.delete-message { margin: 0; color: var(--text-secondary); font-size: 13px; line-height: 1.65; }
.spin { animation: spin 800ms linear infinite; }

@keyframes overlay-enter { from { opacity: 0; } to { opacity: 1; } }
@keyframes modal-enter { from { opacity: 0; transform: translateY(8px) scale(0.98); } to { opacity: 1; transform: translateY(0) scale(1); } }

@media (max-width: 767px) {
  .session-panel {
    width: min(84vw, 320px);
    height: calc(100dvh - 80px);
    position: fixed;
    top: 64px;
    left: 8px;
    z-index: 150;
    transform: translateX(calc(-100% - 16px));
    background: rgba(8, 16, 30, 0.76);
    backdrop-filter: blur(14px) saturate(0.9);
    -webkit-backdrop-filter: blur(14px) saturate(0.9);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 8px;
    box-shadow: 0 16px 36px rgba(0, 0, 0, 0.28);
    transition: transform var(--motion-base) var(--ease-emphasized);
  }

  .session-panel.mobile-open {
    transform: translateX(0);
  }

  .session-actions { opacity: 1; }

  .modal-overlay { padding: 12px; }
  .modal { max-height: calc(100dvh - 24px); }
}

@media (min-width: 768px) and (max-width: 1024px) {
  .session-panel { width: 200px; }
}

@media (min-width: 1441px) {
  .session-panel { width: 280px; }
}
</style>
