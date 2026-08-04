<template>
  <aside class="workspace-panel" aria-label="工作目录">
    <header>
      <div class="panel-title">
        <FolderCog :size="17" aria-hidden="true" />
        <span>工作目录</span>
      </div>
      <button class="icon-btn" title="关闭" aria-label="关闭工作目录" @click="emit('close')">
        <X :size="17" aria-hidden="true" />
      </button>
    </header>

    <div v-if="!browserOpen" class="workspace-body">
      <label>当前目录</label>
      <code :title="settings.effective_workspace">{{ settings.effective_workspace || '加载中...' }}</code>

      <div class="workspace-action-row">
        <button class="browse-btn" :disabled="saving" @click="openBrowser">
          <FolderOpen :size="17" aria-hidden="true" />
          <span>浏览文件夹</span>
          <ChevronRight :size="16" aria-hidden="true" />
        </button>
      </div>

      <div v-if="recentWorkspaces.length" class="recent-section">
        <label>最近使用</label>
        <ul class="workspace-list recent-list">
          <li v-for="path in recentWorkspaces" :key="path">
            <button
              class="recent-row"
              :title="path"
              :disabled="saving"
              @click="selectPath(path)"
            >
              <Folder :size="14" aria-hidden="true" />
              <span>{{ path }}</span>
            </button>
          </li>
        </ul>
      </div>

      <div class="workspace-action-row reset-action">
        <button
          class="reset-btn"
          :disabled="saving || settings.is_default"
          @click="emit('reset-workspace')"
        >
          <RotateCcw :size="15" aria-hidden="true" />
          <span>恢复默认目录</span>
        </button>
      </div>
    </div>

    <div v-else class="directory-browser">
      <div class="browser-toolbar">
        <button
          class="icon-btn"
          :disabled="browserLoading || !parentPath"
          title="返回上级"
          aria-label="返回上级目录"
          @click="browse(parentPath)"
        >
          <ArrowUp :size="17" aria-hidden="true" />
        </button>
        <code :title="browserPath">{{ browserPath }}</code>
        <button
          class="icon-btn"
          :disabled="browserLoading || creatingFolder"
          title="新建文件夹"
          aria-label="新建文件夹"
          @click="startCreateFolder"
        >
          <FolderPlus :size="17" aria-hidden="true" />
        </button>
      </div>

      <div class="directory-list">
        <div v-if="browserLoading" class="browser-state">
          <LoaderCircle class="spin" :size="18" aria-hidden="true" />
          <span>加载中</span>
        </div>
        <div v-else-if="browserError" class="browser-state error">{{ browserError }}</div>
        <template v-else>
          <div v-if="roots.length > 1" class="list-section">
            <span class="list-section-label">磁盘</span>
            <ul class="workspace-list">
              <li v-for="root in roots" :key="root.path">
                <button class="directory-row root-row" :title="root.path" @click="browse(root.path)">
                  <HardDrive :size="15" aria-hidden="true" />
                  <span>{{ root.name }}</span>
                  <ChevronRight :size="15" aria-hidden="true" />
                </button>
              </li>
            </ul>
          </div>
          <div class="list-section">
            <span class="list-section-label">文件夹</span>
            <ul class="workspace-list">
              <li v-if="creatingFolder">
                <form class="create-folder-row" @submit.prevent="createFolder">
                  <FolderPlus :size="16" aria-hidden="true" />
                  <input
                    ref="folderNameInput"
                    v-model="folderName"
                    type="text"
                    maxlength="120"
                    placeholder="文件夹名称"
                    aria-label="文件夹名称"
                    :disabled="folderCreating"
                    @keydown.esc.prevent="cancelCreateFolder"
                  />
                  <button class="inline-action" type="submit" :disabled="folderCreating || !folderName.trim()" title="创建" aria-label="创建文件夹">
                    <LoaderCircle v-if="folderCreating" class="spin" :size="14" aria-hidden="true" />
                    <Check v-else :size="14" aria-hidden="true" />
                  </button>
                  <button class="inline-action" type="button" :disabled="folderCreating" title="取消" aria-label="取消新建文件夹" @click="cancelCreateFolder">
                    <X :size="14" aria-hidden="true" />
                  </button>
                </form>
                <div v-if="folderCreateError" class="create-folder-error">{{ folderCreateError }}</div>
              </li>
              <li v-for="directory in directories" :key="directory.path">
                <button
                  class="directory-row"
                  :title="directory.path"
                  @click="browse(directory.path)"
                >
                  <Folder :size="16" aria-hidden="true" />
                  <span>{{ directory.name }}</span>
                  <ChevronRight :size="15" aria-hidden="true" />
                </button>
              </li>
            </ul>
          </div>
        </template>
        <div v-if="!browserLoading && !browserError && !creatingFolder && directories.length === 0" class="browser-state">
          没有子文件夹
        </div>
      </div>

      <div class="browser-actions">
        <button class="secondary-btn" :disabled="saving" @click="browserOpen = false">取消</button>
        <button class="primary-btn" :disabled="saving || browserLoading || !!browserError" @click="selectPath(browserPath)">
          <LoaderCircle v-if="saving" class="spin" :size="15" aria-hidden="true" />
          <FolderCheck v-else :size="15" aria-hidden="true" />
          <span>选择当前文件夹</span>
        </button>
      </div>
    </div>

    <footer>
      <ShieldCheck v-if="settings.approval_mode === 'auto'" :size="14" aria-hidden="true" />
      <ShieldAlert v-else :size="14" aria-hidden="true" />
      <span>{{ settings.approval_mode === 'auto' ? '自动审批' : '请求批准' }}</span>
    </footer>
  </aside>
