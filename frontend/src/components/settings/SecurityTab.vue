<template>
  <div class="security-tab">
    <header class="tab-header">
      <KeyRound :size="22" aria-hidden="true" />
      <h2>访问安全</h2>
    </header>

    <form class="token-form" @submit.prevent="updateToken">
      <label for="current-token">当前访问令牌</label>
      <div class="field-row">
        <input
          id="current-token"
          v-model="currentToken"
          :type="showCurrent ? 'text' : 'password'"
          autocomplete="current-password"
          :disabled="saving"
        />
        <button
          type="button"
          class="icon-button"
          :title="showCurrent ? '隐藏当前令牌' : '显示当前令牌'"
          :aria-label="showCurrent ? '隐藏当前令牌' : '显示当前令牌'"
          @click="showCurrent = !showCurrent"
        >
          <EyeOff v-if="showCurrent" :size="17" />
          <Eye v-else :size="17" />
        </button>
      </div>

      <label for="new-token">新访问令牌</label>
      <div class="field-row new-token-row">
        <input
          id="new-token"
          v-model="newToken"
          :type="showNew ? 'text' : 'password'"
          autocomplete="new-password"
          :minlength="MIN_TOKEN_LENGTH"
          :disabled="saving"
        />
        <button
          type="button"
          class="icon-button"
          :title="showNew ? '隐藏新令牌' : '显示新令牌'"
          :aria-label="showNew ? '隐藏新令牌' : '显示新令牌'"
          @click="showNew = !showNew"
        >
          <EyeOff v-if="showNew" :size="17" />
          <Eye v-else :size="17" />
        </button>
        <button
          type="button"
          class="icon-button"
          title="生成随机令牌"
          aria-label="生成随机令牌"
          @click="generateToken"
        >
          <RefreshCw :size="17" />
        </button>
        <button
          type="button"
          class="icon-button"
          title="复制新令牌"
          aria-label="复制新令牌"
          :disabled="!newToken"
          @click="copyToken"
        >
          <Check v-if="copied" :size="17" />
          <Copy v-else :size="17" />
        </button>
      </div>

      <label for="confirm-token">确认新访问令牌</label>
      <div class="field-row">
        <input
          id="confirm-token"
          v-model="confirmToken"
          :type="showNew ? 'text' : 'password'"
          autocomplete="new-password"
          :minlength="MIN_TOKEN_LENGTH"
          :disabled="saving"
        />
      </div>

      <p v-if="validationError" class="form-error" role="alert">{{ validationError }}</p>

      <button class="save-button" type="submit" :disabled="!canSubmit || saving">
        <LoaderCircle v-if="saving" class="spin" :size="17" />
        <Save v-else :size="17" />
        <span>更新访问令牌</span>
      </button>
    </form>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  Check,
  Copy,
  Eye,
  EyeOff,
  KeyRound,
  LoaderCircle,
  RefreshCw,
  Save,
} from 'lucide-vue-next'
import { useToast } from '../../composables/useToast'

const toast = useToast()
const MIN_TOKEN_LENGTH = 6
const currentToken = ref('')
const newToken = ref('')
const confirmToken = ref('')
const showCurrent = ref(false)
const showNew = ref(false)
const saving = ref(false)
const copied = ref(false)
const normalizedCurrentToken = computed(() => currentToken.value.trim())
const normalizedNewToken = computed(() => newToken.value.trim())

const validationError = computed(() => {
  if (newToken.value && normalizedNewToken.value.length < MIN_TOKEN_LENGTH) {
    return `新访问令牌至少需要 ${MIN_TOKEN_LENGTH} 个字符`
  }
  if (confirmToken.value && normalizedNewToken.value !== confirmToken.value.trim()) return '两次输入的新令牌不一致'
  if (normalizedCurrentToken.value && normalizedCurrentToken.value === normalizedNewToken.value) return '新访问令牌不能与当前令牌相同'
  return ''
})

const canSubmit = computed(() => (
  normalizedCurrentToken.value.length > 0
  && normalizedNewToken.value.length >= MIN_TOKEN_LENGTH
  && normalizedNewToken.value === confirmToken.value.trim()
  && !validationError.value
))

function generateToken() {
  const bytes = new Uint8Array(32)
  crypto.getRandomValues(bytes)
  const binary = Array.from(bytes, byte => String.fromCharCode(byte)).join('')
  const token = btoa(binary).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/, '')
  newToken.value = token
  confirmToken.value = token
  showNew.value = true
  copied.value = false
}

async function copyToken() {
  if (!newToken.value) return
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(newToken.value)
  } else {
    const textarea = document.createElement('textarea')
    textarea.value = newToken.value
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    textarea.remove()
  }
  copied.value = true
  setTimeout(() => { copied.value = false }, 1600)
}

async function updateToken() {
  if (!canSubmit.value || saving.value) return
  saving.value = true
  const tokenToSave = normalizedNewToken.value
  try {
    const response = await fetch('/api/auth/token', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        current_token: normalizedCurrentToken.value,
        new_token: tokenToSave,
      }),
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`)

    currentToken.value = ''
    newToken.value = tokenToSave
    confirmToken.value = tokenToSave
    toast.success('访问令牌已更新，其他设备需要重新登录')
  } catch (err) {
    toast.error(err.message || '访问令牌更新失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.security-tab {
  max-width: 720px;
}

.tab-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 28px;
}

.tab-header h2 {
  margin: 0;
  font-size: 20px;
}

.token-form {
  display: grid;
  gap: 9px;
  max-width: 620px;
}

label {
  margin-top: 9px;
  color: var(--text-secondary);
  font-size: 13px;
}

.field-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 42px;
  min-height: 42px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  background: rgba(10, 11, 20, 0.38);
  overflow: hidden;
}

.new-token-row {
  grid-template-columns: minmax(0, 1fr) repeat(3, 42px);
}

.field-row:focus-within {
  border-color: var(--primary);
}

input {
  min-width: 0;
  padding: 0 12px;
  border: 0;
  outline: 0;
  color: var(--text-primary);
  background: transparent;
  font: inherit;
}

.icon-button {
  display: grid;
  place-items: center;
  border: 0;
  border-left: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--text-secondary);
  background: transparent;
  cursor: pointer;
}

.icon-button:hover:not(:disabled) {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.08);
}

.icon-button:disabled {
  opacity: 0.35;
  cursor: default;
}

.form-error {
  margin: 2px 0 0;
  color: #ff8f9b;
  font-size: 13px;
}

.save-button {
  width: fit-content;
  min-height: 40px;
  margin-top: 14px;
  padding: 0 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid color-mix(in srgb, var(--primary) 72%, white);
  border-radius: 6px;
  color: white;
  background: color-mix(in srgb, var(--primary) 82%, #11131f);
  cursor: pointer;
}

.save-button:disabled {
  opacity: 0.45;
  cursor: default;
}

.spin {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 600px) {
  .new-token-row {
    grid-template-columns: minmax(0, 1fr) repeat(3, 38px);
  }
}
</style>
