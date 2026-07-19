import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useSessionStore = defineStore('session', () => {
  const sessions = ref([])
  const currentSessionId = ref('default')
  const loading = ref(false)

  async function fetchSessions() {
    loading.value = true
    try {
      const resp = await fetch('/api/sessions')
      sessions.value = await resp.json()
    } finally {
      loading.value = false
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
    await fetch(`/api/sessions/${id}`, { method: 'DELETE' })
    if (currentSessionId.value === id) {
      currentSessionId.value = 'default'
    }
    await fetchSessions()
  }

  function switchSession(id) {
    currentSessionId.value = id
  }

  return { sessions, currentSessionId, loading, fetchSessions, createSession, deleteSession, switchSession }
})
