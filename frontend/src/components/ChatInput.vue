<template>
  <div class="input-wrapper">
    <!-- 附件预览区（在输入框上方） -->
    <div v-if="pendingImage || pendingFile" class="preview-bar">
      <div v-if="pendingImage" class="preview-item">
        <img :src="pendingImage.dataUrl || pendingImage.url" class="preview-thumb" />
        <span class="preview-name">{{ pendingImage.filename }}</span>
        <button class="remove-btn" :disabled="submitting" @click="pendingImage = null" title="移除图片" aria-label="移除图片">
          <X :size="11" aria-hidden="true" />
        </button>
      </div>
      <div v-if="pendingFile" class="preview-item file-item">
        <FileText class="preview-icon" :size="20" aria-hidden="true" />
        <span class="preview-name">{{ pendingFile.filename }}</span>
        <button class="remove-btn" :disabled="submitting" @click="pendingFile = null" title="移除文件" aria-label="移除文件">
          <X :size="11" aria-hidden="true" />
        </button>
      </div>
    </div>
    <div class="input-bar glass-enhanced">
      <input type="file" ref="fileInput" style="display:none" @change="handleFile" accept="image/*,.txt,.md,.py,.js,.json,.csv,.pdf,.docx" />
      <button class="attach-btn" :disabled="submitting" @click="$refs.fileInput.click()" title="添加附件" aria-label="添加附件">
        <Paperclip :size="17" aria-hidden="true" />
      </button>
      <button
        class="reasoning-btn"
        :class="{ on: reasoningEnabled }"
        :disabled="submitting"
        @click="toggleReasoning"
        :title="reasoningEnabled ? '深度思考：开' : '深度思考：关'"
        :aria-label="reasoningEnabled ? '关闭深度思考' : '开启深度思考'"
        :aria-pressed="reasoningEnabled"
      >
        <BrainCircuit :size="17" aria-hidden="true" />
      </button>
      <div ref="approvalRef" class="approval-control">
        <button
          class="approval-btn"
          :class="{ auto: approvalMode === 'auto' }"
          :disabled="submitting || isStreaming"
          @click="approvalMenuOpen = !approvalMenuOpen"
          :title="approvalMode === 'auto' ? '工具审批：自动审批' : '工具审批：请求批准'"
          :aria-label="approvalMode === 'auto' ? '自动审批工具操作' : '工具操作请求批准'"
          :aria-expanded="approvalMenuOpen"
        >
          <ShieldCheck v-if="approvalMode === 'auto'" :size="17" aria-hidden="true" />
          <ShieldAlert v-else :size="17" aria-hidden="true" />
        </button>
        <div v-if="approvalMenuOpen" class="approval-menu">
          <button
            :class="{ selected: approvalMode === 'ask' }"
            @click="selectApprovalMode('ask')"
          >
            <ShieldAlert :size="16" aria-hidden="true" />
            <span><strong>请求批准</strong><small>执行前逐次确认</small></span>
          </button>
          <button
            :class="{ selected: approvalMode === 'auto' }"
            @click="selectApprovalMode('auto')"
          >
            <ShieldCheck :size="16" aria-hidden="true" />
            <span><strong>自动审批</strong><small>本会话直接执行</small></span>
          </button>
        </div>
      </div>
      <textarea
        v-model="text"
        @keydown.enter.exact.prevent="send"
        :placeholder="pendingImage ? '添加文字描述（可选）...' : '输入消息... (Enter 发送)'"
        rows="1"
        ref="textareaRef"
        :disabled="submitting"
      ></textarea>
      <button
        class="mic-btn"
        :class="{ recording: isRecording }"
        @click="toggleVoice"
        :title="isRecording ? '点击停止录音' : '语音输入'"
        :aria-label="isRecording ? '停止录音' : '语音输入'"
      >
        <Square v-if="isRecording" :size="15" fill="currentColor" aria-hidden="true" />
        <Mic v-else :size="17" aria-hidden="true" />
      </button>
      <button
        class="tts-btn"
        :class="{ on: autoTts }"
        @click="emit('toggle-tts')"
        :title="autoTts ? '语音输出：开' : '语音输出：关'"
        :aria-label="autoTts ? '关闭语音输出' : '开启语音输出'"
      >
        <Volume2 v-if="autoTts" :size="17" aria-hidden="true" />
        <VolumeX v-else :size="17" aria-hidden="true" />
      </button>
      <button
        v-if="isStreaming"
        class="stop-btn"
        :disabled="isStopping"
        @click="emit('stop')"
        :title="isStopping ? '正在停止生成' : '停止生成'"
        :aria-label="isStopping ? '正在停止生成' : '停止生成'"
      >
        <LoaderCircle v-if="isStopping" class="spin" :size="15" aria-hidden="true" />
        <Square v-else :size="13" fill="currentColor" aria-hidden="true" />
        <span>{{ isStopping ? '正在停止' : '停止' }}</span>
      </button>
      <button
        v-else
        class="send-btn ripple"
        @click="send"
        :disabled="submitting || !connected || (!text.trim() && !pendingImage && !pendingFile)"
        :title="submitting ? '等待服务端确认' : (connected ? '发送消息' : '连接未就绪')"
        :aria-label="connected ? '发送消息' : '连接未就绪，暂时无法发送'"
      >
        <LoaderCircle v-if="submitting" class="spin" :size="16" aria-hidden="true" />
        <Send v-else :size="16" aria-hidden="true" />
        <span>{{ submitting ? '确认中' : '发送' }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { BrainCircuit, FileText, LoaderCircle, Mic, Paperclip, Send, ShieldAlert, ShieldCheck, Square, Volume2, VolumeX, X } from 'lucide-vue-next'
import { useToast } from '../composables/useToast'

const props = defineProps({
  autoTts: { type: Boolean, default: false },
  isStreaming: { type: Boolean, default: false },
  isStopping: { type: Boolean, default: false },
  connected: { type: Boolean, default: false },
  approvalMode: { type: String, default: 'ask' },
})
const emit = defineEmits(['send', 'toggle-tts', 'stop', 'update:approval-mode'])
const text = ref('')
const textareaRef = ref(null)
const fileInput = ref(null)
const toast = useToast()
const pendingImage = ref(null)
const pendingFile = ref(null) // 非图片附件
const submitting = ref(false)
const reasoningEnabled = ref(localStorage.getItem('reasoning-enabled') === 'true')
const approvalMenuOpen = ref(false)
const approvalRef = ref(null)

function selectApprovalMode(mode) {
  approvalMenuOpen.value = false
  if (mode !== props.approvalMode) emit('update:approval-mode', mode)
}

function closeApprovalMenu(event) {
  if (!approvalRef.value?.contains(event.target)) approvalMenuOpen.value = false
}

function toggleReasoning() {
  reasoningEnabled.value = !reasoningEnabled.value
  localStorage.setItem('reasoning-enabled', String(reasoningEnabled.value))
}

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
async function send() {
  if (submitting.value) return
  const content = text.value.trim()
  const img = pendingImage.value
  const file = pendingFile.value
  if (!content && !img && !file) return
  if (!props.connected) {
    toast.warning('连接尚未就绪，消息已保留')
    return
  }

  let payload
  if (img) {
    payload = { text: content, image: img, reasoning_enabled: reasoningEnabled.value }
  } else if (file) {
    payload = { text: content, file, reasoning_enabled: reasoningEnabled.value }
  } else if (reasoningEnabled.value) {
    payload = { text: content, reasoning_enabled: true }
  } else {
    payload = content
  }

  submitting.value = true
  try {
    const accepted = await new Promise(resolve => {
      emit('send', payload, result => resolve(Boolean(result)))
    })
    if (!accepted) return

    text.value = ''
    pendingImage.value = null
    pendingFile.value = null
  } finally {
    submitting.value = false
  }
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

// textarea 自动调整高度
watch(text, () => {
  nextTick(() => {
    if (textareaRef.value) {
      textareaRef.value.style.height = 'auto'
      textareaRef.value.style.height = Math.min(textareaRef.value.scrollHeight, 120) + 'px'
    }
  })
})


// 自动保存草稿
const DRAFT_KEY = 'chat_draft'
let draftTimer = null

// 保存草稿到 localStorage
function saveDraft() {
  if (text.value.trim()) {
    localStorage.setItem(DRAFT_KEY, text.value)
  } else {
    localStorage.removeItem(DRAFT_KEY)
  }
}

// 恢复草稿
function restoreDraft() {
  const saved = localStorage.getItem(DRAFT_KEY)
  if (saved) {
    text.value = saved
    nextTick(() => {
      if (textareaRef.value) {
        textareaRef.value.style.height = 'auto'
        textareaRef.value.style.height = Math.min(textareaRef.value.scrollHeight, 120) + 'px'
      }
    })
  }
}

// 监听文本变化，防抖保存草稿
watch(text, () => {
  if (draftTimer) clearTimeout(draftTimer)
  draftTimer = setTimeout(saveDraft, 1000)
})

// 组件挂载时恢复草稿
onMounted(() => {
  restoreDraft()
  document.addEventListener('pointerdown', closeApprovalMenu)
})

onUnmounted(() => document.removeEventListener('pointerdown', closeApprovalMenu))
</script>

<style scoped>
.input-wrapper {
  position: relative;
  z-index: 20;
  width: min(100%, var(--chat-content-width));
  padding: 0 var(--chat-gutter) 12px;
  margin-inline: auto;
  box-sizing: border-box;
}

/* 附件预览区 */
.preview-bar {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  background: var(--surface-control);
  border-radius: var(--radius) var(--radius) 0 0;
  box-shadow: var(--ui-border);
  border-bottom: none;
  overflow-x: auto;
  animation: preview-enter 200ms cubic-bezier(0.2, 0.8, 0.2, 1) both;
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
  flex-shrink: 0;
  color: var(--text-secondary);
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
  background: var(--surface-control);
  border-radius: var(--radius);
  box-shadow: var(--ui-border);
  animation: input-enter 240ms cubic-bezier(0.2, 0.8, 0.2, 1) both;
}
/* 有图片预览时，输入栏顶部无圆角 */
.image-preview-bar + .input-bar {
  border-radius: 0 0 var(--radius) var(--radius);
}

textarea {
  flex: 1;
  min-width: 0;
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
.reasoning-btn,
.approval-btn,
.mic-btn {
  width: var(--control-height);
  height: var(--control-height);
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.10);
  cursor: pointer;
  color: var(--text-secondary);
  transition: color var(--motion-fast) var(--ease-standard), background var(--motion-fast) var(--ease-standard), box-shadow var(--motion-fast) var(--ease-standard), transform var(--motion-fast) var(--ease-standard);
  flex-shrink: 0;
}
.attach-btn:hover,
.reasoning-btn:hover,
.approval-btn:hover,
.mic-btn:hover {
  color: var(--text-primary);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
  transform: translateY(-1px);
}
.reasoning-btn.on {
  color: var(--primary);
  background: rgba(124, 92, 252, 0.15);
  box-shadow: 0 0 0 1px var(--primary);
}
.approval-control {
  position: relative;
  flex-shrink: 0;
}
.approval-btn.auto {
  color: #34d399;
  background: rgba(16, 185, 129, 0.12);
  box-shadow: 0 0 0 1px rgba(52, 211, 153, 0.55);
}
.approval-menu {
  position: absolute;
  left: 0;
  bottom: calc(100% + 10px);
  z-index: 40;
  width: 214px;
  padding: 6px;
  background: var(--surface-modal);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 8px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.34);
  backdrop-filter: blur(16px);
}
.approval-menu button {
  width: 100%;
  min-height: 50px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  color: var(--text-secondary);
  background: transparent;
  border: none;
  border-radius: 6px;
  text-align: left;
  cursor: pointer;
}
.approval-menu button:hover,
.approval-menu button.selected {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.08);
}
.approval-menu button.selected { box-shadow: inset 2px 0 0 var(--primary); }
.approval-menu span { display: flex; flex-direction: column; min-width: 0; }
.approval-menu strong { font-size: 13px; font-weight: 600; }
.approval-menu small { margin-top: 2px; color: var(--text-secondary); font-size: 11px; }
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
  width: var(--control-height);
  height: var(--control-height);
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.10);
  cursor: pointer;
  color: var(--text-secondary);
  transition: color var(--motion-fast) var(--ease-standard), background var(--motion-fast) var(--ease-standard), box-shadow var(--motion-fast) var(--ease-standard), transform var(--motion-fast) var(--ease-standard);
  flex-shrink: 0;
}
.tts-btn:hover {
  color: var(--text-primary);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
  transform: translateY(-1px);
}
.tts-btn.on {
  color: var(--primary);
  background: rgba(124, 92, 252, 0.15);
  box-shadow: 0 0 0 1px var(--primary);
}

