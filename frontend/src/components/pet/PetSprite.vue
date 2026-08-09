<template>
  <div class="pet-sprite" :class="'pet-' + currentAction" :style="{ '--sprite-scale': spriteScale }">
    <div class="pet-stage">
      <img
        v-if="previousFrameUrl"
        :key="'previous-' + transitionId"
        class="pet-frame pet-frame-previous"
        :class="{ transitioning: transitionActive }"
        :src="previousFrameUrl"
        :style="frameStyle(previousFrameUrl)"
        alt=""
        draggable="false"
      />
      <img
        v-if="displayedFrameUrl"
        :key="'current-' + displayedFrameUrl + '-' + transitionId"
        class="pet-frame pet-frame-current"
        :class="{ transitioning: transitionActive }"
        :src="displayedFrameUrl"
        :style="frameStyle(displayedFrameUrl)"
        alt=""
        draggable="false"
      />
      <div v-if="!frameLoaded" class="pet-placeholder" aria-hidden="true">
        <div class="pet-aura"></div>
        <div class="pet-head"><span class="pet-eye left"></span><span class="pet-eye right"></span><span class="pet-mouth"></span></div>
        <div class="pet-body"></div>
      </div>
    </div>
    <span class="pet-signal" aria-hidden="true"></span>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  state: { type: String, default: 'idle' },
  theme: { type: String, default: 'default' },
  scale: { type: Number, default: 1 },
  configRevision: { type: Number, default: 0 },
})

const actions = ['idle', 'blink', 'thinking', 'tool', 'working', 'walk', 'jump', 'wave']
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
const minimumActionDuration = {
  idle: 180,
  blink: 0,
  thinking: 320,
  tool: 320,
  working: 320,
  walk: 320,
  jump: 0,
  wave: 320,
}
const crossfadeDuration = 110

const desiredAction = computed(() => {
  if (actions.includes(props.state)) return props.state
  if (props.state === 'done') return 'jump'
  if (props.state === 'speaking') return 'wave'
  return 'idle'
})
const spriteScale = computed(() => String(Math.min(1.8, Math.max(0.6, props.scale))))

const frameFiles = ref({})
const frameIndex = ref(0)
const frameLoaded = ref(false)
const displayedFrameUrl = ref('')
const previousFrameUrl = ref('')
const transitionActive = ref(false)
const transitionId = ref(0)
const loadedTheme = ref(props.theme || 'default')
const assetRevision = ref(Date.now())
const animationSettings = ref(normalizeAnimations())
const placementSettings = ref(normalizePlacements())
const currentAction = ref('idle')
const pendingAction = ref('')
const frameDirection = ref(1)

const frameActions = new Map()
let frameTimer = null
let blinkTimer = null
let transitionTimer = null
let pendingTimer = null
let bridgeTimer = null
let loadGeneration = 0
let frameLoadSequence = 0
let currentActionStartedAt = performance.now()
let crossfadeNextFrame = false
let currentActionFinished = false
let releasedAction = ''

const resolvedFrameAction = computed(() => {
  const fallbacks = {
    thinking: ['thinking', 'walk', 'idle'],
    tool: ['tool', 'walk', 'idle'],
    working: ['working', 'walk', 'idle'],
  }
  const candidates = fallbacks[currentAction.value] || [currentAction.value, 'idle']
  return candidates.find(action => (frameFiles.value[action] || []).length) || currentAction.value
})
const frameUrl = computed(() => {
  const files = frameFiles.value[resolvedFrameAction.value] || []
  if (!files.length) return ''
  return frameAssetUrl(files[frameIndex.value % files.length])
})

function frameAssetUrl(filename, theme = loadedTheme.value, revision = assetRevision.value) {
  return '/api/themes/' + encodeURIComponent(theme) + '/assets/' + encodeURIComponent(filename) + '?petv=' + revision
}

function normalizeAnimations(value = {}) {
  return Object.fromEntries(actions.map(action => {
    const defaults = defaultAnimations[action]
    const source = value?.[action] || {}
    const fps = Number(source.fps)
    return [action, {
      fps: Number.isFinite(fps) ? Math.min(60, Math.max(1, fps)) : defaults.fps,
      mode: ['loop', 'once', 'pingpong'].includes(source.mode) ? source.mode : defaults.mode,
      after: ['idle', 'hold'].includes(source.after) ? source.after : defaults.after,
    }]
  }))
}

