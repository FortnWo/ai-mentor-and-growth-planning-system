<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'

import {
  getAiConfig,
  getAiUsageLogs,
  type UsageDetailEntry,
  type UsageLogPeriod,
  type UsageStatEntry,
} from '../api/adminSystem'
import apiClient from '../api/client'
import AiConfigStatusCard from '../components/admin/AiConfigStatusCard.vue'
import LlmPresetPanel from '../components/admin/LlmPresetPanel.vue'
import UsageStatsPanel from '../components/admin/UsageStatsPanel.vue'
import { getApiErrorMessage } from '../utils/apiError'

// ── Types ─────────────────────────────────────────────────────────────────────

type ActiveTab = 'ai' | 'notify' | 'rateLimit' | 'logs'

// ── State ─────────────────────────────────────────────────────────────────────

const activeTab = ref<ActiveTab>('ai')
const loading = ref(false)
const feedback = ref('')
const errorMsg = ref('')

// AI Config
const aiConfig = reactive({
  llm_api_key: '',
  llm_api_base_url: '',
  llm_model: '',
  llm_system_prompt: '',
  admin_llm_system_prompt: '',
  llm_api_key_set: false,
  llm_api_key_masked: null as string | null,
  active_preset_id: null as string | null,
})

// Notify Config
const smsConfig = reactive({
  vendor: 'aliyun',
  access_key_id: '',
  access_key_secret: '',
  endpoint: '',
  sign_name: '',
  template_code: '',
  sdk_app_id: '',
  region: '',
})

const smtpConfig = reactive({
  smtp_host: '',
  smtp_port: 465,
  from_email: '',
  email_password: '',
  sender_name: '',
})

const vcConfig = reactive({
  expire_minutes: 10,
  resend_interval_seconds: 60,
  code_length: 6,
})

// Rate limit
const rateLimitConfig = reactive({
  daily_limit: 100,
  weekly_limit: 500,
})

// Logs
const logPeriod = ref<UsageLogPeriod>('week')
const usernameFilter = ref('')
const usageStats = ref<UsageStatEntry[]>([])
const userDetail = ref<UsageDetailEntry[] | null>(null)
const errorLogs = ref<string[]>([])
const errorLogTotal = ref(0)
const errorLogPage = ref(1)
const errorLogPageSize = ref(50)
const errorLogDate = ref('')
const logsLoading = ref(false)
const showSmsForm = ref(false)
const showSmtpForm = ref(false)

// ── Messages ─────────────────────────────────────────────────────────────────

function clearMessages() {
  feedback.value = ''
  errorMsg.value = ''
}

// ── Load functions ────────────────────────────────────────────────────────────

async function loadAiConfig() {
  try {
    const d = await getAiConfig()
    aiConfig.llm_api_key_set = d.llm_api_key_set
    aiConfig.llm_api_key_masked = d.llm_api_key_masked
    aiConfig.active_preset_id = d.active_preset_id
    aiConfig.llm_api_base_url = d.llm_api_base_url ?? ''
    aiConfig.llm_model = d.llm_model ?? ''
    aiConfig.llm_system_prompt = d.llm_system_prompt ?? ''
    aiConfig.admin_llm_system_prompt = d.admin_llm_system_prompt ?? ''
    aiConfig.llm_api_key = '' // never pre-fill key
  } catch (err) {
    errorMsg.value = getApiErrorMessage(err, '无法加载 AI 配置')
  }
}

function onPresetPanelError(message: string) {
  errorMsg.value = message
}

async function onPresetActivated() {
  clearMessages()
  await loadAiConfig()
  feedback.value = '已切换 LLM 预设。'
}

async function onPresetSaved() {
  clearMessages()
  await loadAiConfig()
  feedback.value = 'LLM 预设已保存。'
}

async function onPresetDeleted() {
  clearMessages()
  await loadAiConfig()
  feedback.value = 'LLM 预设已删除。'
}

