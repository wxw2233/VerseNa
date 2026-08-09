<template>
  <section
    class="pet-editor"
    @pointerover="showPetTooltip"
    @pointerout="hidePetTooltip"
    @focusin="showPetTooltip"
    @focusout="hidePetTooltip"
  >
    <div class="editor-heading">
      <div>
        <h3>桌宠动画</h3>
        <p>单帧上传，或用以 001、002…开头命名的 ZIP 整组覆盖。</p>
      </div>
      <button type="button" class="icon-button" data-pet-tooltip="刷新动画帧" aria-label="刷新动画帧" @click="loadAll">
        <RefreshCcw :size="14" />
      </button>
    </div>

    <div class="scale-control">
      <label for="pet-default-scale">桌宠默认大小 <strong>{{ Math.round(scale * 100) }}%</strong></label>
      <input
        id="pet-default-scale"
        v-model.number="scale"
        type="range"
        min="0.6"
        max="1.8"
        step="0.1"
        @change="saveConfig('桌宠大小已保存', true)"
      />
    </div>

    <div v-for="action in actions" :key="action.id" class="action-row">
      <div class="action-name">
        <strong>{{ action.label }}</strong>
        <span>{{ action.id }}</span>
      </div>

      <div class="frame-list">
        <div v-for="filename in frames[action.id] || []" :key="filename" class="frame-item">
          <img :src="frameUrl(filename)" alt="" />
          <button type="button" data-pet-tooltip="删除帧" aria-label="删除帧" @click="deleteFrame(filename)">
            <X :size="12" />
          </button>
        </div>
        <label class="frame-upload" :data-pet-tooltip="'添加' + action.label + '帧'" :aria-label="'添加' + action.label + '帧'">
          <Plus :size="15" />
          <input
            type="file"
            accept="image/png,image/webp,image/jpeg,image/gif"
            multiple
            @change="uploadFrames(action.id, $event)"
          />
        </label>
        <label
          class="frame-upload zip-upload"
          :class="{ busy: uploadingAction === action.id }"
          :data-pet-tooltip="'上传 ZIP 覆盖' + action.label + '帧（文件名以 001、002 开头）'"
          :aria-label="'上传 ZIP 覆盖' + action.label + '帧'"
        >
          <LoaderCircle v-if="uploadingAction === action.id" :size="15" />
          <FileArchive v-else :size="15" />
          <input
            type="file"
            accept=".zip,application/zip"
            :disabled="Boolean(uploadingAction)"
            @change="uploadArchive(action, $event)"
          />
        </label>
        <button
          type="button"
          class="frame-upload placement-button"
          :disabled="!(frames[action.id] || []).length || Boolean(uploadingAction)"
          :data-pet-tooltip="'调整' + action.label + '的位置和大小'"
          :aria-label="'调整' + action.label + '的位置和大小'"
          @click="openPlacementEditor(action)"
        >
          <Move :size="15" />
        </button>
        <button
          type="button"
          class="frame-upload clear-frames"
          :disabled="!(frames[action.id] || []).length || Boolean(uploadingAction)"
          :data-pet-tooltip="'清空' + action.label + '的全部动画帧'"
          :aria-label="'清空' + action.label + '的全部动画帧'"
          @click="deleteActionFrames(action)"
        >
          <Trash2 :size="15" />
        </button>
      </div>

      <div class="action-settings">
        <label class="fps-control" :for="'pet-fps-' + action.id">
          <span>FPS</span>
          <input
            :id="'pet-fps-' + action.id"
            v-model.number="animationSettings[action.id].fps"
            type="number"
            min="1"
            max="60"
            step="1"
            @change="saveConfig('动画设置已保存')"
          />
        </label>
        <select v-model="animationSettings[action.id].mode" :aria-label="action.label + '播放方式'" @change="saveConfig('动画设置已保存')">
          <option value="loop">循环</option>
          <option value="once">单次</option>
          <option value="pingpong">往返</option>
        </select>
        <select
          v-model="animationSettings[action.id].after"
          :aria-label="action.label + '结束行为'"
          :disabled="animationSettings[action.id].mode !== 'once'"
          @change="saveConfig('动画设置已保存')"
        >
          <option value="idle">回到待机</option>
          <option value="hold">停留末帧</option>
        </select>
      </div>
    </div>

    <Teleport to="body">
      <Transition name="placement-dialog">
        <div
          v-if="placementEditor.visible"
          class="placement-overlay"
          role="presentation"
          @pointerdown.self="closePlacementEditor"
        >
          <div class="placement-dialog" role="dialog" aria-modal="true" :aria-label="placementEditor.action?.label + '动画位置调整'">
            <header class="placement-header">
              <div>
                <h3>{{ placementEditor.action?.label }}动画调整</h3>
                <span>{{ placementEditor.filename }}</span>
              </div>
              <button type="button" class="dialog-icon-button" title="关闭" aria-label="关闭" @click="closePlacementEditor">
                <X :size="17" />
              </button>
            </header>

            <div
              class="placement-workspace"
              :class="{ dragging: placementEditor.dragging }"
              @pointerdown="startPlacementDrag"
              @wheel.prevent="zoomPlacement"
            >
              <div ref="placementPreviewRef" class="placement-preview">
                <img :src="placementEditor.previewUrl" :style="placementPreviewStyle" alt="" draggable="false" />
                <div class="placement-grid" aria-hidden="true"></div>
                <span class="placement-center" aria-hidden="true"></span>
              </div>
            </div>

            <div class="placement-controls">
              <label for="pet-placement-scale">
                <span>缩放</span>
                <strong>{{ Math.round(placementEditor.draft.scale * 100) }}%</strong>
              </label>
              <input
                id="pet-placement-scale"
                v-model.number="placementEditor.draft.scale"
                type="range"
                min="0.25"
                max="3"
                step="0.01"
              />
              <div class="placement-position">
                <span>X {{ Math.round(placementEditor.draft.x * 100) }}</span>
                <span>Y {{ Math.round(placementEditor.draft.y * 100) }}</span>
              </div>
            </div>

            <footer class="placement-actions">
              <button type="button" class="dialog-icon-button reset-placement" title="重置位置和缩放" aria-label="重置位置和缩放" @click="resetPlacement">
                <RotateCcw :size="16" />
              </button>
              <span class="placement-action-spacer"></span>
              <button type="button" class="dialog-button secondary" @click="closePlacementEditor">取消</button>
              <button type="button" class="dialog-button primary" @click="savePlacement">保存调整</button>
            </footer>
          </div>
        </div>
      </Transition>
    </Teleport>

    <Teleport to="body">
      <Transition name="pet-tooltip">
        <div
          v-if="petTooltip.visible"
          ref="petTooltipRef"
          class="pet-floating-tooltip"
          :class="'is-' + petTooltip.placement"
          :style="{ left: petTooltip.left + 'px', top: petTooltip.top + 'px' }"
          role="tooltip"
        >
          {{ petTooltip.text }}
        </div>
      </Transition>
    </Teleport>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { FileArchive, LoaderCircle, Move, Plus, RefreshCcw, RotateCcw, Trash2, X } from 'lucide-vue-next'
