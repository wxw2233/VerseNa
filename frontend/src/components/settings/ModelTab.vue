<template>
  <div class="tab-content">
    <h2>模型配置</h2>

    <!-- 提供商标签栏 -->
    <div class="provider-tabs">
      <button
        v-for="p in providers"
        :key="p.id"
        class="provider-tab"
        :class="{ active: activeProvider === p.id, configured: p.has_key }"
        @click="activeProvider = p.id"
      >
        <span class="provider-dot" :class="{ on: p.enabled && p.has_key }"></span>
        {{ p.name }}
      </button>
      <button class="provider-tab add-tab" @click="showAddCustom = true">+ 自定义</button>
    </div>

    <!-- 提供商配置面板 -->
    <div v-if="currentProvider" class="provider-panel">
      <div class="panel-header">
        <span class="panel-name">{{ currentProvider.name }}</span>
        <span v-if="currentProvider.base_url" class="panel-url">{{ currentProvider.base_url }}</span>
      </div>

      <!-- API Key -->
      <div class="form-row">
        <label>API Key <span v-if="currentProvider.has_key" class="key-saved">✓ 已保存</span></label>
        <div class="input-group">
          <input
            v-model="providerForm.api_key"
            :type="showKey ? 'text' : 'password'"
            :placeholder="currentProvider.has_key ? '已保存，留空则保留原 key' : 'sk-...'"
          />
          <button class="btn-icon" @click="showKey = !showKey">{{ showKey ? '🙈' : '👁' }}</button>
        </div>
      </div>

      <!-- 自定义提供商的 base_url -->
      <div v-if="currentProvider.is_custom" class="form-row">
        <label>Base URL</label>
        <input v-model="providerForm.base_url" placeholder="https://api.example.com/v1" />
      </div>

      <!-- TTS 接口路径（自定义提供商） -->
      <div v-if="currentProvider.is_custom" class="form-row">
        <label>TTS 接口路径 <span class="hint-inline">（默认 /audio/speech）</span></label>
        <input v-model="providerForm.tts_endpoint" placeholder="/audio/speech" />
      </div>

      <!-- 操作按钮 -->
      <div class="form-actions">
        <button class="btn-test" @click="testConnection" :disabled="testing">
          {{ testing ? '测试中...' : '🔗 测试连接' }}
        </button>
        <button class="btn-save" @click="saveProvider">💾 保存</button>
        <button v-if="providerForm.selected_models.length > 0" class="btn-sm-refresh" @click="refreshModels" title="刷新模型列表">🔄</button>
        <label class="enable-toggle">
          <input type="checkbox" v-model="providerForm.enabled" />
          启用
        </label>
      </div>

      <!-- 测试结果 -->
      <div v-if="testResult" class="test-result" :class="testResult.success ? 'success' : 'error'">
        <span v-if="testResult.success">✓ 连接成功，发现 {{ testResult.models.length }} 个模型</span>
        <span v-else>✕ 连接失败: {{ testResult.error }}</span>
      </div>

      <!-- 模型列表 -->
      <div v-if="availableModels.length > 0" class="model-section">
        <label class="section-label">可用模型（勾选要启用的）</label>
        <div class="model-grid">
          <label v-for="m in availableModels" :key="m" class="model-check">
            <input
              type="checkbox"
              :value="m"
              v-model="providerForm.selected_models"
            />
            <span class="model-name">{{ m }}</span>
          </label>
        </div>
      </div>

      <!-- 删除自定义 -->
      <div v-if="currentProvider.is_custom" class="danger-zone">
        <button class="btn-delete" @click="deleteProvider">🗑 删除此提供商</button>
      </div>
    </div>

    <!-- 分隔线 -->
    <hr class="divider" />

    <!-- 模型角色分配 -->
    <div class="roles-section">
      <h3>模型角色分配</h3>
      <p class="roles-hint">为不同任务分配模型。对话模型是主力，图片识别/生成可选配。</p>

      <div class="role-card" v-for="role in roleDefs" :key="role.key">
        <div class="role-icon">{{ role.icon }}</div>
        <div class="role-info">
          <div class="role-name">{{ role.label }}</div>
          <div class="role-desc">{{ role.desc }}</div>
        </div>
        <div class="role-selects">
          <select v-model="roleForm[role.key].provider" @change="onRoleProviderChange(role.key)">
            <option value="">未分配</option>
            <option v-for="p in enabledProviders" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
          <select v-model="roleForm[role.key].model" :disabled="!roleForm[role.key].provider">
            <option value="">选择模型</option>
            <option v-for="m in getModelsForProvider(roleForm[role.key].provider, role.modelType)" :key="m" :value="m">{{ m }}</option>
          </select>
        </div>
      </div>

      <button class="btn-save-roles" @click="saveRoles">保存角色分配</button>
    </div>

    <!-- 添加自定义提供商弹窗 -->
    <div v-if="showAddCustom" class="modal-overlay" @click.self="showAddCustom = false">
      <div class="modal">
        <div class="modal-title">添加自定义提供商</div>
        <div class="form-row">
          <label>名称</label>
          <input v-model="customForm.name" placeholder="我的API" />
        </div>
        <div class="form-row">
          <label>Base URL</label>
          <input v-model="customForm.base_url" placeholder="https://api.example.com/v1" />
        </div>
        <div class="form-row">
          <label>API Key</label>
          <input v-model="customForm.api_key" type="password" placeholder="sk-..." />
        </div>
        <div class="modal-actions">
          <button class="btn-cancel" @click="showAddCustom = false">取消</button>
          <button class="btn-save" @click="addCustomProvider">添加</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useToast } from '../../composables/useToast'

