import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const isStreaming = ref(false)
  const currentPersona = ref('default')
  const bgOpacity = ref(0.3)

  function addUserMessage(content) {
    messages.value.push({ role: 'user', content, persona: currentPersona.value })
  }

  function appendAgentChunk(content) {
    const last = messages.value[messages.value.length - 1]
    if (last && last.role === 'assistant' && last.streaming) {
      last.content += content
    } else {
      messages.value.push({ role: 'assistant', content, streaming: true, persona: currentPersona.value })
    }
  }

  function finishStreaming() {
    const last = messages.value[messages.value.length - 1]
    if (last) last.streaming = false
    isStreaming.value = false
  }

  function clearMessages() {
    messages.value = []
  }

  return { messages, isStreaming, currentPersona, bgOpacity, addUserMessage, appendAgentChunk, finishStreaming, clearMessages }
})
