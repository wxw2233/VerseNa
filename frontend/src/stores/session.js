import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchJsonWithRetry } from '../utils/api'

export const useSessionStore = defineStore('session', () => {
  const sessions = ref([])
  const currentSessionId = ref('default')
  const loading = ref(false)
  const error = ref('')
  let fetchPromise = null

  async function fetchSessions({ retries = 2, retryDelay = 250 } = {}) {
    if (fetchPromise) return fetchPromise

    loading.value = true
    error.value = ''
    fetchPromise = (async () => {
      const data = await fetchJsonWithRetry('/api/sessions', {
        retries,
        retryDelay,
        cache: 'no-store',
        validate: Array.isArray,
      })
      sessions.value = data
      return data
    })()

    try {
      return await fetchPromise
    } catch (err) {
      error.value = '会话列表加载失败'
      throw err
    } finally {
      loading.value = false
      fetchPromise = null
    }
  }

  async function createSession() {
    const resp = await fetch('/api/sessions', { method: 'POST', headers: {'Content-Type':'application/json'}, body: '{}' })
    const data = await resp.json()
    currentSessionId.value = data.session_id
    await fetchSessions()
    return data.session_id
  }

  async function deleteSession(id) {
    const resp = await fetch(`/api/sessions/${id}`, { method: 'DELETE' })
    if (!resp.ok) throw new Error(`删除会话失败: HTTP ${resp.status}`)
    if (currentSessionId.value === id) {
      currentSessionId.value = 'default'
    }
    await fetchSessions()
  }

  function switchSession(id) {
    currentSessionId.value = id
  }

  return { sessions, currentSessionId, loading, error, fetchSessions, createSession, deleteSession, switchSession }
})
