<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  confirmPasswordReset,
  getAvailableMethods,
  sendResetCode,
  verifyResetCode,
} from '../api/passwordReset'
import { getApiErrorMessage } from '../utils/apiError'

type Step = 'method' | 'send-code' | 'verify' | 'new-password' | 'done'
type ResetMethod = 'admin' | 'phone' | 'email'

const router = useRouter()

const step = ref<Step>('method')
const loading = ref(false)
const errorMsg = ref('')
const successMsg = ref('')

const availableMethods = ref<string[]>(['admin'])
const selectedMethod = ref<ResetMethod>('admin')
const username = ref('')
const code = ref('')
const resetToken = ref('')
const resendCountdown = ref(0)
let resendTimer: ReturnType<typeof setInterval> | null = null

const newPasswordForm = reactive({ password: '', confirm: '' })

// ── Load available methods ──────────────────────────────────────────────────

onMounted(async () => {
  try {
    const res = await getAvailableMethods()
    availableMethods.value = res.methods
  } catch {
    availableMethods.value = ['admin']
  }
})

// ── Helpers ─────────────────────────────────────────────────────────────────

function clearMessages() {
  errorMsg.value = ''
  successMsg.value = ''
}

function startResendCountdown(seconds = 60) {
  resendCountdown.value = seconds
  if (resendTimer) clearInterval(resendTimer)
  resendTimer = setInterval(() => {
    resendCountdown.value -= 1
    if (resendCountdown.value <= 0 && resendTimer) {
      clearInterval(resendTimer)
      resendTimer = null
    }
  }, 1000)
}

function selectMethod(method: ResetMethod) {
  selectedMethod.value = method
  clearMessages()

  if (method === 'admin') {
    step.value = 'method'
    return
  }
  step.value = 'send-code'
}

// ── Step: send code ─────────────────────────────────────────────────────────

async function handleSendCode() {
  clearMessages()
  if (!username.value.trim()) {
    errorMsg.value = '请输入用户名（学号）。'
    return
  }
  loading.value = true
  try {
    await sendResetCode({ username: username.value.trim(), method: selectedMethod.value as 'phone' | 'email' })
    step.value = 'verify'
    startResendCountdown(60)
    successMsg.value = `验证码已发送至你的${selectedMethod.value === 'phone' ? '手机' : '邮箱'}。`
  } catch (err) {
    errorMsg.value = getApiErrorMessage(err, '发送失败，请检查账号信息或稍后重试。')
  } finally {
    loading.value = false
  }
}

async function handleResend() {
  if (resendCountdown.value > 0) return
  clearMessages()
  loading.value = true
  try {
    await sendResetCode({ username: username.value.trim(), method: selectedMethod.value as 'phone' | 'email' })
    startResendCountdown(60)
    successMsg.value = '验证码已重新发送。'
  } catch (err) {
    errorMsg.value = getApiErrorMessage(err, '重新发送失败，请稍后重试。')
  } finally {
    loading.value = false
  }
}

// ── Step: verify code ───────────────────────────────────────────────────────

async function handleVerify() {
  clearMessages()
  if (!code.value.trim()) {
    errorMsg.value = '请输入验证码。'
    return
  }
  loading.value = true
  try {
    const res = await verifyResetCode({
      username: username.value.trim(),
      method: selectedMethod.value,
      code: code.value.trim(),
    })
    resetToken.value = res.reset_token
    step.value = 'new-password'
    successMsg.value = '验证成功，请设置新密码。'
  } catch (err) {
    errorMsg.value = getApiErrorMessage(err, '验证码不正确或已过期，请重新获取。')
  } finally {
    loading.value = false
  }
}

// ── Step: set new password ───────────────────────────────────────────────────

