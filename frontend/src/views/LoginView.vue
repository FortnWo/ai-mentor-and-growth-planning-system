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
    error.value = 'Please enter username and password.'
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
    error.value = 'Login failed. Please check your username and password.'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="page auth-page">
    <section class="auth-shell glass-card">
      <div class="auth-copy">
        <p class="page-kicker">Secure access</p>
        <h1 class="page-title">Sign in to your mentor workspace.</h1>
        <p class="page-subtitle">
          Students use 10-digit IDs. Admins use assigned usernames. The interface is tuned for fast re-entry.
        </p>

        <div class="grid-3 auth-highlights">
          <article class="stat-card">
            <p class="stat-label">Fast access</p>
            <p class="stat-value">1 click</p>
            <p class="stat-note">Back into your workspace quickly</p>
          </article>

          <article class="stat-card">
            <p class="stat-label">Identity model</p>
            <p class="stat-value">Role aware</p>
            <p class="stat-note">Student and admin flows stay separate</p>
          </article>

          <article class="stat-card">
            <p class="stat-label">Secure session</p>
            <p class="stat-value">JWT</p>
            <p class="stat-note">Token-based authentication</p>
          </article>
        </div>
      </div>

      <div class="auth-panel">
        <div class="title-row">
          <div>
            <p class="eyebrow">Login</p>
            <h2 class="section-title">Welcome back</h2>
          </div>

          <span class="chip chip--neutral">Protected</span>
        </div>

        <form class="auth-form" @submit.prevent="submit">
          <label class="field">
            <span class="label">Username</span>
            <input v-model="form.username" class="input" autocomplete="username" />
          </label>

          <label class="field">
            <span class="label">Password</span>
            <input v-model="form.password" class="input" type="password" autocomplete="current-password" />
          </label>

          <button class="button button--primary" :disabled="submitting" type="submit">Login</button>
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
