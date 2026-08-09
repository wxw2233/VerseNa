<template>
  <div class="pet-window" @dblclick="showMain">
    <PetSprite :state="petState" :theme="petTheme" :scale="scale" :config-revision="configRevision" />
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import PetSprite from '../components/pet/PetSprite.vue'

const scale = ref(Number(localStorage.getItem('electron-pet-scale') || 1))
const petState = ref('idle')
const petTheme = ref(localStorage.getItem('current-theme') || 'default')
const configRevision = ref(0)
let removeStateListener = null
let removeScaleListener = null
let removeConfigListener = null

function showMain() { window.electronAPI?.showMain?.() }
async function loadScale() {
  try {
    const response = await fetch('/api/themes/' + encodeURIComponent(petTheme.value) + '/pet-config?t=' + Date.now())
    if (response.ok) {
      scale.value = Number((await response.json()).scale || 1)
      window.electronAPI?.resizePet?.(scale.value)
    }
  } catch {}
}
function applyPetState(nextState) {
  if (typeof nextState?.state === 'string') petState.value = nextState.state
  if (typeof nextState?.theme === 'string' && nextState.theme) petTheme.value = nextState.theme
  loadScale()
}

onMounted(() => {
  document.documentElement.classList.add('pet-window-body')
  document.body.classList.add('pet-window-body')
  removeStateListener = window.electronAPI?.onPetState?.(applyPetState) || null
  removeScaleListener = window.electronAPI?.onPetScale?.((nextScale) => {
    scale.value = Number(nextScale) || 1
  }) || null
  removeConfigListener = window.electronAPI?.onPetConfig?.((config) => {
    if (!config?.theme || config.theme === petTheme.value) configRevision.value += 1
  }) || null
  loadScale()
})
onBeforeUnmount(() => {
  removeStateListener?.()
  removeScaleListener?.()
  removeConfigListener?.()
  document.documentElement.classList.remove('pet-window-body')
  document.body.classList.remove('pet-window-body')
})
</script>

<style scoped>
:global(html.pet-window-body), :global(body.pet-window-body) { background: transparent !important; overflow: hidden; }
.pet-window { position: relative; width: 100vw; height: 100vh; cursor: grab; -webkit-app-region: drag; user-select: none; }
.pet-window:active { cursor: grabbing; }
</style>
