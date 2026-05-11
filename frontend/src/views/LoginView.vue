<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { login } from '../stores/auth'

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
  return typeof redirect === 'string' && redirect ? redirect : '/chat'
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
  } catch {
    error.value = '登录失败，请检查用户名和密码。'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="page auth-page">
    <section class="auth-shell glass-card hero-frame reveal">
      <div class="auth-copy">
        <p class="page-kicker">安全访问</p>
        <h1 class="page-title">登录你的导师工作台。</h1>
        <p class="page-subtitle">
          学生使用 10 位学号登录，管理员使用分配的用户名。界面为快速回到工作台而设计。
        </p>

        <div class="grid-3 auth-highlights">
          <article class="stat-card">
            <p class="stat-label">快速进入</p>
            <p class="stat-value">一键</p>
            <p class="stat-note">快速返回你的工作台</p>
          </article>

          <article class="stat-card">
            <p class="stat-label">身份模型</p>
            <p class="stat-value">角色区分</p>
            <p class="stat-note">学生与管理员流程分离</p>
          </article>

          <article class="stat-card">
            <p class="stat-label">安全会话</p>
            <p class="stat-value">JWT</p>
            <p class="stat-note">基于令牌的身份认证</p>
          </article>
        </div>
      </div>

      <div class="auth-panel">
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
      </div>
    </section>
  </div>
</template>

<style scoped>
.auth-page {
  width: min(1120px, 100%);
  margin: 0 auto;
}

.auth-shell {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(360px, 420px);
  gap: 1rem;
  padding: 1.2rem;
}

.auth-copy,
.auth-form {
  display: grid;
  gap: 1rem;
}

.auth-panel {
  align-self: center;
}

.section-title {
  margin: 0;
  font-family: var(--font-display);
  color: var(--heading);
  font-size: clamp(1.3rem, 2vw, 1.6rem);
}

@media (max-width: 1024px) {
  .auth-shell {
    grid-template-columns: 1fr;
  }
}
</style>
