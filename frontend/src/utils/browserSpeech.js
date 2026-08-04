export function cancelBrowserSpeech() {
  if (typeof window !== 'undefined' && window.speechSynthesis) {
    window.speechSynthesis.cancel()
  }
}

export function speakWithBrowser(text, { onEnd, onError } = {}) {
  if (
    typeof window === 'undefined'
    || !window.speechSynthesis
    || typeof window.SpeechSynthesisUtterance !== 'function'
  ) {
    return null
  }

  cancelBrowserSpeech()
  const utterance = new window.SpeechSynthesisUtterance(text)
  utterance.lang = /[\u3400-\u9fff]/.test(text) ? 'zh-CN' : navigator.language || 'en-US'
  utterance.onend = () => onEnd?.()
  utterance.onerror = event => {
    if (!['canceled', 'interrupted'].includes(event.error)) onError?.(event)
  }
  window.speechSynthesis.speak(utterance)
  return utterance
}