function normalizePlacements(value = {}) {
  return Object.fromEntries(actions.map(action => {
    const source = value?.[action] || {}
    const x = Number(source.x)
    const y = Number(source.y)
    const placementScale = Number(source.scale)
    return [action, {
      x: Number.isFinite(x) ? Math.min(1, Math.max(-1, x)) : 0,
      y: Number.isFinite(y) ? Math.min(1, Math.max(-1, y)) : 0,
      scale: Number.isFinite(placementScale) ? Math.min(3, Math.max(0.25, placementScale)) : 1,
    }]
  }))
}

function animationFor(action) {
  return animationSettings.value[action] || defaultAnimations[action] || defaultAnimations.idle
}

function frameDelay(action = resolvedFrameAction.value) {
  return Math.max(17, Math.round(1000 / animationFor(action).fps))
}

function frameStyle(url) {
  const action = frameActions.get(url) || resolvedFrameAction.value
  const placement = placementSettings.value[action] || defaultPlacement
  return {
    transform: `translate(${placement.x * 100}%, ${placement.y * 100}%) scale(${placement.scale})`,
  }
}

function loadImage(url) {
  return new Promise(resolve => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => resolve(null)
    image.src = url
  })
}

async function preloadFrameSet(files, theme, revision, generation) {
  const entries = Object.entries(files).flatMap(([action, filenames]) => (
    filenames.map(filename => ({ action, url: frameAssetUrl(filename, theme, revision) }))
  ))
  frameActions.clear()
  entries.forEach(entry => frameActions.set(entry.url, entry.action))
  for (let start = 0; start < entries.length; start += 6) {
    const batch = entries.slice(start, start + 6)
    await Promise.all(batch.map(entry => loadImage(entry.url)))
    if (generation !== loadGeneration) return
  }
}

function presentFrame(url, generation) {
  const sequence = ++frameLoadSequence
  if (!url) {
    displayedFrameUrl.value = ''
    previousFrameUrl.value = ''
    frameLoaded.value = false
    return
  }
  loadImage(url).then(image => {
    if (!image || generation !== loadGeneration || sequence !== frameLoadSequence) return
    const shouldCrossfade = crossfadeNextFrame && displayedFrameUrl.value && displayedFrameUrl.value !== url
    crossfadeNextFrame = false
    if (shouldCrossfade) {
      previousFrameUrl.value = displayedFrameUrl.value
      transitionActive.value = true
      transitionId.value += 1
      if (transitionTimer) clearTimeout(transitionTimer)
      transitionTimer = setTimeout(() => {
        previousFrameUrl.value = ''
        transitionActive.value = false
        transitionTimer = null
      }, crossfadeDuration)
    }
    displayedFrameUrl.value = url
    frameLoaded.value = true
  })
}

async function loadFrames() {
  const generation = ++loadGeneration
  const theme = props.theme || 'default'
  const revision = Date.now()
  clearPlaybackTimers()
  if (blinkTimer) {
    clearTimeout(blinkTimer)
    blinkTimer = null
  }
  try {
    const [response, configResponse] = await Promise.all([
      fetch('/api/themes/' + encodeURIComponent(theme) + '/pet-assets?t=' + Date.now()),
      fetch('/api/themes/' + encodeURIComponent(theme) + '/pet-config?t=' + Date.now()),
    ])
    if (!response.ok || generation !== loadGeneration) return
    const files = await response.json()
    const config = configResponse.ok ? await configResponse.json() : {}
    if (generation !== loadGeneration) return
    await preloadFrameSet(files, theme, revision, generation)
    if (generation !== loadGeneration) return
    frameFiles.value = files
    loadedTheme.value = theme
    assetRevision.value = revision
    animationSettings.value = normalizeAnimations(config.animations)
    placementSettings.value = normalizePlacements(config.placements)
  } catch {
    return
  }
  currentAction.value = desiredAction.value
  pendingAction.value = ''
  releasedAction = ''
  currentActionFinished = false
  currentActionStartedAt = performance.now()
  resetPlayback()
  presentFrame(frameUrl.value, generation)
  restartTimer()
  scheduleBlink()
}

function clearPlaybackTimers() {
  for (const timer of [frameTimer, pendingTimer, bridgeTimer]) {
    if (timer) clearTimeout(timer)
  }
  frameTimer = null
  pendingTimer = null
  bridgeTimer = null
}

function restartTimer() {
  if (frameTimer) clearTimeout(frameTimer)
  frameTimer = null
  const files = frameFiles.value[resolvedFrameAction.value] || []
  if (!files.length || files.length === 1) {
    frameTimer = setTimeout(
      completeCurrentAction,
      Math.max(frameDelay(), minimumActionDuration[currentAction.value] || 0),
    )
    return
  }
  frameTimer = setTimeout(advanceFrame, frameDelay())
}