async function loadNotifyConfig() {
  try {
    const res = await apiClient.get('/admin/system/notify-config')
    const d = res.data
    if (d.sms_vendor) smsConfig.vendor = d.sms_vendor
    if (d.sms_endpoint) smsConfig.endpoint = d.sms_endpoint
    if (d.sms_sign_name) smsConfig.sign_name = d.sms_sign_name
    if (d.smtp_host) smtpConfig.smtp_host = d.smtp_host
    if (d.smtp_port) smtpConfig.smtp_port = parseInt(d.smtp_port) || 465
    if (d.smtp_from_email) smtpConfig.from_email = d.smtp_from_email
    if (d.smtp_sender_name) smtpConfig.sender_name = d.smtp_sender_name
  } catch (err) {
    errorMsg.value = getApiErrorMessage(err, '无法加载通知服务配置')
  }
}

async function loadRateLimitConfig() {
  try {
    const res = await apiClient.get('/admin/system/rate-limit-config')
    rateLimitConfig.daily_limit = res.data.daily_limit
    rateLimitConfig.weekly_limit = res.data.weekly_limit
  } catch (err) {
    errorMsg.value = getApiErrorMessage(err, '无法加载速率配置')
  }
}

async function loadVcConfig() {
  try {
    const res = await apiClient.get('/admin/system/verification-config')
    vcConfig.expire_minutes = res.data.expire_minutes
    vcConfig.resend_interval_seconds = res.data.resend_interval_seconds
    vcConfig.code_length = res.data.code_length
  } catch (err) {
    // ignore — non-critical
  }
}

async function loadUsage() {
  logsLoading.value = true
  try {
    const username = usernameFilter.value.trim() || undefined
    const data = await getAiUsageLogs(logPeriod.value, username)
    usageStats.value = data.stats
    userDetail.value = data.user_detail ?? null
  } catch (err) {
    errorMsg.value = getApiErrorMessage(err, '无法加载使用量统计')
  } finally {
    logsLoading.value = false
  }
}

function onErrorLogDateChange() {
  errorLogPage.value = 1
  void loadErrorLogs()
}

function clearErrorLogDate() {
  errorLogDate.value = ''
  errorLogPage.value = 1
  void loadErrorLogs()
}

async function loadErrorLogs() {
  logsLoading.value = true
  try {
    const params: Record<string, string | number> = {
      page: errorLogPage.value,
      page_size: errorLogPageSize.value,
    }
    if (errorLogDate.value) {
      params.date = errorLogDate.value
    }
    const res = await apiClient.get('/admin/system/logs/error', { params })
    errorLogs.value = res.data.lines
    errorLogTotal.value = res.data.total_lines
  } catch (err) {
    errorMsg.value = getApiErrorMessage(err, '无法加载错误日志')
  } finally {
    logsLoading.value = false
  }
}

// ── Save functions ────────────────────────────────────────────────────────────

async function saveAiConfig() {
  clearMessages()
  loading.value = true
  try {
    const payload: Record<string, string> = {}
    if (aiConfig.llm_api_key) payload.llm_api_key = aiConfig.llm_api_key
    if (aiConfig.llm_api_base_url) payload.llm_api_base_url = aiConfig.llm_api_base_url
    if (aiConfig.llm_model) payload.llm_model = aiConfig.llm_model
    if (aiConfig.llm_system_prompt) payload.llm_system_prompt = aiConfig.llm_system_prompt
    if (aiConfig.admin_llm_system_prompt) payload.admin_llm_system_prompt = aiConfig.admin_llm_system_prompt
    await apiClient.put('/admin/system/ai-config', payload)
    feedback.value = 'AI 配置已保存。'
    aiConfig.llm_api_key = ''
    await loadAiConfig()
  } catch (err) {
    errorMsg.value = getApiErrorMessage(err, '保存失败')
  } finally {
    loading.value = false
  }
}

async function saveSmsConfig() {
  clearMessages()
  loading.value = true
  try {
    await apiClient.put('/admin/system/notify-config/sms', { ...smsConfig })
    smsConfig.access_key_secret = ''
    feedback.value = '短信配置已保存。'
  } catch (err) {
    errorMsg.value = getApiErrorMessage(err, '保存失败')
  } finally {
    loading.value = false
  }
}

