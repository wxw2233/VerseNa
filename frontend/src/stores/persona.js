import { defineStore } from 'pinia'
import { ref } from 'vue'

export const usePersonaStore = defineStore('persona', () => {
  const personas = ref([])
  const current = ref('default')

  async function fetchPersonas() {
    const resp = await fetch('/api/personas')
    personas.value = await resp.json()
  }

  function switchPersona(name) {
    current.value = name
  }

  return { personas, current, fetchPersonas, switchPersona }
})