async function handleConfirm() {
  clearMessages()
  if (!newPasswordForm.password || !newPasswordForm.confirm) {
    errorMsg.value = '请填写新密码和确认密码。'
    return
  }
  if (newPasswordForm.password !== newPasswordForm.confirm) {
    errorMsg.value = '两次输入的密码不一致。'
    return
  }
  if (newPasswordForm.password.length < 8) {
    errorMsg.value = '密码不能少于 8 位。'
    return
  }
  loading.value = true
  try {
    await confirmPasswordReset({
      reset_token: resetToken.value,
      new_password: newPasswordForm.password,
    })
    step.value = 'done'
    successMsg.value = '密码重置成功！即将跳转到登录页面……'
    setTimeout(() => router.push('/login'), 2000)
  } catch (err) {
    errorMsg.value = getApiErrorMessage(err, '密码重置失败，请重新尝试完整流程。')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page forgot-page">
    <div class="forgot-card glass-card panel">

      <!-- ── Header ── -->
      <div class="forgot-header">
        <p class="page-kicker">账号安全</p>
        <h1 class="forgot-title">找回密码</h1>
      </div>

      <!-- ── Feedback ── -->
      <p v-if="errorMsg" class="feedback feedback--error">{{ errorMsg }}</p>
      <p v-if="successMsg" class="feedback feedback--success">{{ successMsg }}</p>

      <!-- ── Step: choose method ── -->
      <div v-if="step === 'method'" class="step">
        <p class="step-hint">请选择密码找回方式：</p>

        <div class="method-list">
          <button
            v-if="availableMethods.includes('phone')"
            class="method-btn button button--ghost"
            type="button"
            @click="selectMethod('phone')"
          >
            <span class="method-icon">📱</span>
            <span>
              <strong>手机验证码找回</strong>
              <small>向注册手机号发送验证码</small>
            </span>
          </button>

          <button
            v-if="availableMethods.includes('email')"
            class="method-btn button button--ghost"
            type="button"
            @click="selectMethod('email')"
          >
            <span class="method-icon">📧</span>
            <span>
              <strong>邮箱验证码找回</strong>
              <small>向注册邮箱发送验证码</small>
            </span>
          </button>

          <div class="method-btn method-btn--admin">
            <span class="method-icon">🛡️</span>
            <span>
              <strong>联系管理员重置</strong>
              <small>携带学生证到教务处或联系系统管理员</small>
            </span>
          </div>
        </div>

        <div class="step-actions">
          <router-link class="button button--ghost" to="/login">返回登录</router-link>
        </div>
      </div>

      <!-- ── Step: enter username and send code ── -->
      <div v-else-if="step === 'send-code'" class="step">
        <p class="step-hint">
          通过 <strong>{{ selectedMethod === 'phone' ? '手机验证码' : '邮箱验证码' }}</strong> 找回密码
        </p>

        <label class="field">
          <span class="label">用户名（学号）</span>
          <input
            v-model="username"
            class="input"
            placeholder="请输入 10 位学号"
            maxlength="20"
            @keydown.enter="handleSendCode"
          />
        </label>

        <div class="step-actions">
          <button class="button button--primary" :disabled="loading" type="button" @click="handleSendCode">
            {{ loading ? '发送中…' : '发送验证码' }}
          </button>
          <button class="button button--ghost" type="button" @click="step = 'method'">返回</button>
        </div>
      </div>

      <!-- ── Step: enter verification code ── -->
      <div v-else-if="step === 'verify'" class="step">
        <p class="step-hint">
          验证码已发送，请输入收到的 {{ availableMethods.includes('phone') ? '手机' : '邮箱' }} 验证码：
        </p>

        <label class="field">
          <span class="label">验证码</span>
          <input
            v-model="code"
            class="input input--code"
            placeholder="6 位验证码"
            maxlength="16"
            inputmode="numeric"
            @keydown.enter="handleVerify"
          />
        </label>

        <div class="step-actions">
          <button class="button button--primary" :disabled="loading" type="button" @click="handleVerify">
            {{ loading ? '验证中…' : '确认验证码' }}
          </button>
          <button
            class="button button--ghost"
            type="button"
            :disabled="resendCountdown > 0 || loading"
            @click="handleResend"
          >
            {{ resendCountdown > 0 ? `重新发送（${resendCountdown}s）` : '重新发送' }}
          </button>
          <button class="button button--ghost" type="button" @click="step = 'send-code'">返回</button>
        </div>
      </div>

      <!-- ── Step: set new password ── -->
      <div v-else-if="step === 'new-password'" class="step">
        <p class="step-hint">验证通过，请设置新密码（不少于 8 位）：</p>

        <label class="field">
          <span class="label">新密码</span>
          <input v-model="newPasswordForm.password" class="input" type="password" autocomplete="new-password" />
        </label>

        <label class="field">
          <span class="label">确认新密码</span>
          <input
            v-model="newPasswordForm.confirm"
            class="input"
            type="password"
            autocomplete="new-password"
            @keydown.enter="handleConfirm"
          />
        </label>

        <div class="step-actions">
          <button class="button button--primary" :disabled="loading" type="button" @click="handleConfirm">
            {{ loading ? '提交中…' : '确认重置' }}
          </button>
        </div>
      </div>

      <!-- ── Step: done ── -->
      <div v-else-if="step === 'done'" class="step step--done">
        <div class="done-icon">✅</div>
        <p class="done-text">密码重置成功，正在跳转到登录页面……</p>
        <router-link class="button button--primary" to="/login">立即登录</router-link>
      </div>

    </div>
  </div>
</template>

<style scoped>
.forgot-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 80vh;
}

.forgot-card {
  width: min(480px, 100%);
  display: grid;
  gap: 1.5rem;
}

.forgot-header {
  display: grid;
  gap: 0.3rem;
}

.forgot-title {
  margin: 0;
  font-family: var(--font-display);
  color: var(--heading);
  font-size: clamp(1.5rem, 3vw, 2rem);
}

.step {
  display: grid;
  gap: 1rem;
}

.step-hint {
  margin: 0;
  color: var(--text-muted);
}

.method-list {
  display: grid;
  gap: 0.75rem;
}

.method-btn {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem 1.2rem;
  text-align: left;
  border-radius: var(--radius-lg, 16px);
  cursor: pointer;
}

.method-btn span:last-child {
  display: grid;
  gap: 0.15rem;
}

.method-btn small {
  color: var(--text-muted);
  font-size: 0.82rem;
}

.method-btn--admin {
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-muted);
}

.method-icon {
  font-size: 1.4rem;
  flex-shrink: 0;
}

.input--code {
  letter-spacing: 0.25em;
  font-size: 1.2rem;
}

.step-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.step--done {
  text-align: center;
  align-items: center;
}

.done-icon {
  font-size: 3rem;
}

.done-text {
  margin: 0;
  color: var(--text-muted);
}
</style>
