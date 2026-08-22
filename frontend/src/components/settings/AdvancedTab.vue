<template>
  <div class="tab-content">
    <h2>高级配置</h2>
    <p class="tab-desc">调整 Agent 运行参数。模型与工具循环不设次数上限，任务会在主动停止、超时或重复调用保护触发时结束。点击保存按钮生效。</p>

    <div class="config-section">
      <div class="config-item">
        <div class="config-label">
          <span class="label-title">子 Agent 单轮输出上限 (Token)</span>
          <span class="label-desc">每次子 Agent 请求模型时可生成的最大 Token。模型服务商可能另有更低上限。</span>
        </div>
        <input type="number" v-model.number="config.subagent_max_tokens" :min="1024" :max="100000" :step="1024" class="num-input" />
      </div>

      <div class="config-item">
        <div class="config-label">
          <span class="label-title">子 Agent 最大执行轮次</span>
          <span class="label-desc">单个子 Agent 最多进行多少次模型决策。达到上限会如实返回 partial，避免长任务无止境调查。</span>
        </div>
        <input type="number" v-model.number="config.subagent_max_steps" :min="4" :max="256" :step="4" class="num-input" />
      </div>

      <div class="config-item">
        <div class="config-label">
          <span class="label-title">子 Agent 汇报上限 (字符)</span>
          <span class="label-desc">子 Agent 最终交接给主 Agent 的报告长度。较大报告会占用更多上下文。</span>
        </div>
        <input type="number" v-model.number="config.subagent_report_max_chars" :min="4000" :max="200000" :step="1000" class="num-input" />
      </div>

      <!-- 上下文长度 -->
      <div class="config-item">
        <div class="config-label">
          <span class="label-title">📏 上下文长度 (Token)</span>
          <span class="label-desc">发送给模型的最大 Token 数，接近上限时会自动压缩较早的上下文</span>
        </div>
        <input type="number" v-model.number="config.max_context" :min="2000" :max="1000000" :step="1000" class="num-input" />
      </div>

      <!-- Max Tokens -->
      <div class="config-item">
        <div class="config-label">
          <span class="label-title">📝 最大输出长度 (Token)</span>
          <span class="label-desc">单次回复的最大 Token 数</span>
        </div>
        <input type="number" v-model.number="config.max_tokens" :min="64" :max="100000" :step="256" class="num-input" />
      </div>

      <div class="config-item">
        <div class="config-label">
          <span class="label-title">工具结果上下文上限 (字符)</span>
          <span class="label-desc">单次工具结果最多保留多少内容给模型；同时作为文件读取的默认单次读取大小。</span>
        </div>
        <input type="number" v-model.number="config.tool_result_max_chars" :min="8000" :max="500000" :step="1000" class="num-input" />
      </div>

      <div class="config-item">
        <div class="config-label">
          <span class="label-title">命令输出上限 (字节)</span>
          <span class="label-desc">code_exec 保留的原始终端输出量。过大输出会增加上下文和传输开销。</span>
        </div>
        <input type="number" v-model.number="config.code_exec_output_max_bytes" :min="12000" :max="500000" :step="1000" class="num-input" />
      </div>

      <div class="config-item">
        <div class="config-label">
          <span class="label-title">工具超时时间（秒）</span>
          <span class="label-desc">单个工具超过这个时间没有返回时自动终止，避免文件读取或外部请求永久卡住</span>
        </div>
        <input type="number" v-model.number="config.tool_timeout" :min="10" :max="300" class="num-input" />
      </div>

      <div class="config-item">
        <div class="config-label">
          <span class="label-title">子 Agent 超时时间（秒）</span>
          <span class="label-desc">每个子 Agent 的总运行时限。安装依赖、构建等长操作可适当提高，不会影响普通工具超时。</span>
        </div>
        <input type="number" v-model.number="config.subagent_timeout" :min="30" :max="900" class="num-input" />
      </div>

      <div class="config-item">
        <div class="config-label">
          <span class="label-title">深度思考强度</span>
          <span class="label-desc">控制支持该参数的推理模型在速度与分析深度之间的取舍</span>
        </div>
        <div class="effort-control" role="group" aria-label="深度思考强度">
          <button
            v-for="option in effortOptions"
            :key="option.value"
            type="button"
            :class="{ active: config.reasoning_effort === option.value }"
            @click="config.reasoning_effort = option.value"
          >{{ option.label }}</button>
        </div>
      </div>

      <!-- Custom Instructions -->
      <div class="config-item full-width">
        <div class="config-label">
          <span class="label-title">📋 自定义指令</span>
          <span class="label-desc">追加到系统提示词末尾的自定义内容，对所有会话生效</span>
        </div>
        <textarea
          v-model="config.custom_instructions"
          placeholder="例：请用简洁的语气回答 / 回复时加上适当的 emoji / 始终用中文..."
          class="custom-textarea"
          rows="4"
        ></textarea>
      </div>
    </div>

    <div class="config-footer">
      <button class="btn-reset" @click="resetDefaults">恢复默认值</button>
      <button class="btn-save" :disabled="saving" @click="save">保存</button>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useToast } from '../../composables/useToast'

const toast = useToast()