function advanceFrame() {
  frameTimer = null
  const files = frameFiles.value[resolvedFrameAction.value] || []
  if (files.length <= 1) return
  const settings = animationFor(currentAction.value)
  let reachedBoundary = false
  if (settings.mode === 'pingpong') {
    let next = frameIndex.value + frameDirection.value
    if (next >= files.length) {
      frameDirection.value = -1
      next = files.length - 2
    } else if (next < 0) {
      frameDirection.value = 1
      next = 1
      reachedBoundary = true
    }
    frameIndex.value = next
  } else if (settings.mode === 'once') {
    if (frameIndex.value < files.length - 1) {
      frameIndex.value += 1
    } else {
      completeCurrentAction()
      return
    }
  } else {
    frameIndex.value = (frameIndex.value + 1) % files.length
    reachedBoundary = frameIndex.value === 0
  }
  if (reachedBoundary) completeCurrentAction()
  if (!frameTimer) restartTimer()
}

function resetPlayback() {
  frameDirection.value = 1
  frameIndex.value = 0
}

function switchAction(nextAction) {
  if (!actions.includes(nextAction)) nextAction = 'idle'
  if (bridgeTimer) clearTimeout(bridgeTimer)
  bridgeTimer = null
  if (pendingTimer) clearTimeout(pendingTimer)
  pendingTimer = null
  pendingAction.value = ''
  currentAction.value = nextAction
  currentActionStartedAt = performance.now()
  currentActionFinished = false
  crossfadeNextFrame = true
  resetPlayback()
  presentFrame(frameUrl.value, loadGeneration)
  restartTimer()
}

function transitionTo(nextAction) {
  if (nextAction === currentAction.value) {
    pendingAction.value = ''
    return
  }
  switchAction(nextAction)
}

function requestAction(nextAction) {
  if (bridgeTimer) {
    clearTimeout(bridgeTimer)
    bridgeTimer = null
  }
  if (nextAction !== releasedAction) releasedAction = ''
  // 工具调用是一次明确的工作事件，不能被随后到来的 working/idle 状态覆盖。
  if (nextAction !== 'tool' && pendingAction.value === 'tool' && currentAction.value !== 'tool') {
    return
  }
  if (nextAction === currentAction.value) {
    pendingAction.value = ''
    if (pendingTimer) clearTimeout(pendingTimer)
    pendingTimer = null
    return
  }
  pendingAction.value = nextAction
  if (currentActionFinished) {
    transitionTo(nextAction)
    return
  }
  if (!frameTimer) restartTimer()
}

function completeCurrentAction() {
  if (frameTimer) clearTimeout(frameTimer)
  frameTimer = null
  currentActionFinished = true
  const settings = animationFor(currentAction.value)
  const desired = desiredAction.value === releasedAction ? 'idle' : desiredAction.value
  const nextAction = pendingAction.value || desired
  if (nextAction !== currentAction.value) {
    transitionTo(nextAction)
  } else if (settings.mode === 'once' && currentAction.value !== 'idle' && settings.after === 'idle') {
    releasedAction = currentAction.value
    transitionTo('idle')
  } else if (settings.after !== 'hold') {
    currentActionFinished = false
    resetPlayback()
    restartTimer()
  }
}

function scheduleBlink() {
  if (blinkTimer) clearTimeout(blinkTimer)
  blinkTimer = setTimeout(() => {
    blinkTimer = null
    const frames = frameFiles.value.blink || []
    if (currentAction.value === 'idle' && !pendingAction.value && frames.length > 1) {
      requestAction('blink')
    }
    scheduleBlink()
  }, 4500 + Math.round(Math.random() * 2500))
}

watch(() => props.theme, loadFrames, { immediate: true })
watch(desiredAction, requestAction)
watch(() => props.configRevision, loadFrames)
watch(frameUrl, url => presentFrame(url, loadGeneration))

function handleConfigUpdate(event) {
  if (!event.detail?.theme || event.detail.theme === props.theme) loadFrames()
}

window.addEventListener('versena:pet-config', handleConfigUpdate)
onBeforeUnmount(() => {
  ++loadGeneration
  ++frameLoadSequence
  clearPlaybackTimers()
  if (blinkTimer) clearTimeout(blinkTimer)
  if (transitionTimer) clearTimeout(transitionTimer)
  window.removeEventListener('versena:pet-config', handleConfigUpdate)
})
</script>