async function saveSmtpConfig() {
  clearMessages()
  loading.value = true
  try {
    await apiClient.put('/admin/system/notify-config/smtp', { ...smtpConfig })
    smtpConfig.email_password = ''
    feedback.value = 'SMTP 配置已保存。'
  } catch (err) {
    errorMsg.value = getApiErrorMessage(err, '保存失败')
  } finally {
    loading.value = false
  }
}

async function saveRateLimitConfig() {
  clearMessages()
  loading.value = true
  try {
    await apiClient.put('/admin/system/rate-limit-config', { ...rateLimitConfig })
    feedback.value = '速率配置已保存。'
  } catch (err) {
    errorMsg.value = getApiErrorMessage(err, '保存失败')
  } finally {
    loading.value = false
  }
}

async function saveVcConfig() {
  clearMessages()
  loading.value = true
  try {
    await apiClient.put('/admin/system/verification-config', { ...vcConfig })
    feedback.value = '验证码配置已保存。'
  } catch (err) {
    errorMsg.value = getApiErrorMessage(err, '保存失败')
  } finally {
    loading.value = false
  }
}

// ── Init ─────────────────────────────────────────────────────────────────────

async function switchTab(tab: ActiveTab) {
  activeTab.value = tab
  clearMessages()
  if (tab === 'ai') await loadAiConfig()
  if (tab === 'notify') { await loadNotifyConfig(); await loadVcConfig() }
  if (tab === 'rateLimit') await loadRateLimitConfig()
  if (tab === 'logs') { await loadUsage(); await loadErrorLogs() }
}

watch(logPeriod, () => {
  if (activeTab.value === 'logs') {
    void loadUsage()
  }
})

onMounted(async () => {
  await loadAiConfig()
})
</script>

