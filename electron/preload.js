const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  getVersion: () => ipcRenderer.invoke('get-version'),
  showMain: () => ipcRenderer.invoke('show-main'),
  openPet: () => ipcRenderer.invoke('open-pet'),
  closePet: () => ipcRenderer.invoke('close-pet'),
  setPetState: (state) => ipcRenderer.send('pet-state', state),
  onPetState: (callback) => {
    const listener = (_event, state) => callback(state)
    ipcRenderer.on('pet-state', listener)
    return () => ipcRenderer.removeListener('pet-state', listener)
  },
  isElectron: true,
})
