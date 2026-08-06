export function isDesktopPetAvailable() {
  return Boolean(typeof window !== 'undefined' && window.electronAPI?.isElectron && window.electronAPI?.openPet)
}

export function openDesktopPet() {
  return globalThis.window?.electronAPI?.openPet?.()
}

export function closeDesktopPet() {
  return globalThis.window?.electronAPI?.closePet?.()
}

export function setDesktopPetState(state, theme = '') {
  if (!isDesktopPetAvailable()) return
  window.electronAPI.setPetState({ state, theme })
}
