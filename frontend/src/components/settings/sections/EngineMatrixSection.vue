<template>
  <div class="engine-settings">
    <!-- 顶部标题区 -->
    <header class="es-header">
      <div class="es-header-info">
        <h4>⚡ 模型引擎</h4>
        <p>选择 AI 厂商并配置密钥，保存后立即生效。</p>
      </div>
      <n-space>
        <n-button :loading="testing" @click="handleTest">
          🔌 测试连接
        </n-button>
        <n-button type="primary" :loading="saving" @click="handleSave">
          💾 保存配置
        </n-button>
      </n-space>
    </header>

    <!-- 连接状态指示 -->
    <n-alert
      v-if="connectionStatus !== 'idle'"
      :type="connectionStatus === 'ok' ? 'success' : connectionStatus === 'error' ? 'error' : 'info'"
      :title="connectionStatus === 'ok' ? '✅ 连接正常' : connectionStatus === 'error' ? '❌ 连接失败' : '⏳ 测试中...'"
      closable
      @close="connectionStatus = 'idle'"
      style="margin-bottom: 16px"
    >
      {{ connectionMessage }}
    </n-alert>

    <!-- 厂商预设卡片网格 -->
    <section class="es-section">
      <div class="es-section-title">选择厂商</div>
      <div class="preset-grid">
        <div
          v-for="preset in presets"
          :key="preset.key"
          class="preset-card"
          :class="{
            active: selectedPreset === preset.key,
            domestic: preset.tags?.includes('domestic'),
          }"
          @click="selectPreset(preset)"
        >
          <div class="preset-icon">{{ preset.icon }}</div>
          <div class="preset-name">{{ preset.label }}</div>
          <div class="preset-tags">
            <span v-if="preset.recommended" class="preset-badge recommend">推荐</span>
            <span v-if="preset.tags?.includes('domestic')" class="preset-badge domestic">国内</span>
            <span v-if="preset.tags?.includes('free')" class="preset-badge free">免费</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 配置表单 -->
    <section class="es-section" v-if="selectedPreset">
      <div class="es-section-title">
        配置 {{ selectedPresetInfo?.label }}
        <n-tag v-if="selectedPresetInfo?.protocol" size="small" type="info" style="margin-left: 8px">
          {{ selectedPresetInfo?.protocol }}
        </n-tag>
      </div>

      <n-form label-placement="left" label-width="100" class="es-form">
        <!-- API Key -->
        <n-form-item label="API Key">
          <n-input
            v-model:value="formData.api_key"
            type="password"
            show-password-on="click"
            placeholder="输入你的 API Key"
            size="large"
          >
            <template #prefix>🔑</template>
          </n-input>
        </n-form-item>

        <!-- Base URL -->
        <n-form-item label="Base URL">
          <n-input
            v-model:value="formData.base_url"
            :placeholder="selectedPresetInfo?.default_base_url || 'https://api.example.com/v1'"
            size="large"
          >
            <template #prefix>🌐</template>
          </n-input>
        </n-form-item>

        <!-- 模型 ID -->
        <n-form-item label="模型">
          <n-auto-complete
            v-model:value="formData.model"
            :options="modelSuggestions"
            placeholder="输入模型名称（如 deepseek-chat）"
            size="large"
          >
            <template #prefix>🤖</template>
          </n-auto-complete>
        </n-form-item>

        <!-- 高级参数折叠 -->
        <n-collapse>
          <n-collapse-item title="⚙️ 高级参数" name="advanced">
            <n-grid :cols="2" :x-gap="16" :y-gap="12">
              <n-gi>
                <n-form-item label="温度">
                  <n-slider v-model:value="formData.temperature" :min="0" :max="2" :step="0.1" />
                  <span class="param-value">{{ formData.temperature }}</span>
                </n-form-item>
              </n-gi>
              <n-gi>
                <n-form-item label="最大 Token">
                  <n-input-number v-model:value="formData.max_tokens" :min="256" :max="200000" :step="1024" />
                </n-form-item>
              </n-gi>
              <n-gi>
                <n-form-item label="超时(秒)">
                  <n-input-number v-model:value="formData.timeout_seconds" :min="10" :max="3600" :step="30" />
                </n-form-item>
              </n-gi>
              <n-gi>
                <n-form-item label="协议">
                  <n-select v-model:value="formData.protocol" :options="protocolOptions" />
                </n-form-item>
              </n-gi>
            </n-grid>
          </n-collapse-item>
        </n-collapse>
      </n-form>
    </section>

    <!-- 快速配置提示 -->
    <section class="es-section" v-if="selectedPresetInfo?.setup_hint">
      <n-alert type="info" :title="`💡 ${selectedPresetInfo?.label} 配置提示`">
        <div v-html="selectedPresetInfo?.setup_hint"></div>
      </n-alert>
    </section>

    <!-- 多角色端点 -->
    <n-collapse>
      <n-collapse-item title="🔧 多角色端点（高级）" name="multi-role">
        <p class="es-hint">主力 / 经济 / 知识图谱可分别配置不同模型和密钥。</p>
        <n-switch v-model:value="isIndependent" size="medium">
          <template #checked>独立端点</template>
          <template #unchecked>统一端点</template>
        </n-switch>

        <template v-if="isIndependent">
          <n-tabs type="segment" v-model:value="activeRole" style="margin-top: 12px">
            <n-tab-pane name="cheap" tab="💰 经济模型">
              <n-form label-placement="left" label-width="80" class="es-form">
                <n-form-item label="API Key">
                  <n-input v-model:value="cheapData.api_key" type="password" show-password-on="click" placeholder="留空则跟随主力模型" />
                </n-form-item>
                <n-form-item label="Base URL">
                  <n-input v-model:value="cheapData.base_url" placeholder="留空则跟随主力模型" />
                </n-form-item>
                <n-form-item label="模型">
                  <n-input v-model:value="cheapData.model" placeholder="轻量/低成本模型 ID" />
                </n-form-item>
              </n-form>
            </n-tab-pane>
            <n-tab-pane name="kg" tab="🧠 知识图谱">
              <n-form label-placement="left" label-width="80" class="es-form">
                <n-form-item label="API Key">
                  <n-input v-model:value="kgData.api_key" type="password" show-password-on="click" placeholder="留空则跟随主力模型" />
                </n-form-item>
                <n-form-item label="Base URL">
                  <n-input v-model:value="kgData.base_url" placeholder="留空则跟随主力模型" />
                </n-form-item>
                <n-form-item label="模型">
                  <n-input v-model:value="kgData.model" placeholder="需较强指令遵循能力的模型" />
                </n-form-item>
              </n-form>
            </n-tab-pane>
          </n-tabs>
        </template>
      </n-collapse-item>
    </n-collapse>

    <p class="es-footer-note">
      🔒 密钥仅存于本地 SQLite 数据库，不会上传到任何服务器。
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { llmControlApi, type LLMControlPanelData, type LLMProfile, type LLMProtocol } from '@/api/llmControl'
import { DEFAULT_MAX_OUTPUT_TOKENS } from '@/constants/llm'