const toast = useToast()
const providers = ref([])
const activeProvider = ref('')
const showKey = ref(false)
const testing = ref(false)
const testResult = ref(null)
const showAddCustom = ref(false)
const availableModels = ref([])

const providerForm = reactive({
  api_key: '',
  base_url: '',
  tts_endpoint: '',
  enabled: true,
  selected_models: [],
})

const roleForm = reactive({
  chat: { provider: '', model: '' },
  vision: { provider: '', model: '' },
  image_gen: { provider: '', model: '' },
  tts: { provider: '', model: '' },
})

const customForm = reactive({
  name: '',
  base_url: '',
  api_key: '',
})

const roleDefs = [
  { key: 'chat', icon: '💬', label: '对话模型', desc: '主力对话模型，支持工具调用', modelType: 'all' },
  { key: 'vision', icon: '👁', label: '图片识别', desc: '理解图片内容，需要视觉能力', modelType: 'vision' },
  { key: 'image_gen', icon: '🎨', label: '图片生成', desc: '根据文字生成图片', modelType: 'image' },
  { key: 'tts', icon: '🎤', label: '语音合成', desc: '将文字转为语音，支持音色克隆', modelType: 'tts' },
]

const currentProvider = computed(() =>
  providers.value.find(p => p.id === activeProvider.value)
)

// 只要有 API Key 就出现在角色下拉（enabled 是启用/禁用提供商，不影响角色分配）
const enabledProviders = computed(() =>
  providers.value.filter(p => p.has_key)
)

