import { ref } from 'vue'

const toasts = ref([])
let nextId = 0

export function useToast() {
  function show(message, type = 'info', duration = 3000) {
    const id = nextId++
    toasts.value.push({ id, message, type, leaving: false })
    setTimeout(() => dismiss(id), duration)
    // 最多保留 5 条
    if (toasts.value.length > 5) {
      toasts.value.shift()
    }
  }

  function dismiss(id) {
    const t = toasts.value.find(t => t.id === id)
    if (t) {
      t.leaving = true
      setTimeout(() => {
        toasts.value = toasts.value.filter(t => t.id !== id)
      }, 300)
    }
  }

  function success(msg) { show(msg, 'success') }
  function error(msg) { show(msg, 'error', 5000) }
  function warning(msg) { show(msg, 'warning', 4000) }
  function info(msg) { show(msg, 'info') }

  return { toasts, show, dismiss, success, error, warning, info }
}