const message = useMessage()
const saving = ref(false)
const testing = ref(false)
const connectionStatus = ref<'idle' | 'testing' | 'ok' | 'error'>('idle')
const connectionMessage = ref('')
const selectedPreset = ref('')
const isIndependent = ref(false)
const activeRole = ref('cheap')

// ── 厂商预设 ──
const presets = [
  { key: 'deepseek', label: 'DeepSeek', icon: '🔮', protocol: 'openai', default_base_url: 'https://api.deepseek.com/v1', recommended: true, tags: ['domestic'], default_model: 'deepseek-chat', models: ['deepseek-chat', 'deepseek-reasoner', 'deepseek-coder'], setup_hint: '访问 <a href="https://platform.deepseek.com" target="_blank">platform.deepseek.com</a> 获取 API Key。推荐模型：deepseek-chat（通用）、deepseek-reasoner（推理）。' },
  { key: 'doubao-ark', label: '豆包 / Ark', icon: '🫘', protocol: 'openai', default_base_url: 'https://ark.cn-beijing.volces.com/api/v3', recommended: true, tags: ['domestic'], default_model: '', models: [], setup_hint: '访问 <a href="https://console.volcengine.com/ark" target="_blank">火山方舟控制台</a> 创建推理接入点，复制 Endpoint ID 作为模型名。' },
  { key: 'siliconflow', label: 'SiliconFlow', icon: '🌊', protocol: 'openai', default_base_url: 'https://api.siliconflow.cn/v1', tags: ['domestic', 'free'], default_model: 'deepseek-ai/DeepSeek-V3', models: ['deepseek-ai/DeepSeek-V3', 'Qwen/Qwen2.5-72B-Instruct', 'THUDM/glm-4-9b-chat'], setup_hint: '访问 <a href="https://cloud.siliconflow.cn" target="_blank">SiliconFlow</a> 注册即可获得免费额度，支持多种开源模型。' },
  { key: 'minimax', label: 'MiniMax', icon: '🤖', protocol: 'openai', default_base_url: 'https://api.minimax.chat/v1', tags: ['domestic'], default_model: 'MiniMax-Text-01', models: ['MiniMax-Text-01', 'abab7-chat'], setup_hint: '访问 <a href="https://platform.minimaxi.com" target="_blank">MiniMax 开放平台</a> 获取 API Key。' },
  { key: 'mimo', label: '小米 MiMo', icon: '📱', protocol: 'openai', default_base_url: 'https://api.xiaomimimo.com/v1', tags: ['domestic', 'free'], default_model: 'MiMo-7B-RL', models: ['MiMo-7B-RL', 'MiMo-7B-SFT'], setup_hint: '小米 MiMo 推理模型，支持两种使用方式：<br><br><b>① 按量付费</b>（API Key 格式 <code>sk-xxx</code>）<br>Base URL：<code>https://api.xiaomimimo.com/v1</code><br>前往 <a href="https://platform.xiaomimimo.com" target="_blank">API Keys</a> 创建 Key<br><br><b>② Token Plan</b>（固定订阅，API Key 格式 <code>tp-xxx</code>）<br>Base URL：<code>https://token-plan-cn.xiaomimimo.com/v1</code><br>订阅后前往 <a href="https://platform.xiaomimimo.com" target="_blank">Token Plan</a> 获取专属 Key<br><br>两种均支持 OpenAI 和 Anthropic 兼容协议，系统会根据你选的协议自动切换。<br>MiMo-7B-RL 擅长数学与代码推理。' },
  { key: 'moonshot', label: 'Moonshot', icon: '🌙', protocol: 'openai', default_base_url: 'https://api.moonshot.cn/v1', tags: ['domestic'], default_model: 'moonshot-v1-128k', models: ['moonshot-v1-8k', 'moonshot-v1-32k', 'moonshot-v1-128k'], setup_hint: '访问 <a href="https://platform.moonshot.cn" target="_blank">Moonshot 开放平台</a> 获取 API Key。推荐 moonshot-v1-128k（长上下文）。' },
  { key: 'qwen-dashscope', label: '通义千问', icon: '☁️', protocol: 'openai', default_base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', tags: ['domestic'], default_model: 'qwen-plus', models: ['qwen-turbo', 'qwen-plus', 'qwen-max', 'qwen-long'], setup_hint: '访问 <a href="https://dashscope.console.aliyun.com" target="_blank">阿里云百炼</a> 获取 API Key。推荐 qwen-plus（性价比高）。' },
  { key: 'glm-openai', label: '智谱 GLM', icon: '🧊', protocol: 'openai', default_base_url: 'https://open.bigmodel.cn/api/paas/v4', tags: ['domestic'], default_model: 'glm-4-flash', models: ['glm-4-flash', 'glm-4-plus', 'glm-4-long'], setup_hint: '访问 <a href="https://open.bigmodel.cn" target="_blank">智谱开放平台</a> 获取 API Key。glm-4-flash 免费使用。' },
  { key: 'qianfan', label: '百度千帆', icon: '🔵', protocol: 'openai', default_base_url: 'https://qianfan.baidubce.com/v2', tags: ['domestic'], default_model: 'ernie-4.0-8k', models: ['ernie-4.0-8k', 'ernie-3.5-8k', 'ernie-speed-128k'], setup_hint: '访问 <a href="https://console.bce.baidu.com/qianfan" target="_blank">百度千帆</a> 获取 API Key。' },
  { key: 'yi', label: '零一万物', icon: '✨', protocol: 'openai', default_base_url: 'https://api.lingyiwanwu.com/v1', tags: ['domestic'], default_model: 'yi-large', models: ['yi-large', 'yi-medium', 'yi-spark'], setup_hint: '访问 <a href="https://platform.lingyiwanwu.com" target="_blank">零一万物开放平台</a> 获取 API Key。' },
  { key: 'openai-official', label: 'OpenAI', icon: '🟢', protocol: 'openai', default_base_url: 'https://api.openai.com/v1', tags: [], default_model: 'gpt-4o', models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'o1-mini'], setup_hint: '需要海外网络。访问 <a href="https://platform.openai.com" target="_blank">platform.openai.com</a> 获取 API Key。' },
  { key: 'claude-official', label: 'Claude', icon: '🟠', protocol: 'anthropic', default_base_url: 'https://api.anthropic.com', tags: [], default_model: 'claude-sonnet-4-20250514', models: ['claude-opus-4-20250514', 'claude-sonnet-4-20250514', 'claude-haiku-4-20250414'], setup_hint: '需要海外网络。访问 <a href="https://console.anthropic.com" target="_blank">console.anthropic.com</a> 获取 API Key。' },
  { key: 'gemini-official', label: 'Gemini', icon: '💎', protocol: 'gemini', default_base_url: 'https://generativelanguage.googleapis.com/v1beta', tags: ['free'], default_model: 'gemini-2.0-flash', models: ['gemini-2.0-flash', 'gemini-2.5-pro', 'gemini-2.5-flash'], setup_hint: '访问 <a href="https://aistudio.google.com" target="_blank">Google AI Studio</a> 获取 API Key。免费额度充足。' },
  { key: 'custom', label: '自定义', icon: '🔧', protocol: 'openai', default_base_url: '', tags: [], default_model: '', models: [], setup_hint: '' },
]