.send-btn {
  min-width: 84px;
  height: var(--control-height);
  padding: 0 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 14px;
  transition: filter var(--motion-fast) var(--ease-standard), transform var(--motion-fast) var(--ease-standard), opacity var(--motion-fast) var(--ease-standard);
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
.spin { animation: spin 800ms linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.stop-btn {
  min-width: 84px;
  height: var(--control-height);
  padding: 0 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  background: rgba(239, 68, 68, 0.8);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 14px;
  transition: filter var(--motion-fast) var(--ease-standard), transform var(--motion-fast) var(--ease-standard);
  flex-shrink: 0;
}
.stop-btn:hover:not(:disabled) {
  filter: brightness(1.1);
  transform: translateY(-1px);
}
.stop-btn:disabled {
  cursor: wait;
  opacity: 0.78;
}

@keyframes input-enter {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes preview-enter {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
  .input-bar,
  .preview-bar {
    animation: none;
  }
}

@media (max-width: 767px) {
  .input-wrapper {
    width: 100vw;
    max-width: 100vw;
    padding: 0 12px 12px;
  }

  .input-bar {
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 6px;
    padding: 8px;
  }

  .input-bar textarea {
    grid-column: 1 / -1;
    grid-row: 1;
  }

  .attach-btn { grid-column: 1; grid-row: 2; }
  .reasoning-btn { grid-column: 2; grid-row: 2; }
  .approval-control { grid-column: 3; grid-row: 2; }
  .mic-btn { grid-column: 4; grid-row: 2; }
  .tts-btn { grid-column: 5; grid-row: 2; }
  .send-btn,
  .stop-btn { grid-column: 6; grid-row: 2; }

  .attach-btn,
  .reasoning-btn,
  .approval-btn,
  .mic-btn,
  .tts-btn,
  .send-btn,
  .stop-btn {
    width: var(--control-height);
    min-width: var(--control-height);
    padding: 0;
    justify-self: center;
  }

  .send-btn span,
  .stop-btn span {
    display: none;
  }

  textarea {
    width: 100%;
    box-sizing: border-box;
    padding: 8px;
  }
}
</style>