</template>

<script setup>
import { nextTick, ref } from 'vue'
import {
  ArrowUp,
  Check,
  ChevronRight,
  Folder,
  FolderCheck,
  FolderCog,
  FolderOpen,
  FolderPlus,
  HardDrive,
  LoaderCircle,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  X,
} from 'lucide-vue-next'

const props = defineProps({
  settings: { type: Object, required: true },
  saving: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'save-workspace', 'reset-workspace'])
const recentWorkspaces = ref(loadRecent())
const browserOpen = ref(false)
const browserLoading = ref(false)
const browserError = ref('')
const browserPath = ref('')
const parentPath = ref(null)
const directories = ref([])
const roots = ref([])
const creatingFolder = ref(false)
const folderCreating = ref(false)
const folderName = ref('')
const folderCreateError = ref('')
const folderNameInput = ref(null)

function loadRecent() {
  try {
    const value = JSON.parse(localStorage.getItem('recent-tool-workspaces') || '[]')
    return Array.isArray(value) ? value.slice(0, 6) : []
  } catch {
    return []
  }
}

function remember(path) {
  recentWorkspaces.value = [path, ...recentWorkspaces.value.filter(item => item !== path)].slice(0, 6)
  localStorage.setItem('recent-tool-workspaces', JSON.stringify(recentWorkspaces.value))
}

function openBrowser() {
  browserOpen.value = true
  browse(props.settings.effective_workspace)
}

async function browse(path) {
  if (!path || browserLoading.value) return
  cancelCreateFolder()
  browserLoading.value = true
  browserError.value = ''
  try {
    const response = await fetch(`/api/tools/directories?path=${encodeURIComponent(path)}`)
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.detail || `无法浏览目录: HTTP ${response.status}`)
    browserPath.value = data.current
    parentPath.value = data.parent
    directories.value = data.directories || []
    roots.value = data.roots || []
  } catch (error) {
    browserError.value = error.message || '无法浏览此目录'
  } finally {
    browserLoading.value = false
  }
}

async function startCreateFolder() {
  creatingFolder.value = true
  folderName.value = ''
  folderCreateError.value = ''
  await nextTick()
  folderNameInput.value?.focus()
}

function cancelCreateFolder() {
  if (folderCreating.value) return
  creatingFolder.value = false
  folderName.value = ''
  folderCreateError.value = ''
}

async function createFolder() {
  const name = folderName.value.trim()
  if (!name || folderCreating.value) return
  folderCreating.value = true
  folderCreateError.value = ''
  try {
    const response = await fetch('/api/tools/directories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ parent: browserPath.value, name }),
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.detail || `新建文件夹失败: HTTP ${response.status}`)
    creatingFolder.value = false
    folderName.value = ''
    await browse(browserPath.value)
  } catch (error) {
    folderCreateError.value = error.message || '新建文件夹失败'
    await nextTick()
    folderNameInput.value?.focus()
  } finally {
    folderCreating.value = false
  }
}

function selectPath(path) {
  if (!path) return
  remember(path)
  browserOpen.value = false
  emit('save-workspace', path)
}
</script>