import { useToast } from '../../composables/useToast'

const props = defineProps({
  packId: { type: String, required: true },
  themeId: { type: String, default: '' },
})

const toast = useToast()
const actions = [
  { id: 'idle', label: '待机' },
  { id: 'blink', label: '眨眼' },
  { id: 'thinking', label: '思考中' },
  { id: 'tool', label: '调用工具' },
  { id: 'working', label: '生成回复' },
  { id: 'walk', label: '走路' },
  { id: 'jump', label: '跳跃' },
  { id: 'wave', label: '挥手' },
]
const defaultAnimations = {
  idle: { fps: 7, mode: 'loop', after: 'idle' },
  blink: { fps: 33, mode: 'once', after: 'idle' },
  thinking: { fps: 20, mode: 'loop', after: 'idle' },
  tool: { fps: 20, mode: 'loop', after: 'idle' },
  working: { fps: 20, mode: 'loop', after: 'idle' },
  walk: { fps: 20, mode: 'loop', after: 'idle' },
  jump: { fps: 12, mode: 'once', after: 'idle' },
  wave: { fps: 27, mode: 'loop', after: 'idle' },
}
const defaultPlacement = { x: 0, y: 0, scale: 1 }
const frames = ref(Object.fromEntries(actions.map(action => [action.id, []])))
const animationSettings = ref(normalizeAnimations())
const placementSettings = ref(normalizePlacements())
const frameRevision = ref(Date.now())
const scale = ref(1)
const uploadingAction = ref('')
const placementPreviewRef = ref(null)
const petTooltipRef = ref(null)
const petTooltip = reactive({ visible: false, text: '', left: 0, top: 0, placement: 'above' })
const placementEditor = reactive({
  visible: false,
  action: null,
  filename: '',
  previewUrl: '',
  dragging: false,
  draft: { ...defaultPlacement },
})
const placementPreviewStyle = computed(() => ({
  transform: `translate(${placementEditor.draft.x * 100}%, ${placementEditor.draft.y * 100}%) scale(${placementEditor.draft.scale})`,
}))
let placementDrag = null
let petTooltipTarget = null

