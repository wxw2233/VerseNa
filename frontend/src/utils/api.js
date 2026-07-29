export async function fetchJsonWithRetry(url, options = {}) {
  const {
    retries = 2,
    retryDelay = 250,
    validate,
    ...requestInit
  } = options
  let lastError

  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const response = await fetch(url, requestInit)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const data = await response.json()
      if (validate && !validate(data)) throw new Error(`Invalid response from ${url}`)
      return data
    } catch (err) {
      lastError = err
      if (attempt < retries) {
        await new Promise(resolve => setTimeout(resolve, retryDelay * (2 ** attempt)))
      }
    }
  }

  throw lastError
}