// 提供商预设模型的硬编码后备，防止 providers.value 里数据不全
const PRESET_MODELS = {
  deepseek: { models: ['deepseek-chat', 'deepseek-reasoner'], vision: [], image: [], tts: [] },
  openai: { models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'], vision: ['gpt-4o', 'gpt-4-turbo'], image: ['dall-e-3', 'dall-e-2'], tts: ['tts-1', 'tts-1-hd'] },
  siliconflow: { models: ['deepseek-ai/DeepSeek-V3', 'Qwen/Qwen2.5-72B-Instruct'], vision: ['deepseek-ai/deepseek-vl2'], image: ['stabilityai/stable-diffusion-3-medium'], tts: ['fishaudio/fish-speech-1.5'] },
  zhipu: { models: ['glm-4-flash', 'glm-4-plus', 'glm-4'], vision: ['glm-4v-flash', 'glm-4v-plus'], image: ['cogview-3-flash', 'cogview-3-plus'], tts: [] },
  moonshot: { models: ['moonshot-v1-8k', 'moonshot-v1-32k', 'moonshot-v1-128k'], vision: [], image: [], tts: [] },
  qwen: { models: ['qwen-turbo', 'qwen-plus', 'qwen-max'], vision: ['qwen-vl-plus', 'qwen-vl-max'], image: ['wanx-v1'], tts: ['cosyvoice-v1'] },
  baidu: { models: ['ernie-4.0-turbo-8k', 'ernie-4.0-8k', 'ernie-3.5-8k'], vision: [], image: [], tts: [] },
}

function getModelsForProvider(providerId, modelType) {
  if (!providerId) return []
  const p = providers.value.find(x => x.id === providerId)
  const preset = PRESET_MODELS[providerId]
  // 合并：已选模型 + providers 里的模型 + 预设后备
  const selected = p?.selected_models || []
  const fromApi = p?.models || []
  const fromPreset = preset?.models || []
  const all = [...new Set([...selected, ...fromApi, ...fromPreset])]
  if (all.length === 0) return []
  if (modelType === 'vision') {
    const capable = (p?.vision_models?.length ? p.vision_models : preset?.vision) || []
    const filtered = all.filter(m => capable.includes(m))
    return filtered.length > 0 ? filtered : all
  }
  if (modelType === 'image') {
    const capable = (p?.image_models?.length ? p.image_models : preset?.image) || []
    const filtered = all.filter(m => capable.includes(m))
    return filtered.length > 0 ? filtered : all
  }
  if (modelType === 'tts') {
    const capable = preset?.tts || []
    // 先过滤有 TTS 能力的，没有则返回全部已选/预设模型（自定义提供商可能所有模型都支持 TTS）
    const filtered = all.filter(m => capable.includes(m))
    return filtered.length > 0 ? filtered : all
  }
  return all
}

async function loadProviders() {
  try {
    const resp = await fetch('/api/models/providers')
    providers.value = await resp.json()
    if (!activeProvider.value && providers.value.length > 0) {
      activeProvider.value = providers.value[0].id
    }
  } catch (e) {
    console.error('Failed to load providers:', e)
  }
}

async function loadActiveModels() {
  try {
    const resp = await fetch('/api/models/active')
    const data = await resp.json()
    roleForm.chat = data.chat || { provider: '', model: '' }
    roleForm.vision = data.vision || { provider: '', model: '' }
    roleForm.image_gen = data.image_gen || { provider: '', model: '' }
    roleForm.tts = data.tts || { provider: '', model: '' }
  } catch {}
}

// 当切换提供商时，填充表单
function fillProviderForm() {
  const p = currentProvider.value
  if (!p) return
  providerForm.api_key = ''
  providerForm.base_url = p.base_url || ''
  providerForm.tts_endpoint = p.tts_endpoint || ''
  // 有 key 的提供商默认启用
  providerForm.enabled = p.has_key ? true : (p.enabled !== false)
  providerForm.selected_models = [...(p.selected_models || [])]
  // 合并：已选 + API 返回 + 预设后备
  const preset = PRESET_MODELS[p.id]
  const fromApi = p.models || []
  const fromPreset = preset?.models || []
  const selected = p.selected_models || []
  const allModels = [...new Set([...selected, ...fromApi, ...fromPreset])]
  availableModels.value = allModels
  testResult.value = null
}

async function testConnection() {
  if (!providerForm.api_key) {
    toast.warning('请先填写 API Key')
    return
  }
  testing.value = true
  testResult.value = null
  try {
    const resp = await fetch('/api/models/providers/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider_id: activeProvider.value,
        api_key: providerForm.api_key,
        base_url: providerForm.base_url,
      })
    })
    const data = await resp.json()
    testResult.value = data
    if (data.success && data.models.length > 0) {
      availableModels.value = data.models
      // 自动选中所有模型
      providerForm.selected_models = [...data.models]
    }
  } catch (e) {
    testResult.value = { success: false, error: e.message }
  } finally {
    testing.value = false
  }
}

async function saveProvider() {
  try {
    const p = currentProvider.value
    await fetch('/api/models/providers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider_id: activeProvider.value,
        api_key: providerForm.api_key,
        base_url: providerForm.base_url,
        tts_endpoint: providerForm.tts_endpoint,
        enabled: providerForm.enabled,
        selected_models: providerForm.selected_models,
        vision_models: p?.vision_models || [],
        image_models: p?.image_models || [],
        is_custom: p?.is_custom || false,
        name: p?.name || '',
      })
    })
    toast.success('提供商配置已保存')
    await loadProviders()
  } catch (e) {
    toast.error('保存失败: ' + e.message)
  }
}

async function saveRoles() {
  try {
    for (const [role, config] of Object.entries(roleForm)) {
      if (config.provider && config.model) {
        await fetch('/api/models/active', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ role, provider: config.provider, model: config.model })
        })
      }
    }
    toast.success('角色分配已保存')
  } catch (e) {
    toast.error('保存失败: ' + e.message)
  }
}