function showPetTooltip(event) {
  const target = event.target?.closest?.('[data-pet-tooltip]')
  if (!target || target === petTooltipTarget || !event.currentTarget.contains(target)) return
  petTooltipTarget = target
  const rect = target.getBoundingClientRect()
  petTooltip.text = target.dataset.petTooltip || ''
  petTooltip.placement = rect.top >= 48 ? 'above' : 'below'
  petTooltip.left = rect.left + rect.width / 2
  petTooltip.top = petTooltip.placement === 'above' ? rect.top - 8 : rect.bottom + 8
  petTooltip.visible = Boolean(petTooltip.text)

  nextTick(() => {
    if (target !== petTooltipTarget || !petTooltipRef.value) return
    const halfWidth = petTooltipRef.value.offsetWidth / 2
    petTooltip.left = Math.min(
      window.innerWidth - halfWidth - 10,
      Math.max(halfWidth + 10, rect.left + rect.width / 2),
    )
  })
}

function hidePetTooltip(event) {
  if (petTooltipTarget?.contains(event.relatedTarget)) return
  petTooltipTarget = null
  petTooltip.visible = false
}

function normalizeAnimations(value = {}) {
  return Object.fromEntries(actions.map(action => {
    const defaults = defaultAnimations[action.id]
    const source = value?.[action.id] || {}
    const fps = Number(source.fps)
    return [action.id, {
      fps: Number.isFinite(fps) ? Math.min(60, Math.max(1, Math.round(fps))) : defaults.fps,
      mode: ['loop', 'once', 'pingpong'].includes(source.mode) ? source.mode : defaults.mode,
      after: ['idle', 'hold'].includes(source.after) ? source.after : defaults.after,
    }]
  }))
}

function normalizePlacements(value = {}) {
  return Object.fromEntries(actions.map(action => {
    const source = value?.[action.id] || {}
    const x = Number(source.x)
    const y = Number(source.y)
    const placementScale = Number(source.scale)
    return [action.id, {
      x: Number.isFinite(x) ? Math.min(1, Math.max(-1, x)) : 0,
      y: Number.isFinite(y) ? Math.min(1, Math.max(-1, y)) : 0,
      scale: Number.isFinite(placementScale) ? Math.min(3, Math.max(0.25, placementScale)) : 1,
    }]
  }))
}

function effectiveThemeId() {
  return props.themeId || props.packId
}

function frameUrl(filename) {
  return '/api/themes/' + encodeURIComponent(effectiveThemeId()) + '/assets/' + encodeURIComponent(filename) + '?t=' + frameRevision.value
}

function notifyPetUpdate() {
  const detail = { theme: effectiveThemeId(), revision: Date.now() }
  window.dispatchEvent(new CustomEvent('versena:pet-config', { detail }))
  window.electronAPI?.setPetConfig?.(detail)
}

async function loadAll() {
  if (!props.packId) return
  try {
    const [framesResponse, configResponse] = await Promise.all([
      fetch('/api/themepacks/' + encodeURIComponent(props.packId) + '/pet-assets'),
      fetch('/api/themepacks/' + encodeURIComponent(props.packId) + '/pet-config'),
    ])
    if (!framesResponse.ok || !configResponse.ok) throw new Error('HTTP ' + (!framesResponse.ok ? framesResponse.status : configResponse.status))
    frames.value = await framesResponse.json()
    const config = await configResponse.json()
    scale.value = Number(config.scale || 1)
    animationSettings.value = normalizeAnimations(config.animations)
    placementSettings.value = normalizePlacements(config.placements)
    frameRevision.value = Date.now()
  } catch (error) {
    toast.error('桌宠素材加载失败：' + error.message)
  }
}

