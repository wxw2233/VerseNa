const DEFAULT_TIMEOUT_MS = 15000

export async function fetchWithTimeout(url, options = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const duration = Number(timeoutMs)
  if (!Number.isFinite(duration) || duration <= 0) return fetch(url, options)

  const controller = new AbortController()
  const sourceSignal = options.signal
  let timedOut = false
  let timer = null

  const abortFromSource = () => controller.abort(sourceSignal?.reason)
  if (sourceSignal?.aborted) abortFromSource()
  else sourceSignal?.addEventListener('abort', abortFromSource, { once: true })

  timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, duration)

  try {
    return await fetch(url, { ...options, signal: controller.signal })
  } catch (error) {
    if (timedOut) {
      const timeoutError = new Error(`请求超时（${duration}ms）`)
      timeoutError.name = 'TimeoutError'
      timeoutError.code = 'TIMEOUT'
      throw timeoutError
    }
    throw error
  } finally {
    if (timer) clearTimeout(timer)
    sourceSignal?.removeEventListener('abort', abortFromSource)
  }
}

export async function fetchJsonWithRetry(url, options = {}) {
  const {
    retries = 2,
    retryDelay = 250,
    validate,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    retryTimeouts = false,
    ...requestInit
  } = options
  let lastError

  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const response = await fetchWithTimeout(url, requestInit, timeoutMs)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const data = await response.json()
      if (validate && !validate(data)) throw new Error(`Invalid response from ${url}`)
      return data
    } catch (err) {
      lastError = err
      if (requestInit.signal?.aborted) throw err
      if (err?.code === 'TIMEOUT' && !retryTimeouts) throw err
      if (attempt < retries) {
        await new Promise(resolve => setTimeout(resolve, retryDelay * (2 ** attempt)))
      }
    }
  }

  throw lastError
}
