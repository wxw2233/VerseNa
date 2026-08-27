import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchJsonWithRetry } from '../utils/api'

export const usePersonaStore = defineStore('persona', () => {
  const personas = ref([])
  const current = ref('default')

  async function fetchPersonas({ retries = 2, retryDelay = 250, timeoutMs = 8000 } = {}) {
    const data = await fetchJsonWithRetry('/api/personas', {
      retries,
      retryDelay,
      timeoutMs,
      cache: 'no-store',
      validate: Array.isArray,
    })
    personas.value = data
    return data
  }

  function switchPersona(name) {
    current.value = name
  }

  return { personas, current, fetchPersonas, switchPersona }
})
