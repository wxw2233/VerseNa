<template>
  <div class="input-bar">
    <input type="file" ref="fileInput" style="display:none" @change="handleFile" />
    <button class="attach-btn" @click="$refs.fileInput.click()">📎</button>
    <textarea v-model="text" @keydown.enter.exact.prevent="send" placeholder="输入消息... (Enter 发送)" rows="1" ref="textareaRef"></textarea>
    <button @click="send" :disabled="!text.trim()">发送</button>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'


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
/* L2 base for input bar, perceptual border on top only */
.input-bar {
  display: flex;
  gap: 8px;
  padding: 12px 24px;
  background: var(--panel-l2);
   

  box-shadow: 0 -1px 0 rgba(255, 255, 255, 0.04);
}
/* L4 textarea: 12px radius, inner glow */
textarea {
  flex: 1;
  resize: none;
  border: none;
  border-radius: var(--radius);
  padding: 8px 12px;
  background: transparent;
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
  max-height: 120px;
  font-family: inherit;
  box-shadow: var(--border-subtle), var(--glow-inner);
  transition: box-shadow 0.2s;
}
textarea:focus {
  box-shadow: 0 0 0 1px var(--primary), var(--glow-inner);
}
/* L4 buttons: 10px radius, hover brightness + translateY */
button {
  padding: 8px 20px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 14px;
  box-shadow: var(--border-subtle);
  transition: filter 0.2s, transform 0.2s;
}
button:hover:not(:disabled) {
  filter: brightness(1.08);
  transform: translateY(-1px);
  box-shadow: 0 0 20px rgba(124,92,252,0.35);
}
button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  filter: none;
  transform: none;
}
/* Attach button: subtle glass style */
.attach-btn {
  padding: 8px 12px;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  box-shadow: var(--border-subtle);
  cursor: pointer;
  font-size: 16px;
  color: var(--text-secondary);
  transition: filter 0.2s, transform 0.2s, box-shadow 0.2s;
}
.attach-btn:hover {
  filter: brightness(1.08);
  transform: translateY(-1px);
  box-shadow: 0 0 20px rgba(124,92,252,0.35);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.08);
}
</style>
