export function isDesktopPetAvailable() {
  return Boolean(typeof window !== 'undefined' && window.electronAPI?.isElectron && window.electronAPI?.openPet)
}

export function openDesktopPet() {
  if (isDesktopPetAvailable()) return globalThis.window.electronAPI.openPet()
  globalThis.window?.dispatchEvent(new CustomEvent('versena:toggle-pet'))
}

export function closeDesktopPet() {
  return globalThis.window?.electronAPI?.closePet?.()
}

export function setDesktopPetState(state, theme = '') {
  if (typeof window === 'undefined') return
  const detail = { state, theme }
  window.dispatchEvent(new CustomEvent('versena:pet-state', { detail }))
  if (isDesktopPetAvailable()) window.electronAPI.setPetState(detail)
}

export function detectAgentPetState({ isStopping = false, isStreaming = false, messages = [] } = {}) {
  if (isStopping) return 'stopping'
  if (!isStreaming) return 'idle'

  const assistant = [...messages].reverse().find(message => (
    message?.role === 'assistant' && message.streaming
  ))
  if (!assistant) return 'working'

  const segments = Array.isArray(assistant.segments) ? assistant.segments : []
  // 工具执行优先级高于思考，避免残留的 running reasoning 覆盖真实工具状态。
  const activeTool = [...segments].reverse().find(segment => (
    ['tool', 'subagent', 'subagent_plan'].includes(segment?.type) && segment.status === 'running'
  ))
  if (activeTool) return 'tool'
  const activeReasoning = [...segments].reverse().find(segment => (
    segment?.type === 'reasoning' && segment.status === 'running'
  ))
  if (activeReasoning) return 'thinking'

  // The reasoning segment can arrive a moment after the generation is accepted.
  if (assistant.reasoningEnabled === true && segments.length === 0) return 'thinking'
  return 'working'
}
