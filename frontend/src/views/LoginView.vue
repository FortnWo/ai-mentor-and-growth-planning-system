<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { login } from '../stores/auth'
import { getApiErrorMessage } from '../utils/apiError'

const router = useRouter()
const route = useRoute()

const form = reactive({
  username: '',
  password: '',
})

const error = ref('')
const submitting = ref(false)
const redirectTarget = computed(() => {
  const redirect = route.query.redirect
  return typeof redirect === 'string' && redirect ? redirect : '/home'
})

async function submit() {
  error.value = ''

  if (!form.username.trim() || !form.password.trim()) {
    error.value = '请输入用户名和密码。'
    return
  }

  try {
    submitting.value = true
    await login({
      username: form.username.trim(),
      password: form.password,
    })

    await router.push(redirectTarget.value)
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError, '登录失败，请检查用户名和密码。')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="page auth-page">
    <div class="auth-panel reveal">
      <div class="title-row">
        <div>
          <p class="eyebrow">登录</p>
          <h2 class="section-title">欢迎回来</h2>
        </div>

        <span class="chip chip--neutral">受保护</span>
      </div>

      <form class="auth-form" @submit.prevent="submit">
        <label class="field">
          <span class="label">用户名</span>
          <input v-model="form.username" class="input" autocomplete="username" />
        </label>

        <label class="field">
          <span class="label">密码</span>
          <input v-model="form.password" class="input" type="password" autocomplete="current-password" />
        </label>

        <button class="button button--primary" :disabled="submitting" type="submit">登录</button>
      </form>

      <p v-if="error" class="feedback feedback--error">{{ error }}</p>

      <div class="auth-footer">
        <RouterLink class="forgot-link" to="/forgot-password">忘记密码？</RouterLink>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: calc(100vh - var(--app-header-height, 4rem) - 3rem);
  width: 100%;
}

.auth-panel {
  width: min(420px, 100%);
}

.auth-form {
  display: grid;
  gap: 1rem;
}

.section-title {
  margin: 0;
  font-family: var(--font-display);
  color: var(--heading);
  font-size: clamp(1.3rem, 2vw, 1.6rem);
}

.auth-footer {
  margin-top: 0.75rem;
  text-align: center;
}

.forgot-link {
  color: var(--text-muted);
  font-size: 0.88rem;
  text-decoration: none;
  transition: color 0.2s ease;
}

.forgot-link:hover {
  color: var(--primary);
}
</style>
