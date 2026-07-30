<template>
  <main class="login-screen">
    <form class="login-panel" @submit.prevent="submit">
      <div class="brand">VerseNa</div>
      <LockKeyhole :size="24" aria-hidden="true" />
      <h1>访问验证</h1>

      <label for="access-token">访问令牌</label>
      <div class="token-field">
        <input
          id="access-token"
          v-model="token"
          :type="showToken ? 'text' : 'password'"
          autocomplete="current-password"
          autofocus
          :disabled="submitting"
        />
        <button
          type="button"
          class="icon-button"
          :aria-label="showToken ? '隐藏令牌' : '显示令牌'"
          :title="showToken ? '隐藏令牌' : '显示令牌'"
          @click="showToken = !showToken"
        >
          <EyeOff v-if="showToken" :size="18" />
          <Eye v-else :size="18" />
        </button>
      </div>

      <p v-if="error" class="login-error" role="alert">{{ error }}</p>
      <button class="submit-button" type="submit" :disabled="submitting || !token.trim()">
        <LoaderCircle v-if="submitting" class="spin" :size="18" />
        <LogIn v-else :size="18" />
        <span>进入 VerseNa</span>
      </button>
    </form>
  </main>
</template>

<script setup>
import { ref } from 'vue'
import { Eye, EyeOff, LoaderCircle, LockKeyhole, LogIn } from 'lucide-vue-next'
import { loginWithToken } from '../utils/auth'

const emit = defineEmits(['authenticated'])
const token = ref('')
const showToken = ref(false)
const submitting = ref(false)
const error = ref('')

async function submit() {
  if (!token.value.trim() || submitting.value) return
  submitting.value = true
  error.value = ''
  try {
    await loginWithToken(token.value.trim())
    token.value = ''
    emit('authenticated')
  } catch (err) {
    error.value = err.status === 429 ? '尝试次数过多，请稍后再试' : '访问令牌不正确'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.login-screen {
  position: relative;
  z-index: 2;
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
}

.login-panel {
  width: min(360px, 100%);
  padding: 28px;
  border: 1px solid rgba(255, 255, 255, 0.24);
  border-radius: 8px;
  background: rgba(15, 16, 28, 0.88);
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.38);
  backdrop-filter: blur(18px);
}

.brand {
  margin-bottom: 28px;
  color: var(--primary);
  font-size: 24px;
  font-weight: 700;
}

h1 {
  margin: 10px 0 24px;
  font-size: 20px;
}

label {
  display: block;
  margin-bottom: 8px;
  color: var(--text-secondary);
  font-size: 13px;
}

.token-field {
  display: grid;
  grid-template-columns: 1fr 42px;
  min-height: 42px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.2);
  overflow: hidden;
}

.token-field:focus-within {
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
  color: var(--text-secondary);
  background: transparent;
  cursor: pointer;
}

.icon-button:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.08);
}

.login-error {
  margin: 10px 0 0;
  color: #ff8f9b;
  font-size: 13px;
}

.submit-button {
  width: 100%;
  min-height: 42px;
  margin-top: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid color-mix(in srgb, var(--primary) 72%, white);
  border-radius: 6px;
  color: white;
  background: color-mix(in srgb, var(--primary) 82%, #11131f);
  cursor: pointer;
}

.submit-button:disabled {
  opacity: 0.45;
  cursor: default;
}

.spin {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