<style scoped>
.pet-sprite { position:relative; width:100%; height:100%; display:grid; place-items:stretch; padding:8px 10px 4px; box-sizing:border-box; }
.pet-stage { position:relative; width:100%; height:100%; overflow:visible; }
.pet-frame { position:absolute; inset:0; display:block; width:100%; height:100%; object-fit:contain; transform-origin:center; pointer-events:none; user-select:none; -webkit-user-drag:none; filter:drop-shadow(0 8px 12px rgba(0,0,0,.28)); }
.pet-frame-current { z-index:2; }
.pet-frame-previous { z-index:1; }
.pet-frame-current.transitioning { animation:pet-frame-in 110ms ease-out both; }
.pet-frame-previous.transitioning { animation:pet-frame-out 110ms ease-out both; }
.pet-placeholder { position:absolute; left:50%; bottom:0; width:126px; height:178px; display:grid; place-items:end center; filter:drop-shadow(0 8px 12px rgba(0,0,0,.28)); transform-origin:center bottom; animation:pet-idle 1.8s ease-in-out infinite; }
.pet-aura { position:absolute; width:104px; height:104px; top:22px; border-radius:50%; background:color-mix(in srgb,var(--primary) 32%,transparent); filter:blur(16px); opacity:.7; }
.pet-head { position:absolute; top:28px; width:88px; height:84px; border:3px solid rgba(255,255,255,.84); border-radius:46% 46% 42% 42%; background:color-mix(in srgb,var(--primary) 66%,#172033); box-shadow:inset 0 -8px 0 rgba(0,0,0,.1); }
.pet-head:before,.pet-head:after { content:''; position:absolute; top:-22px; width:26px; height:30px; border:3px solid rgba(255,255,255,.84); background:color-mix(in srgb,var(--primary) 66%,#172033); z-index:-1; }
.pet-head:before { left:5px; transform:rotate(-24deg); border-radius:8px 18px 2px 18px; } .pet-head:after { right:5px; transform:rotate(24deg); border-radius:18px 8px 18px 2px; }
.pet-eye { position:absolute; top:36px; width:9px; height:13px; border-radius:50%; background:#fff; box-shadow:0 0 6px rgba(255,255,255,.65); } .pet-eye.left { left:24px; } .pet-eye.right { right:24px; }
.pet-mouth { position:absolute; left:38px; bottom:17px; width:12px; height:6px; border-bottom:2px solid rgba(255,255,255,.9); border-radius:0 0 12px 12px; }
.pet-body { width:96px; height:70px; border:3px solid rgba(255,255,255,.84); border-radius:46% 46% 20px 20px; background:color-mix(in srgb,var(--primary) 48%,#172033); }
.pet-signal { position:absolute; z-index:3; right:12px; top:12px; width:9px; height:9px; border-radius:50%; background:#7ee787; box-shadow:0 0 10px rgba(126,231,135,.8); }
.pet-thinking .pet-placeholder,.pet-walk .pet-placeholder { animation:pet-think .7s ease-in-out infinite; }
.pet-tool .pet-placeholder { animation:pet-tool .42s ease-in-out infinite alternate; }
.pet-working .pet-placeholder,.pet-wave .pet-placeholder { animation:pet-speak .32s ease-in-out infinite alternate; }
.pet-jump .pet-placeholder { animation:pet-done .6s ease-in-out 2; }
@keyframes pet-frame-in { from { opacity:0; } to { opacity:1; } }
@keyframes pet-frame-out { from { opacity:1; } to { opacity:0; } }
@keyframes pet-idle { 0%,100% { transform:translateX(-50%) scale(var(--sprite-scale)); } 50% { transform:translate(-50%,-5px) scale(var(--sprite-scale)); } }
@keyframes pet-think { 0%,100% { transform:translateX(-50%) scale(var(--sprite-scale)); } 50% { transform:translate(-50%,-8px) rotate(-2deg) scale(var(--sprite-scale)); } }
@keyframes pet-tool { from { transform:translateX(-50%) scale(var(--sprite-scale)); } to { transform:translate(-48%,-4px) rotate(2deg) scale(var(--sprite-scale)); } }
@keyframes pet-speak { from { transform:translateX(-50%) scale(var(--sprite-scale)); } to { transform:translate(-50%,-3px) scale(calc(var(--sprite-scale) * .96)); } }
@keyframes pet-done { 0%,100% { transform:translateX(-50%) scale(var(--sprite-scale)); } 50% { transform:translate(-50%,-14px) scale(calc(var(--sprite-scale) * 1.04)); } }
</style>
