const AUTH_REQUIRED_EVENT = 'versena-auth-required'
const nativeFetch = globalThis.fetch.bind(globalThis)
let interceptorInstalled = false


function isAuthEndpoint(input) {
  const url = typeof input === 'string' ? input : input?.url || ''
  return url.includes('/api/auth/login') || url.includes('/api/auth/status')
}


export function notifyAuthenticationRequired() {
  window.dispatchEvent(new CustomEvent(AUTH_REQUIRED_EVENT))
}


export function onAuthenticationRequired(handler) {
  window.addEventListener(AUTH_REQUIRED_EVENT, handler)
  return () => window.removeEventListener(AUTH_REQUIRED_EVENT, handler)
}


export function installAuthFetchInterceptor() {
  if (interceptorInstalled) return
  interceptorInstalled = true

  globalThis.fetch = async (input, init = {}) => {
    const response = await nativeFetch(input, {
      credentials: 'same-origin',
      ...init,
    })
    if (response.status === 401 && !isAuthEndpoint(input)) {
      notifyAuthenticationRequired()
    }
    return response
  }
}


export async function getAuthStatus() {
  const response = await nativeFetch('/api/auth/status', {
    credentials: 'same-origin',
    cache: 'no-store',
  })
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  return response.json()
}


export async function loginWithToken(token) {
  const response = await nativeFetch('/api/auth/login', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const error = new Error(data.detail || `HTTP ${response.status}`)
    error.status = response.status
    throw error
  }
  return data
}


export async function logoutSession() {
  await nativeFetch('/api/auth/logout', {
    method: 'POST',
    credentials: 'same-origin',
  })
  notifyAuthenticationRequired()
}
