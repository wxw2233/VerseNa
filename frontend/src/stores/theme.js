import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchJsonWithRetry, fetchWithTimeout } from '../utils/api'

export const useThemeStore = defineStore('theme', () => {
  const themes = ref([])
  const current = ref('default')

  async function fetchThemes({ retries = 2, retryDelay = 250, timeoutMs = 8000 } = {}) {
    const data = await fetchJsonWithRetry('/api/themes', {
      retries,
      retryDelay,
      timeoutMs,
      cache: 'no-store',
      validate: Array.isArray,
    })
    themes.value = data
    return data
  }

  /**
   * 切换主题：预加载 CSS，一次性应用（遮罩已覆盖屏幕）
   */
  async function switchTheme(name, colorOverrides = {}, { signal } = {}) {
    if (!name || name === 'null' || name === 'undefined') return

    // 预加载 CSS
    let css = ''
    try {
      const resp = await fetchWithTimeout(`/api/themes/${encodeURIComponent(name)}/css`, {
        cache: 'no-store',
        signal,
      }, 12000)
      if (resp.ok) css = await resp.text()
    } catch {}

    // 同一帧内应用 CSS + 颜色
    if (signal?.aborted) return
    if (css) {
      let styleEl = document.getElementById('theme-style')
      if (!styleEl) {
        styleEl = document.createElement('style')
        styleEl.id = 'theme-style'
        document.head.appendChild(styleEl)
      }
      styleEl.textContent = css
    }

    for (const [cssVar, val] of Object.entries(colorOverrides)) {
      document.documentElement.style.setProperty(cssVar, val)
    }
    if (Object.keys(colorOverrides).length > 0) {
      localStorage.setItem('theme-color-overrides', JSON.stringify(colorOverrides))
    }

    // 切换主题（背景图由 App.vue 自然加载）
    current.value = name
    localStorage.setItem('current-theme', name)
  }

  async function applyTheme(name, { signal } = {}) {
    if (!name || name === 'null' || name === 'undefined') return
    const resp = await fetchWithTimeout(`/api/themes/${encodeURIComponent(name)}/css`, {
      cache: 'no-store',
      signal,
    }, 12000)
    if (!resp.ok) return
    const css = await resp.text()
    if (signal?.aborted) return
    let styleEl = document.getElementById('theme-style')
    if (!styleEl) {
      styleEl = document.createElement('style')
      styleEl.id = 'theme-style'
      document.head.appendChild(styleEl)
    }
    styleEl.textContent = css
    current.value = name
    localStorage.setItem('current-theme', name)
  }

  async function restoreTheme() {
    const saved = localStorage.getItem('current-theme')
    if (saved && saved !== 'default' && saved !== 'null') {
      if (document.getElementById('theme-style')) {
        current.value = saved
      } else {
        await applyTheme(saved)
      }
      try {
        const overrides = JSON.parse(localStorage.getItem('theme-color-overrides') || '{}')
        for (const [cssVar, val] of Object.entries(overrides)) {
          document.documentElement.style.setProperty(cssVar, val)
        }
      } catch {}
    }
  }

  function ensureValidTheme() { if (!current.value || current.value === "null") applyTheme("default") }
  return { themes, current, fetchThemes, applyTheme, switchTheme, ensureValidTheme, restoreTheme }
})