const selectedPresetInfo = computed(() => presets.find(p => p.key === selectedPreset.value))

const modelSuggestions = computed(() => {
  const models = selectedPresetInfo.value?.models || []
  return models.map(m => ({ label: m, value: m }))
})

const protocolOptions = [
  { label: 'OpenAI 兼容', value: 'openai' },
  { label: 'Anthropic', value: 'anthropic' },
  { label: 'Gemini', value: 'gemini' },
]

// ── 表单数据 ──
const formData = reactive({
  api_key: '',
  base_url: '',
  model: '',
  temperature: 0.7,
  max_tokens: DEFAULT_MAX_OUTPUT_TOKENS,
  timeout_seconds: 300,
  protocol: 'openai' as string,
})

const cheapData = reactive({ api_key: '', base_url: '', model: '' })
const kgData = reactive({ api_key: '', base_url: '', model: '' })

function selectPreset(preset: typeof presets[0]) {
  selectedPreset.value = preset.key
  formData.base_url = preset.default_base_url
  formData.model = preset.default_model
  formData.protocol = preset.protocol
}

// MiMo 智能识别：根据 API Key 前缀自动切换 Base URL
watch(() => formData.api_key, (key) => {
  if (selectedPreset.value !== 'mimo') return
  const trimmed = (key || '').trim()
  if (trimmed.startsWith('tp-')) {
    // Token Plan 模式
    if (formData.protocol === 'anthropic') {
      formData.base_url = 'https://token-plan-cn.xiaomimimo.com/anthropic'
    } else {
      formData.base_url = 'https://token-plan-cn.xiaomimimo.com/v1'
    }
  } else if (trimmed.startsWith('sk-')) {
    // 按量付费模式
    if (formData.protocol === 'anthropic') {
      formData.base_url = 'https://api.xiaomimimo.com/anthropic'
    } else {
      formData.base_url = 'https://api.xiaomimimo.com/v1'
    }
  }
})

