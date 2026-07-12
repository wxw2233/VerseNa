<template>
  <div class="input-bar">
    <textarea
      v-model="text"
      @keydown.enter.exact.prevent="send"
      placeholder="输入消息... (Enter 发送)"
      rows="1"
      ref="textareaRef"
    ></textarea>
    <button @click="send" :disabled="!text.trim()">发送</button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
const emit = defineEmits(['send'])
const text = ref('')
const textareaRef = ref(null)

function send() {
  if (text.value.trim()) {
    emit('send', text.value.trim())
    text.value = ''
  }
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
</style>