<style>
.workspace-panel,
.workspace-panel * {
  box-sizing: border-box;
}
.workspace-panel button {
  appearance: none;
  -webkit-appearance: none;
  margin: 0;
  font: inherit;
}
.workspace-panel {
  width: 312px;
  height: 100vh;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  color: var(--text-primary);
  background: color-mix(in srgb, var(--surface-modal) 92%, transparent);
  border-left: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow: -14px 0 30px rgba(0, 0, 0, 0.18);
  backdrop-filter: blur(18px);
  box-sizing: border-box;
}
.workspace-panel > header {
  height: 58px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px 0 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.09);
  flex-shrink: 0;
}
.workspace-panel .panel-title { display: flex; align-items: center; gap: 9px; font-size: 14px; font-weight: 600; }
.workspace-panel .icon-btn {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  padding: 0;
  color: var(--text-secondary);
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
.workspace-panel .icon-btn:hover:not(:disabled) { color: var(--text-primary); background: rgba(255, 255, 255, 0.08); }
.workspace-panel .icon-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.workspace-body { flex: 1; padding: 18px 16px; overflow-y: auto; }
.workspace-panel label { display: block; margin: 0 0 7px; color: var(--text-secondary); font-size: 12px; }
.workspace-body > code {
  display: block;
  min-height: 44px;
  margin-bottom: 16px;
  padding: 10px;
  overflow-wrap: anywhere;
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.055);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  font-size: 11px;
  line-height: 1.45;
  box-sizing: border-box;
}
.workspace-action-row {
  display: block;
  width: 100%;
}
.browse-btn {
  width: 100%;
  height: 40px;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 0 11px;
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.075);
  border: 1px solid rgba(255, 255, 255, 0.13);
  border-radius: 4px;
  cursor: pointer;
}
.browse-btn span { flex: 1; text-align: left; }
.browse-btn:hover { border-color: var(--primary); }
.recent-section { margin-top: 22px; }
.workspace-list {
  display: block;
  width: 100%;
  margin: 0;
  padding: 0;
  list-style: none;
}
.workspace-list > li {
  display: block;
  width: 100%;
  margin: 0;
  padding: 0;
}
.recent-row {
  width: 100%;
  height: 34px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 8px;
  color: var(--text-secondary);
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
.recent-row:hover { color: var(--text-primary); background: rgba(255, 255, 255, 0.06); }
.recent-row span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 11px; }
.reset-btn {
  width: 100%;
  height: 34px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin-top: 0;
  padding: 0 10px;
  color: var(--text-secondary);
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}
.reset-btn:hover:not(:disabled) { color: var(--text-primary); background: rgba(255, 255, 255, 0.06); }
.reset-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.reset-action { margin-top: 14px; }
.directory-browser { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.browser-toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 48px;
  padding: 7px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  box-sizing: border-box;
}
.browser-toolbar code {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-secondary);
  font-size: 11px;
}
.directory-list { flex: 1; min-height: 0; overflow-y: auto; padding: 8px; }
.list-section + .list-section { margin-top: 12px; }
.list-section-label {
  display: block;
  height: 24px;
  padding: 0 8px;
  color: var(--text-secondary);
  font-size: 11px;
  line-height: 24px;
}
.directory-row {
  width: 100%;
  height: 36px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 9px;
  color: var(--text-primary);
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  text-align: left;
}
.directory-row:hover { background: rgba(255, 255, 255, 0.08); }
.directory-row span { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; }
.directory-row > svg:first-child { color: #fbbf24; }
.root-row > svg:first-child { color: var(--text-secondary); }
.create-folder-row {
  width: 100%;
  min-height: 36px;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 3px 5px 3px 9px;
  background: rgba(255, 255, 255, 0.055);
  border: 1px solid color-mix(in srgb, var(--primary) 55%, transparent);
  border-radius: 4px;
}
.create-folder-row > svg:first-child { flex-shrink: 0; color: #fbbf24; }
.create-folder-row input {
  min-width: 0;
  flex: 1;
  height: 28px;
  padding: 0 5px;
  color: var(--text-primary);
  background: transparent;
  border: none;
  outline: none;
  font: inherit;
  font-size: 12px;
}
.create-folder-row input::placeholder { color: var(--text-secondary); }
.create-folder-row .inline-action {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  padding: 0;
  color: var(--text-secondary);
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
.create-folder-row .inline-action:hover:not(:disabled) { color: var(--text-primary); background: rgba(255, 255, 255, 0.08); }
.create-folder-row .inline-action:disabled { opacity: 0.4; cursor: not-allowed; }
.create-folder-error { padding: 5px 8px 6px 32px; color: #fca5a5; font-size: 11px; line-height: 1.35; }
.browser-state {
  min-height: 90px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 12px;
  text-align: center;
}
.browser-state.error { color: #fca5a5; padding: 0 14px; }
.browser-actions {
  min-height: 52px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 0 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}
.browser-actions button {
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 11px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}
.browser-actions button:disabled { opacity: 0.45; cursor: not-allowed; }
.workspace-panel .secondary-btn { color: var(--text-secondary); background: rgba(255, 255, 255, 0.07); }
.workspace-panel .primary-btn { color: #fff; background: var(--primary); }
.workspace-panel > footer {
  height: 44px;
  display: flex;
  align-items: center;
  gap: 7px;
  flex-shrink: 0;
  padding: 0 16px;
  color: var(--text-secondary);
  border-top: 1px solid rgba(255, 255, 255, 0.09);
  font-size: 11px;
}
.workspace-panel .spin { animation: spin 800ms linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 767px) {
  .workspace-panel {
    position: fixed;
    inset: 0 0 0 auto;
    z-index: 500;
    width: min(88vw, 332px);
  }
}
</style>