// MiMo 协议切换时同步 Base URL
watch(() => formData.protocol, (proto) => {
  if (selectedPreset.value !== 'mimo') return
  const isTp = (formData.api_key || '').trim().startsWith('tp-')
  if (proto === 'anthropic') {
    formData.base_url = isTp
      ? 'https://token-plan-cn.xiaomimimo.com/anthropic'
      : 'https://api.xiaomimimo.com/anthropic'
  } else {
    formData.base_url = isTp
      ? 'https://token-plan-cn.xiaomimimo.com/v1'
      : 'https://api.xiaomimimo.com/v1'
  }
})

// ── 加载配置 ──
async function loadData() {
  try {
    const data: LLMControlPanelData = await llmControlApi.getPanel()
    const profiles = data.config.profiles
    const activeId = data.config.active_profile_id
    const main = profiles.find(p => p.name === '主力模型') || profiles.find(p => p.id === activeId) || profiles[0]

    if (main) {
      // 匹配预设
      const matchedPreset = presets.find(p =>
        main.base_url?.includes(p.default_base_url?.replace('https://', '').split('/')[0] || '___')
      )
      selectedPreset.value = matchedPreset?.key || 'custom'
      formData.api_key = main.api_key || ''
      formData.base_url = main.base_url || ''
      formData.model = main.model || ''
      formData.temperature = main.temperature ?? 0.7
      formData.max_tokens = main.max_tokens ?? DEFAULT_MAX_OUTPUT_TOKENS
      formData.timeout_seconds = main.timeout_seconds ?? 300
      formData.protocol = main.protocol || 'openai'
    }

    isIndependent.value = (data.config.endpoint_mode ?? 'unified') === 'independent'

    const cheap = profiles.find(p => p.name.includes('经济'))
    if (cheap) {
      cheapData.api_key = cheap.api_key || ''
      cheapData.base_url = cheap.base_url || ''
      cheapData.model = cheap.model || ''
    }
    const kg = profiles.find(p => p.name.includes('知识') && p.name.includes('图谱'))
    if (kg) {
      kgData.api_key = kg.api_key || ''
      kgData.base_url = kg.base_url || ''
      kgData.model = kg.model || ''
    }
  } catch { /* 默认值 */ }
}

