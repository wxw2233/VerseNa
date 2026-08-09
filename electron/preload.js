const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  getVersion: () => ipcRenderer.invoke('get-version'),
  showMain: () => ipcRenderer.invoke('show-main'),
  openPet: () => ipcRenderer.invoke('open-pet'),
  closePet: () => ipcRenderer.invoke('close-pet'),
  resizePet: (scale) => ipcRenderer.invoke('resize-pet', scale),
  onPetScale: (callback) => {
    const listener = (_event, scale) => callback(scale)
    ipcRenderer.on('pet-scale', listener)
    return () => ipcRenderer.removeListener('pet-scale', listener)
  },
  setPetState: (state) => ipcRenderer.send('pet-state', state),
  onPetState: (callback) => {
    const listener = (_event, state) => callback(state)
    ipcRenderer.on('pet-state', listener)
    return () => ipcRenderer.removeListener('pet-state', listener)
  },
  setPetConfig: (config) => ipcRenderer.send('pet-config', config),
  onPetConfig: (callback) => {
    const listener = (_event, config) => callback(config)
    ipcRenderer.on('pet-config', listener)
    return () => ipcRenderer.removeListener('pet-config', listener)
  },
  isElectron: true,
})