const config = reactive({
  subagent_max_tokens: 32768,
  subagent_max_steps: 64,
  subagent_report_max_chars: 60000,
  max_context: 1000000,
  max_tokens: 100000,
  tool_result_max_chars: 100000,
  code_exec_output_max_bytes: 100000,
  tool_timeout: 120,
  subagent_timeout: 300,
  reasoning_effort: 'medium',
  custom_instructions: '',
})

const effortOptions = [
  { value: 'low', label: '低' },
  { value: 'medium', label: '中' },
  { value: 'high', label: '高' },
]

const defaults = { ...config }
const saving = ref(false)

const numericFields = {
  subagent_max_tokens: [1024, 100000],
  subagent_max_steps: [4, 256],
  subagent_report_max_chars: [4000, 200000],
  max_context: [2000, 1000000],
  max_tokens: [256, 100000],
  tool_result_max_chars: [8000, 500000],
  code_exec_output_max_bytes: [12000, 500000],
  tool_timeout: [10, 300],
  subagent_timeout: [30, 900],
}

function buildPayload() {
  const effort = effortOptions.some(option => option.value === config.reasoning_effort)
    ? config.reasoning_effort
    : 'medium'
  const payload = {
    custom_instructions: config.custom_instructions || '',
    reasoning_effort: effort,
  }
  for (const [key, [min, max]] of Object.entries(numericFields)) {
    const value = Number(config[key])
    if (!Number.isFinite(value) || !Number.isInteger(value) || value < min || value > max) {
      throw new Error(`${key} 必须是 ${min} 到 ${max} 之间的整数`)
    }
    payload[key] = value
  }
  return payload
}

function responseError(data, status) {
  if (typeof data?.detail === 'string') return data.detail
  if (Array.isArray(data?.detail)) {
    return data.detail.map(item => item.msg || String(item)).join('; ')
  }
  return `HTTP ${status}`
}

async function loadConfig() {
  try {
    const resp = await fetch('/api/config/agent')
    const data = await resp.json()
    Object.assign(config, data)
  } catch {}
}

async function save() {
  if (saving.value) return
  saving.value = true
  try {
    const payload = buildPayload()
    const resp = await fetch('/api/config/agent', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    const data = await resp.json().catch(() => ({}))
    if (!resp.ok) throw new Error(responseError(data, resp.status))
    toast.success('保存成功')
  } catch (e) {
    toast.error('保存失败: ' + e.message)
  } finally {
    saving.value = false
  }
}

async function resetDefaults() {
  Object.assign(config, defaults)
  await save()
}

onMounted(loadConfig)
</script>

<style scoped>
.tab-desc { font-size: 13px; color: var(--text-secondary); margin-bottom: 20px; }

.config-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.config-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-radius: 10px;
  background: rgba(20, 20, 40, 0.45);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.08);
  transition: box-shadow 0.2s;
}
.config-item:hover {
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.18);
}
.config-item.full-width {
  flex-direction: column;
  align-items: stretch;
  gap: 12px;
}

.config-label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-width: 0;
}
.label-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.label-desc {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.4;
}

.num-input {
  width: 100px;
  padding: 6px 10px;
  border-radius: 6px;
  background: rgba(20, 20, 40, 0.60);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.15);
  border: none;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
  text-align: center;
  font-variant-numeric: tabular-nums;
  outline: none;
  transition: box-shadow 0.2s;
}
.num-input:focus {
  box-shadow: 0 0 0 1px var(--primary);
}

.effort-control {
  display: grid;
  grid-template-columns: repeat(3, 42px);
  height: 32px;
  padding: 2px;
  border-radius: 6px;
  background: rgba(20, 20, 40, 0.60);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.15);
}
.effort-control button {
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 12px;
}
.effort-control button.active {
  background: var(--primary);
  color: #fff;
}

.custom-textarea {
  width: 100%;
  padding: 10px 14px;
  border-radius: 8px;
  background: rgba(20, 20, 40, 0.60);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.12);
  border: none;
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.6;
  resize: vertical;
  min-height: 80px;
  font-family: inherit;
  transition: box-shadow 0.2s;
}
.custom-textarea:focus {
  outline: none;
  box-shadow: 0 0 0 1px var(--primary);
}
.custom-textarea::placeholder {
  color: rgba(255, 255, 255, 0.25);
}

.config-footer {
  margin-top: 24px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
.btn-reset {
  padding: 8px 18px;
  border-radius: 8px;
  background: rgba(20, 20, 40, 0.60);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.15);
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
}
.btn-reset:hover {
  color: var(--text-primary);
  box-shadow: 0 0 0 1px rgba(255, 100, 100, 0.4);
}
.btn-save {
  padding: 8px 24px;
  border-radius: 8px;
  background: var(--primary);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  transition: filter 0.2s, transform 0.2s;
}
.btn-save:hover {
  filter: brightness(1.1);
  transform: translateY(-1px);
}
.btn-save:disabled {
  opacity: 0.55;
  cursor: default;
  transform: none;
}

@media (max-width: 640px) {
  .config-item:not(.full-width) { align-items: flex-start; flex-direction: column; gap: 10px; }
  .num-input { width: 100%; }
  .effort-control { width: 100%; grid-template-columns: repeat(3, 1fr); }
}
</style>
