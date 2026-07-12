<template>
  <div class="input-bar">
    <input type="file" ref="fileInput" style="display:none" @change="handleFile" />
    <button class="attach-btn" @click="$refs.fileInput.click()">📎</button>
    <textarea v-model="text" @keydown.enter.exact.prevent="send" placeholder="输入消息... (Enter 发送)" rows="1" ref="textareaRef"></textarea>
    <button @click="send" :disabled="!text.trim()">发送</button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
const emit = defineEmits(['send'])
const text = ref('')
const textareaRef = ref(null)
const fileInput = ref(null)

function send() {
  if (text.value.trim()) {
    emit('send', text.value.trim())
    text.value = ''
  }
}

async function handleFile(e) {
  const file = e.target.files[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  const resp = await fetch('/api/upload', { method: 'POST', body: formData })
  const data = await resp.json()
  text.value += `\n[文件: ${data.filename}]\n${data.text_preview}\n`
  e.target.value = ''
}
</script>

<style scoped>
.input-bar {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  background: var(--bg-secondary);
  border-top: 1px solid var(--border);
}
textarea {
  flex: 1;
  resize: none;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 12px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
  max-height: 120px;
}
textarea:focus {
  border-color: var(--primary);
}
button {
  padding: 8px 20px;
  background: var(--primary);
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.attach-btn {
  padding: 8px 12px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 8px;
  cursor: pointer;
  font-size: 16px;
}
</style>
