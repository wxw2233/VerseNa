<template>
  <div
    class="pet-window"
    :class="`pet-${petState}`"
    @dblclick="showMain"
  >
    <img
      class="pet-frame"
      :src="frameUrl"
      alt=""
      draggable="false"
      :class="{ hidden: !frameLoaded }"
      @load="frameLoaded = true"
      @error="frameLoaded = false"
    />
    <div v-if="!frameLoaded" class="pet-placeholder" aria-hidden="true">
      <div class="pet-aura"></div>
      <div class="pet-head">
        <span class="pet-eye left"></span>
        <span class="pet-eye right"></span>
        <span class="pet-mouth"></span>
      </div>
      <div class="pet-body"></div>
    </div>
    <span class="pet-signal" aria-hidden="true"></span>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const frameCounts = {
  idle: 2,
  thinking: 4,
  tool: 3,
  speaking: 2,
  working: 3,
  stopping: 2,
  done: 2,
  error: 2,
}

const frameIntervals = {
  idle: 900,
  thinking: 220,
  tool: 320,
  speaking: 160,
  working: 300,
  stopping: 260,
  done: 500,
  error: 600,
}

const petState = ref('idle')
const petTheme = ref(localStorage.getItem('current-theme') || 'default')
const frameIndex = ref(1)
const frameLoaded = ref(false)
let frameTimer = null
let removeStateListener = null

const frameUrl = computed(() => {
  const number = String(frameIndex.value).padStart(2, '0')
  return `/api/themes/${encodeURIComponent(petTheme.value || 'default')}/assets/pet-${petState.value}-${number}.png`
})

function resetFrames() {
  frameIndex.value = 1
  frameLoaded.value = false
  if (frameTimer) clearInterval(frameTimer)

  const count = frameCounts[petState.value] || frameCounts.idle
  const interval = frameIntervals[petState.value] || frameIntervals.idle
  if (count <= 1) return

  frameTimer = setInterval(() => {
    frameIndex.value = frameIndex.value >= count ? 1 : frameIndex.value + 1
    frameLoaded.value = false
  }, interval)
}

function applyPetState(nextState) {
  const state = nextState?.state
  if (typeof state === 'string' && frameCounts[state]) petState.value = state
  if (typeof nextState?.theme === 'string' && nextState.theme) petTheme.value = nextState.theme
  resetFrames()
}

function showMain() {
  window.electronAPI?.showMain?.()
}

watch(frameUrl, () => {
  frameLoaded.value = false
})

onMounted(() => {
  document.documentElement.classList.add('pet-window-body')
  document.body.classList.add('pet-window-body')
  removeStateListener = window.electronAPI?.onPetState?.(applyPetState) || null
  resetFrames()
})

onBeforeUnmount(() => {
  removeStateListener?.()
  if (frameTimer) clearInterval(frameTimer)
  document.documentElement.classList.remove('pet-window-body')
  document.body.classList.remove('pet-window-body')
})
</script>

<style scoped>
:global(html.pet-window-body),
:global(body.pet-window-body) {
  background: transparent !important;
  overflow: hidden;
}

.pet-window {
  position: relative;
  width: 100vw;
  height: 100vh;
  display: grid;
  place-items: end center;
  padding: 8px 10px 4px;
  cursor: grab;
  -webkit-app-region: drag;
  user-select: none;
}

.pet-window:active { cursor: grabbing; }

.pet-frame {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
  -webkit-user-drag: none;
  filter: drop-shadow(0 8px 12px rgba(0, 0, 0, 0.28));
}

.pet-frame.hidden { display: none; }

.pet-placeholder {
  position: relative;
  width: 126px;
  height: 178px;
  display: grid;
  place-items: end center;
  filter: drop-shadow(0 8px 12px rgba(0, 0, 0, 0.28));
  animation: pet-idle 1.8s ease-in-out infinite;
}

.pet-aura {
  position: absolute;
  width: 104px;
  height: 104px;
  top: 22px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--primary) 32%, transparent);
  filter: blur(16px);
  opacity: 0.7;
}

.pet-head {
  position: absolute;
  top: 28px;
  width: 88px;
  height: 84px;
  border: 3px solid rgba(255, 255, 255, 0.84);
  border-radius: 46% 46% 42% 42%;
  background: color-mix(in srgb, var(--primary) 66%, #172033);
  box-shadow: inset 0 -8px 0 rgba(0, 0, 0, 0.1);
}

.pet-head::before,
.pet-head::after {
  content: '';
  position: absolute;
  top: -22px;
  width: 26px;
  height: 30px;
  border: 3px solid rgba(255, 255, 255, 0.84);
  background: color-mix(in srgb, var(--primary) 66%, #172033);
  z-index: -1;
}

.pet-head::before { left: 5px; transform: rotate(-24deg); border-radius: 8px 18px 2px 18px; }
.pet-head::after { right: 5px; transform: rotate(24deg); border-radius: 18px 8px 18px 2px; }

.pet-eye {
  position: absolute;
  top: 36px;
  width: 9px;
  height: 13px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 0 6px rgba(255, 255, 255, 0.65);
}

.pet-eye.left { left: 24px; }
.pet-eye.right { right: 24px; }

.pet-mouth {
  position: absolute;
  left: 38px;
  bottom: 17px;
  width: 12px;
  height: 6px;
  border-bottom: 2px solid rgba(255, 255, 255, 0.9);
  border-radius: 0 0 12px 12px;
}

.pet-body {
  width: 96px;
  height: 70px;
  border: 3px solid rgba(255, 255, 255, 0.84);
  border-radius: 46% 46% 20px 20px;
  background: color-mix(in srgb, var(--primary) 48%, #172033);
}

.pet-signal {
  position: absolute;
  right: 12px;
  top: 12px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #7ee787;
  box-shadow: 0 0 10px rgba(126, 231, 135, 0.8);
}

.pet-thinking .pet-placeholder,
.pet-working .pet-placeholder,
.pet-tool .pet-placeholder { animation: pet-think 0.7s ease-in-out infinite; }
.pet-speaking .pet-placeholder { animation: pet-speak 0.32s ease-in-out infinite alternate; }
.pet-done .pet-placeholder { animation: pet-done 0.6s ease-in-out 2; }
.pet-error .pet-placeholder { animation: pet-error 0.25s ease-in-out 3; }
.pet-stopping .pet-signal { background: #f2cc60; box-shadow: 0 0 10px rgba(242, 204, 96, 0.8); }
.pet-error .pet-signal { background: #ff7b72; box-shadow: 0 0 10px rgba(255, 123, 114, 0.8); }

@keyframes pet-idle { 50% { transform: translateY(-5px); } }
@keyframes pet-think { 50% { transform: translateY(-8px) rotate(-2deg); } }
@keyframes pet-speak { to { transform: translateY(-3px) scaleY(0.96); } }
@keyframes pet-done { 50% { transform: translateY(-14px) scale(1.04); } }
@keyframes pet-error { 50% { transform: translateX(-5px); } }
</style>
