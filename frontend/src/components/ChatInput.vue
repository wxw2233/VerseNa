<template>
  <div class="input-wrapper">
    <!-- 附件预览区（在输入框上方） -->
    <div v-if="pendingImage || pendingFile" class="preview-bar">
      <div v-if="pendingImage" class="preview-item">
        <img :src="pendingImage.dataUrl || pendingImage.url" class="preview-thumb" />
        <span class="preview-name">{{ pendingImage.filename }}</span>
        <button class="remove-btn" @click="pendingImage = null">×</button>
      </div>
      <div v-if="pendingFile" class="preview-item file-item">
        <span class="preview-icon">📄</span>
        <span class="preview-name">{{ pendingFile.filename }}</span>
        <button class="remove-btn" @click="pendingFile = null">×</button>
      </div>
    </div>
    <div class="input-bar">
      <input type="file" ref="fileInput" style="display:none" @change="handleFile" accept="image/*,.txt,.md,.py,.js,.json,.csv,.pdf,.docx" />
      <button class="attach-btn" @click="$refs.fileInput.click()">📎</button>
      <textarea
        v-model="text"
        @keydown.enter.exact.prevent="send"
        :placeholder="pendingImage ? '添加文字描述（可选）...' : '输入消息... (Enter 发送)'"
        rows="1"
        ref="textareaRef"
      ></textarea>
      <button
        class="mic-btn"
        :class="{ recording: isRecording }"
        @click="toggleVoice"
        :title="isRecording ? '点击停止录音' : '语音输入'"
      >{{ isRecording ? '⏹' : '🎤' }}</button>
      <button
        class="tts-btn"
        :class="{ on: autoTts }"
        @click="emit('toggle-tts')"
        :title="autoTts ? '语音输出：开' : '语音输出：关'"
      >{{ autoTts ? '🔊' : '🔇' }}</button>
      <button class="send-btn" @click="send" :disabled="!text.trim() && !pendingImage">发送</button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useToast } from '../composables/useToast'

const props = defineProps({
  autoTts: { type: Boolean, default: false },
})
const emit = defineEmits(['send', 'toggle-tts'])
const text = ref('')
const textareaRef = ref(null)
const fileInput = ref(null)
const toast = useToast()
const pendingImage = ref(null)
const pendingFile = ref(null) // 非图片附件

// --- 语音输入 ---
const isRecording = ref(false)
let recognition = null

function toggleVoice() {
  if (isRecording.value) stopRecording()
  else startRecording()
}

function startRecording() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SpeechRecognition) {
    toast.error('当前浏览器不支持语音输入，请使用 Chrome')
    return
  }
  recognition = new SpeechRecognition()
  recognition.lang = 'zh-CN'
  recognition.interimResults = true
  recognition.continuous = true
  let finalTranscript = ''
  recognition.onresult = (event) => {
    let interim = ''
    for (let i = event.resultIndex; i < event.results.length; i++) {
      if (event.results[i].isFinal) finalTranscript += event.results[i][0].transcript
      else interim += event.results[i][0].transcript
    }
    text.value = finalTranscript + interim
  }
  recognition.onerror = (event) => {
    if (event.error !== 'aborted') toast.warning('语音识别出错: ' + event.error)
    isRecording.value = false
  }
  recognition.onend = () => { isRecording.value = false }
  recognition.start()
  isRecording.value = true
  toast.info('开始录音，请说话...')
}

function stopRecording() {
  if (recognition) { recognition.stop(); recognition = null }
  isRecording.value = false
}

// --- 发送 ---
function send() {
  const content = text.value.trim()
  const img = pendingImage.value
  const file = pendingFile.value
  if (!content && !img && !file) return

  if (img) {
    emit('send', { text: content, image: img })
  } else if (file) {
    emit('send', { text: content, file: file })
  } else {
    emit('send', content)
  }
  text.value = ''
  pendingImage.value = null
  pendingFile.value = null
}

// --- 文件上传 ---
async function handleFile(e) {
  const file = e.target.files[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  try {
    const resp = await fetch('/api/upload', { method: 'POST', body: formData })
    const data = await resp.json()
    if (data.is_image) {
      pendingImage.value = {
        url: data.image_url,
        dataUrl: data.image_data_url,
        filename: data.filename,
      }
    } else {
      pendingFile.value = {
        filename: data.filename,
        saved_as: data.saved_as,
        text_preview: data.text_preview,
        full_text: data.full_text,
      }
    }
  } catch (err) {
    toast.error('上传失败: ' + err.message)
  }
  e.target.value = ''
}

function removeImage() {
  pendingImage.value = null
}
</script>

<style scoped>
.input-wrapper {
  width: 100%;
  padding: 0 16px 12px;
}

/* 附件预览区 */
.preview-bar {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(20, 20, 40, 0.60);
  border-radius: var(--radius) var(--radius) 0 0;
  box-shadow: var(--ui-border);
  border-bottom: none;
  overflow-x: auto;
}
.preview-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
}
.preview-thumb {
  width: 56px;
  height: 56px;
  object-fit: cover;
  border-radius: 8px;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.15);
}
.file-item {
  padding: 6px 10px;
  background: rgba(255,255,255,0.06);
  border-radius: 8px;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.10);
}
.preview-icon {
  font-size: 20px;
}
.preview-name {
  font-size: 12px;
  color: var(--text-secondary);
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.remove-btn {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 18px;
  height: 18px;
  padding: 0;
  background: rgba(239, 68, 68, 0.9);
  color: white;
  border: none;
  border-radius: 50%;
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: none;
  line-height: 1;
}

/* 输入栏 */
.input-bar {
  display: flex;
  gap: 8px;
  padding: 10px 16px;
  align-items: flex-end;
  background: rgba(20, 20, 40, 0.60);
  border-radius: var(--radius);
  box-shadow: var(--ui-border);
}
/* 有图片预览时，输入栏顶部无圆角 */
.image-preview-bar + .input-bar {
  border-radius: 0 0 var(--radius) var(--radius);
}

textarea {
  flex: 1;
  resize: none;
  border: none;
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
  max-height: 120px;
  font-family: inherit;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.10);
  transition: box-shadow 0.2s;
}
textarea:focus {
  box-shadow: 0 0 0 1px var(--primary);
}

.attach-btn,
.mic-btn {
  padding: 8px 12px;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.10);
  cursor: pointer;
  font-size: 16px;
  color: var(--text-secondary);
  transition: all 0.2s;
  flex-shrink: 0;
}
.attach-btn:hover,
.mic-btn:hover {
  color: var(--text-primary);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
}
.mic-btn.recording {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
  box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.4);
  animation: pulse-recording 1.5s infinite;
}
@keyframes pulse-recording {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.tts-btn {
  padding: 8px 10px;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.10);
  cursor: pointer;
  font-size: 16px;
  color: var(--text-secondary);
  transition: all 0.2s;
  flex-shrink: 0;
}
.tts-btn:hover {
  color: var(--text-primary);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
}
.tts-btn.on {
  color: var(--primary);
  background: rgba(124, 92, 252, 0.15);
  box-shadow: 0 0 0 1px var(--primary);
}

.send-btn {
  padding: 8px 20px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 14px;
  transition: filter 0.2s, transform 0.2s;
  flex-shrink: 0;
}
.send-btn:hover:not(:disabled) {
  filter: brightness(1.08);
  transform: translateY(-1px);
}
.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  filter: none;
  transform: none;
}
</style>