// ── 测试连接 ──
async function handleTest() {
  if (!formData.api_key && !formData.base_url) {
    message.warning('请先填写 API Key 和 Base URL')
    return
  }
  testing.value = true
  connectionStatus.value = 'testing'
  connectionMessage.value = '正在测试连接...'
  try {
    const result = await llmControlApi.testProfile({
      id: 'test',
      name: 'test',
      protocol: formData.protocol as LLMProtocol,
      api_key: formData.api_key,
      base_url: formData.base_url,
      model: formData.model,
      temperature: formData.temperature,
      max_tokens: formData.max_tokens,
      timeout_seconds: formData.timeout_seconds,
      extra_headers: {},
      extra_query: {},
      extra_body: {},
      notes: '',
      preset_key: selectedPreset.value || 'custom-openai-compatible',
      use_legacy_chat_completions: false,
    })
    if (result?.ok) {
      connectionStatus.value = 'ok'
      connectionMessage.value = `连接成功！模型 ${result.model || formData.model || '(默认)'} 可用。延迟 ${result.latency_ms || '?'}ms`
    } else {
      connectionStatus.value = 'error'
      connectionMessage.value = (result as any)?.error || '连接失败，请检查配置'
    }
  } catch (err: any) {
    connectionStatus.value = 'error'
    connectionMessage.value = err?.response?.data?.detail || err?.message || '测试失败'
  } finally {
    testing.value = false
  }
}