<template>
  <div class="page page--wide admin-system-page">
    <div class="page-header reveal">
      <p class="page-kicker">管理员工作区</p>
      <h1 class="page-title">系统维护</h1>
      <p class="page-subtitle">配置 AI 参数、密码找回通知服务、速率限制，查看日志与用量统计。</p>
    </div>

    <p v-if="errorMsg" class="feedback feedback--error">{{ errorMsg }}</p>
    <p v-if="feedback" class="feedback feedback--success">{{ feedback }}</p>

    <!-- ── Tab bar ── -->
    <div class="tab-bar reveal reveal--delay-1">
      <button class="tab-btn" :class="{ 'tab-btn--active': activeTab === 'ai' }" @click="switchTab('ai')">AI 助手配置</button>
      <button class="tab-btn" :class="{ 'tab-btn--active': activeTab === 'notify' }" @click="switchTab('notify')">密码找回服务</button>
      <button class="tab-btn" :class="{ 'tab-btn--active': activeTab === 'rateLimit' }" @click="switchTab('rateLimit')">调用速率</button>
      <button class="tab-btn" :class="{ 'tab-btn--active': activeTab === 'logs' }" @click="switchTab('logs')">日志与流量</button>
    </div>

    <!-- ════════════ AI CONFIG ════════════ -->
    <div v-if="activeTab === 'ai'" class="tab-content reveal reveal--delay-2 ai-config-layout">
      <div class="panel config-form ai-config-layout__main">
        <div class="title-row">
          <div>
            <p class="eyebrow">AI 服务</p>
            <h2 class="section-title">AI 助手配置</h2>
          </div>
          <span v-if="aiConfig.llm_api_key_set" class="chip chip--active">API Key 已设置</span>
          <span v-else class="chip chip--warn">API Key 未设置</span>
        </div>

        <form class="form-grid" @submit.prevent="saveAiConfig">
          <label class="field span-2">
            <span class="label">LLM API Key（留空保持不变）</span>
            <input v-model="aiConfig.llm_api_key" class="input" type="password" autocomplete="new-password" placeholder="sk-..." />
          </label>

          <label class="field">
            <span class="label">LLM API Base URL</span>
            <input v-model="aiConfig.llm_api_base_url" class="input" placeholder="https://api.openai.com/v1" />
          </label>

          <label class="field">
            <span class="label">LLM Model</span>
            <input v-model="aiConfig.llm_model" class="input" placeholder="gpt-4o" />
          </label>

          <label class="field span-2">
            <span class="label">普通用户系统提示词</span>
            <textarea v-model="aiConfig.llm_system_prompt" class="textarea" rows="3" placeholder="你是一个专业、友好、简洁的AI成长规划助手"></textarea>
          </label>

          <label class="field span-2">
            <span class="label">管理员系统提示词</span>
            <textarea v-model="aiConfig.admin_llm_system_prompt" class="textarea" rows="3" placeholder="你是一个专业全能的系统管理助手"></textarea>
          </label>

          <div class="actions span-2">
            <button class="button button--primary" :disabled="loading" type="submit">保存 AI 配置</button>
          </div>
        </form>
      </div>

      <aside class="ai-config-layout__aside">
        <AiConfigStatusCard
          :model="aiConfig.llm_model || null"
          :base-url="aiConfig.llm_api_base_url || null"
          :key-masked="aiConfig.llm_api_key_masked"
          :key-set="aiConfig.llm_api_key_set"
        />
        <LlmPresetPanel
          :active-preset-id="aiConfig.active_preset_id"
          :form-api-key="aiConfig.llm_api_key"
          :form-base-url="aiConfig.llm_api_base_url"
          :form-model="aiConfig.llm_model"
          :busy="loading"
          @activated="onPresetActivated"
          @saved="onPresetSaved"
          @deleted="onPresetDeleted"
          @error="onPresetPanelError"
        />
      </aside>
    </div>

    <!-- ════════════ NOTIFY CONFIG ════════════ -->
    <div v-else-if="activeTab === 'notify'" class="tab-content reveal reveal--delay-2">

      <!-- SMS -->
      <div class="panel config-form">
        <div class="title-row">
          <div>
            <p class="eyebrow">短信服务</p>
            <h2 class="section-title">SMS 密码找回</h2>
          </div>
          <button class="button button--ghost" type="button" @click="showSmsForm = !showSmsForm">
            {{ showSmsForm ? '收起' : '展开配置' }}
          </button>
        </div>

        <transition name="fade-slide">
          <form v-if="showSmsForm" class="form-grid" @submit.prevent="saveSmsConfig">
            <label class="field">
              <span class="label">短信服务商</span>
              <select v-model="smsConfig.vendor" class="input">
                <option value="aliyun">阿里云 (Aliyun)</option>
                <option value="tencent">腾讯云 (Tencent)</option>
                <option value="custom">自定义</option>
              </select>
            </label>

            <label class="field">
              <span class="label">AccessKey ID</span>
              <input v-model="smsConfig.access_key_id" class="input" placeholder="云平台密钥 ID" />
            </label>

            <label class="field span-2">
              <span class="label">AccessKey Secret（密文存储）</span>
              <input v-model="smsConfig.access_key_secret" class="input" type="password" placeholder="留空保持不变" autocomplete="new-password" />
            </label>

            <label class="field">
              <span class="label">Endpoint（接口域名）</span>
              <input v-model="smsConfig.endpoint" class="input" placeholder="dysmsapi.aliyuncs.com" />
            </label>

            <label class="field">
              <span class="label">短信签名名称</span>
              <input v-model="smsConfig.sign_name" class="input" placeholder="如：USTH系统" />
            </label>

            <label class="field">
              <span class="label">模板 Code</span>
              <input v-model="smsConfig.template_code" class="input" placeholder="SMS_12345678" />
            </label>

            <label v-if="smsConfig.vendor === 'tencent'" class="field">
              <span class="label">SDK AppId（腾讯云）</span>
              <input v-model="smsConfig.sdk_app_id" class="input" />
            </label>

            <div class="actions span-2">
              <button class="button button--primary" :disabled="loading" type="submit">保存短信配置</button>
            </div>
          </form>
        </transition>
      </div>

      <!-- SMTP -->
      <div class="panel config-form">
        <div class="title-row">
          <div>
            <p class="eyebrow">邮件服务</p>
            <h2 class="section-title">SMTP 密码找回</h2>
          </div>
          <button class="button button--ghost" type="button" @click="showSmtpForm = !showSmtpForm">
            {{ showSmtpForm ? '收起' : '展开配置' }}
          </button>
        </div>

        <transition name="fade-slide">
          <form v-if="showSmtpForm" class="form-grid" @submit.prevent="saveSmtpConfig">
            <label class="field">
              <span class="label">SMTP 服务器地址</span>
              <input v-model="smtpConfig.smtp_host" class="input" placeholder="smtp.163.com" />
            </label>

            <label class="field">
              <span class="label">SMTP 端口</span>
              <input v-model.number="smtpConfig.smtp_port" class="input" type="number" placeholder="465（SSL）或 25" />
            </label>

            <label class="field">
              <span class="label">发件邮箱账号</span>
              <input v-model="smtpConfig.from_email" class="input" type="email" placeholder="system@example.com" />
            </label>

            <label class="field">
              <span class="label">发件人昵称</span>
              <input v-model="smtpConfig.sender_name" class="input" placeholder="AI Mentor 系统" />
            </label>

            <label class="field span-2">
              <span class="label">邮件密码 / 授权码（密文存储）</span>
              <input v-model="smtpConfig.email_password" class="input" type="password" placeholder="留空保持不变" autocomplete="new-password" />
            </label>

            <div class="actions span-2">
              <button class="button button--primary" :disabled="loading" type="submit">保存 SMTP 配置</button>
            </div>
          </form>
        </transition>
      </div>

      <!-- Verification code config -->
      <div class="panel config-form">
        <div class="title-row">
          <div>
            <p class="eyebrow">验证码参数</p>
            <h2 class="section-title">验证码配置</h2>
          </div>
        </div>

        <form class="form-grid" @submit.prevent="saveVcConfig">
          <label class="field">
            <span class="label">验证码有效时长（分钟）</span>
            <input v-model.number="vcConfig.expire_minutes" class="input" type="number" min="1" max="60" />
          </label>

          <label class="field">
            <span class="label">两次获取最小间隔（秒）</span>
            <input v-model.number="vcConfig.resend_interval_seconds" class="input" type="number" min="10" max="600" />
          </label>

          <label class="field">
            <span class="label">验证码位数</span>
            <input v-model.number="vcConfig.code_length" class="input" type="number" min="4" max="12" />
          </label>

          <div class="actions span-2">
            <button class="button button--primary" :disabled="loading" type="submit">保存验证码配置</button>
          </div>
        </form>
      </div>
    </div>

    <!-- ════════════ RATE LIMIT ════════════ -->
    <div v-else-if="activeTab === 'rateLimit'" class="tab-content reveal reveal--delay-2">
      <div class="panel config-form">
        <div class="title-row">
          <div>
            <p class="eyebrow">调用控制</p>
            <h2 class="section-title">AI 调用速率限制</h2>
          </div>
        </div>
        <p class="hint-text">超过阈值的账户将被限速，并在日志中标记为风险账户。正常使用的学生不会触及限制。</p>

        <form class="form-grid" @submit.prevent="saveRateLimitConfig">
          <label class="field">
            <span class="label">每日调用上限（次）</span>
            <input v-model.number="rateLimitConfig.daily_limit" class="input" type="number" min="1" />
          </label>

          <label class="field">
            <span class="label">每周调用上限（次）</span>
            <input v-model.number="rateLimitConfig.weekly_limit" class="input" type="number" min="1" />
          </label>

          <div class="actions span-2">
            <button class="button button--primary" :disabled="loading" type="submit">保存速率配置</button>
          </div>
        </form>
      </div>
    </div>

    <!-- ════════════ LOGS ════════════ -->
    <div v-else-if="activeTab === 'logs'" class="tab-content reveal reveal--delay-2">

      <!-- Usage stats -->
      <div class="panel">
        <div class="title-row">
          <div>
            <p class="eyebrow">AI 使用量</p>
            <h2 class="section-title">流量统计</h2>
          </div>
        </div>

        <UsageStatsPanel
          v-model:period="logPeriod"
          :loading="logsLoading"
          :stats="usageStats"
          :user-detail="userDetail"
          @refresh="loadUsage"
        >
          <template #filters>
            <input
              v-model="usernameFilter"
              class="input input--sm"
              placeholder="按学号过滤"
              @keydown.enter="loadUsage"
            />
          </template>
        </UsageStatsPanel>
      </div>

      <!-- Error logs -->
      <div class="panel">
        <div class="title-row">
          <div>
            <p class="eyebrow">系统日志</p>
            <h2 class="section-title">错误日志</h2>
          </div>
          <div class="log-controls">
            <label class="log-date-filter">
              <span class="log-date-filter__label">日期</span>
              <input
                v-model="errorLogDate"
                type="date"
                class="input input--sm log-date-filter__input"
                :disabled="logsLoading"
                @change="onErrorLogDateChange"
              />
            </label>
            <button
              v-if="errorLogDate"
              class="button button--ghost"
              :disabled="logsLoading"
              type="button"
              @click="clearErrorLogDate"
            >
              全部
            </button>
            <button class="button button--ghost" :disabled="logsLoading" type="button" @click="loadErrorLogs">刷新</button>
          </div>
        </div>

        <p v-if="errorLogTotal > 0" class="hint-text">
          <template v-if="errorLogDate">{{ errorLogDate }}：</template>
          共 {{ errorLogTotal }} 行，显示最新 {{ errorLogPageSize }} 行
        </p>
        <div v-if="errorLogs.length > 0" class="log-output">
          <pre v-for="(line, i) in errorLogs" :key="i" class="log-line" :class="{ 'log-line--error': line.includes('ERROR'), 'log-line--warn': line.includes('WARNING') }">{{ line }}</pre>
        </div>
        <p v-else class="hint-text">
          <template v-if="errorLogDate">{{ errorLogDate }} 暂无错误日志。</template>
          <template v-else>暂无错误日志，或日志文件尚未创建。</template>
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-system-page {
  width: min(1180px, 100%);
  margin: 0 auto;
  display: grid;
  gap: 1rem;
}

