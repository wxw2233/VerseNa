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
    const resp = await fetch(`/api/themes/${name}/css`)
    const css = await resp.text()
    let styleEl = document.getElementById('theme-style')
    if (!styleEl) {
      styleEl = document.createElement('style')
      styleEl.id = 'theme-style'
      document.head.appendChild(styleEl)
    }
    styleEl.textContent = css
    current.value = name
  }

  return { themes, current, fetchThemes, applyTheme }
})