// ── 保存配置 ──
async function handleSave() {
  saving.value = true
  try {
    const data: LLMControlPanelData = await llmControlApi.getPanel()
    const profiles: LLMProfile[] = [...data.config.profiles]
    const mainExisting = profiles.find(p => p.name === '主力模型') || profiles.find(p => p.id === data.config.active_profile_id) || profiles[0]

    const mainProfile: LLMProfile = {
      id: mainExisting?.id || 'main-default',
      name: '主力模型',
      protocol: formData.protocol as LLMProtocol,
      base_url: formData.base_url,
      api_key: formData.api_key,
      model: formData.model,
      temperature: formData.temperature,
      max_tokens: formData.max_tokens,
      timeout_seconds: formData.timeout_seconds,
      extra_headers: mainExisting?.extra_headers ?? {},
      extra_query: mainExisting?.extra_query ?? {},
      extra_body: mainExisting?.extra_body ?? {},
      notes: mainExisting?.notes ?? '',
      preset_key: selectedPreset.value || 'custom-openai-compatible',
      use_legacy_chat_completions: mainExisting?.use_legacy_chat_completions ?? false,
    }

    const idx = profiles.findIndex(p => p.id === mainProfile.id)
    if (idx >= 0) profiles[idx] = mainProfile
    else profiles.unshift(mainProfile)

    const newConfig = {
      ...data.config,
      endpoint_mode: (isIndependent.value ? 'independent' : 'unified') as 'unified' | 'independent',
      active_profile_id: mainProfile.id,
      profiles,
    }

    await llmControlApi.saveConfig(newConfig)
    message.success('✅ 配置已保存')
    connectionStatus.value = 'idle'
  } catch {
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => { void loadData() })
</script>

<style scoped>
.engine-settings {
  max-width: 800px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.es-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.es-header-info h4 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--app-text-primary, #1f2937);
}

.es-header-info p {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--app-text-muted, #6b7280);
}

.es-section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--app-text-primary, #1f2937);
  margin-bottom: 12px;
}

/* ── 厂商预设卡片网格 ── */
.preset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 10px;
}

.preset-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 14px 8px;
  border: 2px solid var(--app-border, #e5e7eb);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--app-surface, #fff);
  text-align: center;
  position: relative;
}

.preset-card:hover {
  border-color: var(--color-brand, #4f46e5);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.preset-card.active {
  border-color: var(--color-brand, #4f46e5);
  background: var(--color-brand-light, #eef2ff);
  box-shadow: 0 0 0 1px var(--color-brand, #4f46e5), 0 4px 12px rgba(79, 70, 229, 0.15);
}

.preset-icon {
  font-size: 28px;
  line-height: 1;
}

.preset-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--app-text-primary, #1f2937);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.preset-tags {
  display: flex;
  gap: 3px;
  flex-wrap: wrap;
  justify-content: center;
}

.preset-badge {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 999px;
  font-weight: 600;
}

.preset-badge.recommend {
  background: #fef3c7;
  color: #92400e;
}

.preset-badge.domestic {
  background: #dbeafe;
  color: #1e40af;
}

.preset-badge.free {
  background: #d1fae5;
  color: #065f46;
}

/* ── 表单 ── */
.es-form {
  padding: 8px 0;
}

.param-value {
  font-size: 12px;
  color: var(--app-text-muted, #6b7280);
  margin-left: 8px;
  min-width: 30px;
}

.es-hint {
  font-size: 12px;
  color: var(--app-text-muted, #6b7280);
  margin-bottom: 12px;
}

.es-footer-note {
  font-size: 11px;
  color: var(--app-text-muted, #9ca3af);
  text-align: center;
  padding: 8px 0;
}

@media (max-width: 640px) {
  .preset-grid {
    grid-template-columns: repeat(3, 1fr);
  }
  .es-header {
    flex-direction: column;
  }
}
</style>
