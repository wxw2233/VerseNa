<template>
  <div v-if="visible" class="pet-overlay" :style="overlayStyle" @pointerdown="startDrag">
    <PetSprite :state="liveState" :theme="liveTheme" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import PetSprite from './PetSprite.vue'

const props = defineProps({ state: { type: String, default: 'idle' }, theme: { type: String, default: 'default' } })
const liveState = ref(props.state)
const liveTheme = ref(props.theme)
const visible = ref(localStorage.getItem('pet-visible') === 'true')
const scale = ref(Number(localStorage.getItem('pet-scale') || 1))
let savedPosition = { x: Math.max(12, window.innerWidth - 220), y: Math.max(72, window.innerHeight - 280) }
try {
  const stored = localStorage.getItem('pet-position')
  if (stored) savedPosition = JSON.parse(stored)
} catch {}
const position = ref(savedPosition)
let drag = null
const overlayStyle = computed(() => ({ left: position.value.x + 'px', top: position.value.y + 'px', transform: 'scale(' + scale.value + ')', transformOrigin: 'top left' }))
function persist() { localStorage.setItem('pet-visible', String(visible.value)); localStorage.setItem('pet-scale', String(scale.value)); localStorage.setItem('pet-position', JSON.stringify(position.value)) }
function toggle() { visible.value = !visible.value; persist() }
function updateState(event) {
  if (typeof event.detail?.state === 'string') liveState.value = event.detail.state
  if (typeof event.detail?.theme === 'string' && event.detail.theme) liveTheme.value = event.detail.theme
}
async function loadScale() {
  try {
    const response = await fetch('/api/themes/' + encodeURIComponent(liveTheme.value) + '/pet-config?t=' + Date.now())
    if (response.ok) {
      scale.value = Number((await response.json()).scale || 1)
      localStorage.setItem('pet-scale', String(scale.value))
    }
  } catch {}
}
function updateScale(event) {
  if (event.detail?.theme === liveTheme.value && Number.isFinite(Number(event.detail.scale))) {
    scale.value = Number(event.detail.scale)
    localStorage.setItem('pet-scale', String(scale.value))
  }
}
function startDrag(event) { if (event.button !== 0) return; drag = { x:event.clientX, y:event.clientY, left:position.value.x, top:position.value.y }; window.addEventListener('pointermove', moveDrag); window.addEventListener('pointerup', stopDrag, { once:true }) }
function moveDrag(event) { if (!drag) return; position.value = { x:Math.max(0, Math.min(window.innerWidth - 80, drag.left + event.clientX - drag.x)), y:Math.max(0, Math.min(window.innerHeight - 100, drag.top + event.clientY - drag.y)) } }
function stopDrag() { drag = null; window.removeEventListener('pointermove', moveDrag); persist() }
window.addEventListener('versena:toggle-pet', toggle)
window.addEventListener('versena:pet-state', updateState)
window.addEventListener('versena:pet-scale', updateScale)
watch(() => props.state, value => { liveState.value = value })
watch(() => props.theme, value => { liveTheme.value = value; loadScale() })
onMounted(loadScale)
onBeforeUnmount(() => { window.removeEventListener('versena:toggle-pet', toggle); window.removeEventListener('versena:pet-state', updateState); window.removeEventListener('versena:pet-scale', updateScale); window.removeEventListener('pointermove', moveDrag) })
</script>

<style scoped>
.pet-overlay { position:fixed; z-index:120; width:180px; height:225px; cursor:grab; user-select:none; touch-action:none; }
.pet-overlay:active { cursor:grabbing; }
</style>