function onRoleProviderChange(roleKey) {
  roleForm[roleKey].model = ''
}

async function addCustomProvider() {
  if (!customForm.name || !customForm.base_url) {
    toast.warning('请填写名称和 Base URL')
    return
  }
  const id = 'custom_' + customForm.name.toLowerCase().replace(/[^a-z0-9]/g, '_').slice(0, 20)
  try {
    await fetch('/api/models/providers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider_id: id,
        api_key: customForm.api_key,
        base_url: customForm.base_url,
        name: customForm.name,
        enabled: true,
        is_custom: true,
      })
    })
    showAddCustom.value = false
    customForm.name = ''
    customForm.base_url = ''
    customForm.api_key = ''
    await loadProviders()
    activeProvider.value = id
    toast.success('自定义提供商已添加')
  } catch (e) {
    toast.error('添加失败: ' + e.message)
  }
}

async function refreshModels() {
  // 用已保存的 key 重新测试连接（不发 api_key，后端自动用已保存的）
  const p = currentProvider.value
  if (!p?.has_key) {
    toast.warning('请先保存 API Key')
    return
  }
  testing.value = true
  try {
    const resp = await fetch('/api/models/providers/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider_id: activeProvider.value,
        api_key: '',
        base_url: providerForm.base_url,
      })
    })
    const data = await resp.json()
    if (data.success && data.models.length > 0) {
      availableModels.value = data.models
      providerForm.selected_models = [...data.models]
      toast.success(`刷新成功，发现 ${data.models.length} 个模型`)
    } else {
      toast.error(data.error || '刷新失败')
    }
  } catch (e) {
    toast.error('刷新失败: ' + e.message)
  } finally {
    testing.value = false
  }
}

async function deleteProvider() {
  if (!confirm(`确定删除「${currentProvider.value?.name}」？`)) return
  try {
    await fetch(`/api/models/providers/${activeProvider.value}`, { method: 'DELETE' })
    activeProvider.value = ''
    await loadProviders()
    toast.success('已删除')
  } catch (e) {
    toast.error('删除失败: ' + e.message)
  }
}

// 监听 activeProvider 变化
import { watch } from 'vue'
watch(activeProvider, () => {
  fillProviderForm()
})

onMounted(async () => {
  await loadProviders()
  await loadActiveModels()
  if (providers.value.length > 0) {
    activeProvider.value = providers.value[0].id
    fillProviderForm()
  }
})
</script>

<style scoped>
/* Provider tabs */
.provider-tabs {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}
.provider-tab {
  padding: 6px 16px;
  border-radius: var(--radius-sm);
  background: rgba(20, 20, 40, 0.60);
  color: var(--text-secondary);
  border: none;
  cursor: pointer;
  font-size: 13px;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
  transition: all 0.15s;
  display: flex;
  align-items: center;
  gap: 6px;
}
.provider-tab:hover {
  box-shadow: 0 0 0 1px var(--primary);
  filter: brightness(1.05);
}
.provider-tab.active {
  background: var(--primary);
  color: #fff;
  box-shadow: none;
}
.provider-tab.configured:not(.active) {
  border-left: 3px solid var(--primary);
}
.provider-tab.add-tab {
  border-style: dashed;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.15);
}
.provider-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(255,255,255,0.2);
}
.provider-dot.on {
  background: #22c55e;
}

/* Provider panel */
.provider-panel {
  background: rgba(20, 20, 40, 0.60);
  box-shadow: var(--ui-border);
  border-radius: var(--radius);
  padding: 20px;
  margin-bottom: 20px;
}
.panel-header {
  margin-bottom: 16px;
}
.panel-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}
.panel-url {
  font-size: 12px;
  color: var(--text-secondary);
  margin-left: 8px;
  font-family: monospace;
}

/* Form */
.form-row {
  margin-bottom: 14px;
}
.form-row label {
  display: block;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}
.form-row input, .form-row select {
  width: 100%;
  padding: 8px 12px;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
  border-radius: var(--radius-sm);
  background: rgba(20, 20, 40, 0.60);
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
  border: none;
  transition: box-shadow 0.2s;
}
.form-row input:focus {
  box-shadow: 0 0 0 1px var(--primary);
}
.input-group {
  display: flex;
  gap: 6px;
}
.input-group input {
  flex: 1;
}
.btn-icon {
  width: 40px;
  background: rgba(20, 20, 40, 0.60);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 14px;
  transition: all 0.15s;
}
.btn-icon:hover {
  box-shadow: 0 0 0 1px var(--primary);
}