async function saveConfig(message, resize = false) {
  try {
    const response = await fetch('/api/themepacks/' + encodeURIComponent(props.packId) + '/pet-config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scale: scale.value, animations: animationSettings.value, placements: placementSettings.value }),
    })
    const result = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(result.detail || '桌宠设置保存失败')
    if (!result.animations || !result.placements) throw new Error('当前后端未加载最新桌宠配置接口，请重启 VerseNa 后端')
  } catch (error) {
    toast.error(error.message || '桌宠设置保存失败')
    await loadAll()
    return false
  }
  notifyPetUpdate()
  if (resize) {
    window.dispatchEvent(new CustomEvent('versena:pet-scale', {
      detail: { theme: effectiveThemeId(), scale: scale.value },
    }))
    window.electronAPI?.resizePet?.(scale.value)
  }
  toast.success(message)
  return true
}

function openPlacementEditor(action) {
  const actionFrames = frames.value[action.id] || []
  const filename = actionFrames.find(name => /-001\.[^.]+$/i.test(name)) || actionFrames[0]
  if (!filename) return
  placementEditor.action = action
  placementEditor.filename = filename
  placementEditor.previewUrl = frameUrl(filename)
  placementEditor.draft = { ...(placementSettings.value[action.id] || defaultPlacement) }
  placementEditor.visible = true
}

function closePlacementEditor() {
  stopPlacementDrag()
  placementEditor.visible = false
}

function resetPlacement() {
  placementEditor.draft = { ...defaultPlacement }
}

function clampPlacement(value) {
  return Math.min(1, Math.max(-1, value))
}

function startPlacementDrag(event) {
  if (event.button !== 0) return
  event.preventDefault()
  const rect = placementPreviewRef.value?.getBoundingClientRect()
  if (!rect) return
  placementDrag = {
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    originX: placementEditor.draft.x,
    originY: placementEditor.draft.y,
    width: Math.max(1, rect.width),
    height: Math.max(1, rect.height),
  }
  placementEditor.dragging = true
  window.addEventListener('pointermove', movePlacementDrag)
  window.addEventListener('pointerup', stopPlacementDrag, { once: true })
  window.addEventListener('pointercancel', stopPlacementDrag, { once: true })
}

function movePlacementDrag(event) {
  if (!placementDrag || event.pointerId !== placementDrag.pointerId) return
  placementEditor.draft.x = clampPlacement(placementDrag.originX + (event.clientX - placementDrag.startX) / placementDrag.width)
  placementEditor.draft.y = clampPlacement(placementDrag.originY + (event.clientY - placementDrag.startY) / placementDrag.height)
}

function stopPlacementDrag() {
  placementDrag = null
  placementEditor.dragging = false
  window.removeEventListener('pointermove', movePlacementDrag)
  window.removeEventListener('pointerup', stopPlacementDrag)
  window.removeEventListener('pointercancel', stopPlacementDrag)
}

function zoomPlacement(event) {
  const direction = event.deltaY < 0 ? 1 : -1
  placementEditor.draft.scale = Math.min(3, Math.max(0.25, placementEditor.draft.scale + direction * 0.05))
}

async function savePlacement() {
  const actionId = placementEditor.action?.id
  if (!actionId) return
  placementSettings.value[actionId] = { ...placementEditor.draft }
  const saved = await saveConfig(placementEditor.action.label + '位置已保存')
  if (saved) closePlacementEditor()
}

function handlePlacementKeydown(event) {
  if (event.key === 'Escape' && placementEditor.visible) closePlacementEditor()
}

async function uploadFrames(action, event) {
  const files = Array.from(event.target.files || [])
  for (const file of files) {
    const formData = new FormData()
    formData.append('file', file)
    const response = await fetch('/api/themepacks/' + encodeURIComponent(props.packId) + '/pet-assets/' + action, {
      method: 'POST',
      body: formData,
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      toast.error(error.detail || '动画帧上传失败')
      break
    }
  }
  event.target.value = ''
  await loadAll()
  notifyPetUpdate()
}

async function uploadArchive(action, event) {
  const file = event.target.files?.[0]
  if (!file) return
  if (!confirm('使用此 ZIP 覆盖「' + action.label + '」的全部动画帧？')) {
    event.target.value = ''
    return
  }
  uploadingAction.value = action.id
  try {
    const formData = new FormData()
    formData.append('file', file)
    const response = await fetch('/api/themepacks/' + encodeURIComponent(props.packId) + '/pet-assets/' + action.id + '/zip', {
      method: 'POST',
      body: formData,
    })
    const result = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(result.detail || 'ZIP 动画上传失败')
    await loadAll()
    notifyPetUpdate()
    toast.success('已用 ZIP 覆盖' + action.label + '动画，共 ' + result.count + ' 帧')
  } catch (error) {
    toast.error(error.message || 'ZIP 动画上传失败')
  } finally {
    event.target.value = ''
    uploadingAction.value = ''
  }
}

async function deleteFrame(filename) {
  if (!confirm('确定删除动画帧「' + filename + '」？')) return
  const response = await fetch('/api/themepacks/' + encodeURIComponent(props.packId) + '/pet-assets/' + encodeURIComponent(filename), { method: 'DELETE' })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    toast.error(error.detail || '动画帧删除失败')
    return
  }
  await loadAll()
  notifyPetUpdate()
}

