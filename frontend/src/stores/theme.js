import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  const themes = ref([])
  const current = ref('default')

  async function fetchThemes() {
    const resp = await fetch('/api/themes')
    themes.value = await resp.json()
  }

  async function applyTheme(name) {
    if (!name || name === 'null' || name === 'undefined') return
    const resp = await fetch(`/api/themes/${name}/css?t=${Date.now()}`)
    if (!resp.ok) return
    const css = await resp.text()
    let styleEl = document.getElementById('theme-style')
    if (!styleEl) {
      styleEl = document.createElement('style')
      styleEl.id = 'theme-style'
      document.head.appendChild(styleEl)
    }
    styleEl.textContent = css; 
    current.value = name
    localStorage.setItem('current-theme', name)
  }

  async function restoreTheme() {
    const saved = localStorage.getItem('current-theme')
    if (saved && saved !== 'default' && saved !== 'null') {
      await applyTheme(saved)
    }
  }

  function ensureValidTheme() { if (!current.value || current.value === "null") applyTheme("default") }
  return { themes, current, fetchThemes, applyTheme, ensureValidTheme, restoreTheme }
})