/* Actions */
.form-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}
.btn-test {
  padding: 8px 16px;
  background: rgba(20, 20, 40, 0.60);
  color: var(--text-primary);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.15s;
}
.btn-test:hover:not(:disabled) {
  box-shadow: 0 0 0 1px var(--primary);
  filter: brightness(1.05);
}
.btn-test:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-save {
  padding: 8px 16px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
  transition: filter 0.15s;
}
.btn-save:hover {
  filter: brightness(1.08);
}
.btn-sm-refresh {
  padding: 6px 10px;
  background: rgba(20, 20, 40, 0.60);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 14px;
  transition: all 0.15s;
}
.btn-sm-refresh:hover {
  box-shadow: 0 0 0 1px var(--primary);
  filter: brightness(1.05);
}
.key-saved {
  font-size: 11px;
  color: #22c55e;
  font-weight: 400;
  margin-left: 6px;
}
.hint-inline {
  font-size: 11px;
  color: var(--text-secondary);
  font-weight: 400;
}
.enable-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  margin-left: auto;
}
.enable-toggle input {
  accent-color: var(--primary);
}

/* Test result */
.test-result {
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  margin-bottom: 14px;
}
.test-result.success {
  background: rgba(34, 197, 94, 0.12);
  color: #22c55e;
}
.test-result.error {
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
}

/* Model section */
.model-section {
  margin-bottom: 16px;
}
.section-label {
  display: block;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}
.model-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-height: 200px;
  overflow-y: auto;
  padding: 2px;
}
.model-check {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  background: rgba(20, 20, 40, 0.60);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.15);
  border-radius: 16px;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-secondary);
  transition: all 0.15s;
}
.model-check:hover {
  box-shadow: 0 0 0 1px var(--primary);
  color: var(--text-primary);
}
.model-check:has(input:checked) {
  background: rgba(124, 92, 252, 0.15);
  box-shadow: 0 0 0 1px var(--primary);
  color: var(--primary);
}
.model-check input {
  accent-color: var(--primary);
  margin: 0;
}
.model-name {
  font-family: monospace;
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Danger zone */
.danger-zone {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(239, 68, 68, 0.2);
}
.btn-delete {
  padding: 6px 14px;
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.15s;
}
.btn-delete:hover {
  background: rgba(239, 68, 68, 0.2);
}

/* Divider */
.divider {
  border: none;
  box-shadow: 0 -1px 0 rgba(20, 20, 40, 0.60);
  margin: 28px 0;
  height: 1px;
}

/* Roles section */
.roles-section h3 {
  font-size: 16px;
  margin-bottom: 6px;
}
.roles-hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 16px;
}
.role-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  background: rgba(20, 20, 40, 0.60);
  box-shadow: var(--ui-border);
  border-radius: var(--radius);
  margin-bottom: 10px;
}
.role-icon {
  font-size: 24px;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(20, 20, 40, 0.60);
  border-radius: 8px;
  flex-shrink: 0;
}
.role-info {
  flex: 1;
  min-width: 0;
}
.role-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.role-desc {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}
.role-selects {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
.role-selects select {
  padding: 6px 10px;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.20);
  border-radius: var(--radius-sm);
  background: rgba(20, 20, 40, 0.60);
  color: var(--text-primary);
  font-size: 12px;
  border: none;
  outline: none;
  max-width: 200px;
}
.role-selects select:focus {
  box-shadow: 0 0 0 1px var(--primary);
}
.role-selects select:disabled {
  opacity: 0.4;
}
.btn-save-roles {
  margin-top: 14px;
  padding: 10px 24px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 14px;
  transition: filter 0.15s;
}
.btn-save-roles:hover {
  filter: brightness(1.08);
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal {
  background: rgba(15, 15, 30, 0.9);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: var(--radius);
  padding: 24px;
  width: 380px;
}
.modal-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 16px;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}
.btn-cancel {
  padding: 8px 16px;
  background: rgba(20, 20, 40, 0.60);
  color: var(--text-secondary);
  border: 1px solid rgba(255, 255, 255, 0.20);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
}
.btn-cancel:hover {
  background: rgba(20, 20, 40, 0.60);
}
</style>