async function deleteActionFrames(action) {
  const count = (frames.value[action.id] || []).length
  if (!count || !confirm('确定删除「' + action.label + '」的全部 ' + count + ' 帧动画？')) return
  try {
    const response = await fetch('/api/themepacks/' + encodeURIComponent(props.packId) + '/pet-assets/' + action.id + '/all', {
      method: 'DELETE',
    })
    const result = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(result.detail || '批量删除动画帧失败')
    await loadAll()
    notifyPetUpdate()
    toast.success('已清空' + action.label + '动画，共删除 ' + result.deleted + ' 帧')
  } catch (error) {
    toast.error(error.message || '批量删除动画帧失败')
  }
}

watch(() => [props.packId, props.themeId], loadAll, { immediate: true })
window.addEventListener('keydown', handlePlacementKeydown)
onBeforeUnmount(() => {
  stopPlacementDrag()
  window.removeEventListener('keydown', handlePlacementKeydown)
})
</script>

<style scoped>
.pet-editor { margin-top:24px; padding-top:20px; border-top:1px solid rgba(255,255,255,.10); color:var(--text-primary); }
.editor-heading { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; }
.editor-heading h3 { margin:0 0 4px; color:var(--text-primary); font-size:15px; }
.editor-heading p { margin:0; color:var(--text-secondary); font-size:12px; }
.icon-button { width:30px; height:30px; flex:0 0 30px; display:grid; place-items:center; padding:0; color:var(--text-secondary); background:transparent; border:1px solid rgba(255,255,255,.16); border-radius:6px; cursor:pointer; }
.icon-button:hover { color:var(--primary); border-color:var(--primary); }
.scale-control { margin:14px 0; padding:10px 12px; background:rgba(20,20,40,.45); border:1px solid rgba(255,255,255,.12); border-radius:6px; }
.scale-control label { display:flex; align-items:center; justify-content:space-between; gap:12px; margin:0; color:var(--text-secondary); font-size:12px; }
.scale-control strong { color:var(--primary); }
.scale-control > input { width:100%; margin-top:7px; padding:0; box-shadow:none; accent-color:var(--primary); }
.action-row { min-height:68px; display:grid; grid-template-columns:70px minmax(0,1fr) 288px; align-items:center; gap:12px; border-top:1px solid rgba(255,255,255,.10); }
.action-name { display:flex; flex-direction:column; gap:2px; }
.action-name strong { color:var(--text-primary); font-size:13px; }
.action-name span { color:var(--text-secondary); font-size:10px; }
.frame-list { min-width:0; display:flex; align-items:center; gap:7px; overflow-x:auto; padding:9px 0; scrollbar-width:thin; }
.frame-item { position:relative; width:48px; height:48px; flex:0 0 48px; overflow:hidden; background:rgba(20,20,40,.48); border:1px solid rgba(255,255,255,.16); border-radius:6px; }
.frame-item img { width:100%; height:100%; object-fit:contain; }
.frame-item button { position:absolute; top:2px; right:2px; width:17px; height:17px; display:grid; place-items:center; padding:0; color:rgba(255,255,255,.78); background:rgba(12,14,24,.78); border:1px solid rgba(255,255,255,.16); border-radius:4px; cursor:pointer; opacity:.82; transition:color .15s,background .15s,border-color .15s; }
.frame-item button:hover { color:#fff; background:rgba(220,70,90,.82); border-color:rgba(255,160,170,.65); }
.frame-upload { width:48px; height:48px; flex:0 0 48px; display:grid; place-items:center; margin:0; color:var(--primary); background:rgba(20,20,40,.22); border:1px dashed color-mix(in srgb,var(--primary) 70%,transparent); border-radius:6px; cursor:pointer; transition:background .15s,border-color .15s; }
.frame-upload:hover { background:color-mix(in srgb,var(--primary) 10%,transparent); }
.frame-upload input { display:none; }
.zip-upload { color:var(--text-secondary); border-style:solid; border-color:rgba(255,255,255,.18); }
.zip-upload:hover { color:var(--primary); border-color:color-mix(in srgb,var(--primary) 70%,transparent); }
.zip-upload.busy { color:var(--primary); cursor:wait; }
.zip-upload.busy svg { animation:pet-upload-spin .8s linear infinite; }
.placement-button { padding:0; color:var(--text-secondary); border-style:solid; border-color:rgba(255,255,255,.18); }
.placement-button:hover:not(:disabled) { color:var(--primary); border-color:color-mix(in srgb,var(--primary) 70%,transparent); }
.placement-button:disabled { opacity:.32; cursor:not-allowed; }
.clear-frames { padding:0; color:var(--text-secondary); border-style:solid; border-color:rgba(255,255,255,.18); }
.clear-frames:hover:not(:disabled) { color:#ff7f91; background:rgba(220,70,90,.12); border-color:rgba(255,110,130,.48); }
.clear-frames:disabled { opacity:.32; cursor:not-allowed; }
.pet-floating-tooltip { position:fixed; z-index:3000; width:max-content; max-width:min(280px,calc(100vw - 20px)); box-sizing:border-box; padding:5px 8px; color:#fff; background:rgba(8,10,16,.96); border:1px solid rgba(255,255,255,.16); border-radius:4px; box-shadow:0 6px 18px rgba(0,0,0,.32); font-size:11px; line-height:1.45; text-align:center; white-space:normal; pointer-events:none; }
.pet-floating-tooltip.is-above { transform:translate(-50%,-100%); }
.pet-floating-tooltip.is-below { transform:translateX(-50%); }
.pet-tooltip-enter-active,.pet-tooltip-leave-active { transition:opacity .12s ease; }
.pet-tooltip-enter-from,.pet-tooltip-leave-to { opacity:0; }
.action-settings { display:grid; grid-template-columns:70px 90px 116px; align-items:center; gap:6px; }
.action-settings select,.fps-control { height:30px; box-sizing:border-box; margin:0; color:var(--text-primary); background:rgba(20,20,40,.58); border:1px solid rgba(255,255,255,.18); border-radius:6px; color-scheme:dark; }
.action-settings select { min-width:0; padding:0 7px; font-size:12px; outline:none; }
.action-settings select:focus { border-color:var(--primary); box-shadow:0 0 0 2px color-mix(in srgb,var(--primary) 18%,transparent); }
.action-settings select:disabled { opacity:.45; }
.fps-control { display:grid; grid-template-columns:auto 1fr; align-items:center; gap:4px; padding:0 5px 0 7px; color:var(--text-secondary); font-size:10px; }
.fps-control input { min-width:0; width:100%; height:100%; box-sizing:border-box; padding:0 5px 0 0; color:var(--text-primary); background:transparent; border:0; box-shadow:none; outline:none; text-align:right; font-size:12px; font-variant-numeric:tabular-nums; }
.fps-control:focus-within { border-color:var(--primary); box-shadow:0 0 0 2px color-mix(in srgb,var(--primary) 18%,transparent); }
.fps-control input::-webkit-inner-spin-button,.fps-control input::-webkit-outer-spin-button { opacity:.6; }
.placement-overlay { position:fixed; z-index:1000; inset:0; display:grid; place-items:center; padding:18px; box-sizing:border-box; background:rgba(6,8,14,.72); backdrop-filter:blur(5px); }
.placement-dialog { width:min(700px,100%); max-height:calc(100vh - 36px); display:flex; flex-direction:column; overflow:auto; color:var(--text-primary); background:rgba(18,20,30,.98); border:1px solid rgba(255,255,255,.16); border-radius:8px; box-shadow:0 18px 48px rgba(0,0,0,.44); }
.placement-header { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:13px 14px; border-bottom:1px solid rgba(255,255,255,.10); }
.placement-header h3 { margin:0 0 2px; font-size:14px; color:var(--text-primary); }
.placement-header span { display:block; max-width:320px; overflow:hidden; color:var(--text-secondary); font-size:10px; text-overflow:ellipsis; white-space:nowrap; }
.dialog-icon-button { width:30px; height:30px; flex:0 0 30px; display:grid; place-items:center; padding:0; color:var(--text-secondary); background:transparent; border:1px solid rgba(255,255,255,.16); border-radius:6px; cursor:pointer; }
.dialog-icon-button:hover { color:var(--primary); border-color:var(--primary); }
.placement-workspace { position:relative; min-height:min(470px,calc(100vh - 250px)); display:grid; place-items:center; flex:0 0 auto; overflow:hidden; margin:16px; background:rgba(8,10,18,.62); border:1px solid rgba(255,255,255,.12); border-radius:6px; cursor:grab; touch-action:none; user-select:none; }
.placement-workspace.dragging { cursor:grabbing; }
.placement-preview { position:relative; width:min(260px,46%); aspect-ratio:190/230; overflow:visible; background:rgba(255,255,255,.025); border:1px solid rgba(255,255,255,.18); border-radius:4px; }
.placement-preview img { position:absolute; z-index:1; inset:0; width:100%; height:100%; object-fit:contain; transform-origin:center; pointer-events:none; user-select:none; -webkit-user-drag:none; }
.placement-grid { position:absolute; z-index:2; inset:0; pointer-events:none; background-image:linear-gradient(to right,transparent calc(33.333% - .5px),rgba(255,255,255,.28) 33.333%,transparent calc(33.333% + .5px),transparent calc(66.666% - .5px),rgba(255,255,255,.28) 66.666%,transparent calc(66.666% + .5px)),linear-gradient(to bottom,transparent calc(33.333% - .5px),rgba(255,255,255,.28) 33.333%,transparent calc(33.333% + .5px),transparent calc(66.666% - .5px),rgba(255,255,255,.28) 66.666%,transparent calc(66.666% + .5px)); box-shadow:inset 0 0 0 1px rgba(255,255,255,.10); }
.placement-center { position:absolute; z-index:3; left:50%; top:50%; width:9px; height:9px; border:1px solid color-mix(in srgb,var(--primary) 75%,white); border-radius:50%; transform:translate(-50%,-50%); pointer-events:none; box-shadow:0 0 0 2px rgba(0,0,0,.35); }
.placement-controls { margin:0 16px 14px; padding:10px 12px; background:rgba(8,10,18,.42); border:1px solid rgba(255,255,255,.10); border-radius:6px; }
.placement-controls label { display:flex; align-items:center; justify-content:space-between; color:var(--text-secondary); font-size:12px; }
.placement-controls strong { color:var(--primary); }
.placement-controls > input { width:100%; margin:8px 0 5px; padding:0; box-shadow:none; accent-color:var(--primary); }
.placement-position { display:flex; justify-content:space-between; color:var(--text-secondary); font-size:10px; font-variant-numeric:tabular-nums; }
.placement-actions { display:flex; align-items:center; gap:8px; padding:12px 14px; border-top:1px solid rgba(255,255,255,.10); }
.placement-action-spacer { flex:1; }
.dialog-button { min-height:32px; padding:0 13px; border-radius:6px; cursor:pointer; font-size:12px; }
.dialog-button.secondary { color:var(--text-primary); background:transparent; border:1px solid rgba(255,255,255,.18); }
.dialog-button.primary { color:#fff; background:var(--primary); border:1px solid var(--primary); }
.placement-dialog-enter-active,.placement-dialog-leave-active { transition:opacity .16s ease; }
.placement-dialog-enter-active .placement-dialog,.placement-dialog-leave-active .placement-dialog { transition:transform .16s ease,opacity .16s ease; }
.placement-dialog-enter-from,.placement-dialog-leave-to { opacity:0; }
.placement-dialog-enter-from .placement-dialog,.placement-dialog-leave-to .placement-dialog { opacity:0; transform:translateY(8px); }
@media (max-width:760px) { .action-row { grid-template-columns:62px minmax(0,1fr); padding:8px 0; } .action-settings { grid-column:2; justify-content:start; } }
@media (max-width:560px) { .action-settings { grid-template-columns:64px 82px minmax(96px,1fr); width:100%; } .placement-workspace { min-height:min(400px,calc(100vh - 250px)); margin:12px; } .placement-preview { width:min(210px,54%); } .placement-controls { margin-inline:12px; } }
@keyframes pet-upload-spin { to { transform:rotate(360deg); } }
</style>