.page-header {
  margin-bottom: 0.5rem;
}

.section-title {
  margin: 0;
  font-family: var(--font-display);
  color: var(--heading);
  font-size: clamp(1.2rem, 2vw, 1.5rem);
}

.hint-text {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin: 0;
}

/* Tabs */
.tab-bar {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.tab-btn {
  padding: 0.55rem 1.1rem;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-btn:hover,
.tab-btn--active {
  border-color: rgba(var(--accent-1-rgb), 0.35);
  background: rgba(var(--accent-1-rgb), 0.08);
  color: var(--nav-active-text);
}

.tab-content {
  display: grid;
  gap: 1rem;
}

/* AI config two-column layout */
.ai-config-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 340px);
  gap: 1rem;
  align-items: start;
  max-width: 1200px;
}

.ai-config-layout__aside {
  display: grid;
  gap: 1rem;
}

/* Config form */
.config-form {
  display: grid;
  gap: 1rem;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.span-2 {
  grid-column: 1 / -1;
}

.actions {
  display: flex;
  gap: 0.75rem;
}

/* Logs */
.log-controls {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
}

.log-date-filter {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.log-date-filter__label {
  font-size: 0.85rem;
  color: var(--text-muted);
  white-space: nowrap;
}

.log-date-filter__input {
  min-width: 10.5rem;
}

.input--sm {
  padding: 0.35rem 0.55rem;
  font-size: 0.85rem;
}

.log-output {
  max-height: 480px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-md, 8px);
  padding: 0.75rem;
  background: var(--surface);
}

.log-line {
  margin: 0;
  padding: 0.15rem 0;
  font-family: var(--font-mono, monospace);
  font-size: 0.78rem;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--text-muted);
  border-bottom: 1px solid transparent;
}

.log-line--error {
  color: #ef4444;
}

.log-line--warn {
  color: #f59e0b;
}

/* Transition */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

@media (max-width: 900px) {
  .ai-config-layout {
    grid-template-columns: 1fr;
    max-width: 860px;
  }
}

@media (max-width: 768px) {
  .form-grid {
    grid-template-columns: 1fr;
  }

  .span-2 {
    grid-column: 1;
  }
}
</style>
