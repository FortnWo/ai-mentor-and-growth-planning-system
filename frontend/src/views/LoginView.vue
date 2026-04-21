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
  <div class="view">
    <div class="card">
      <h1>Sign In</h1>
      <p class="hint">Students use 10-digit student IDs. Admins use assigned usernames.</p>

      <form class="form" @submit.prevent="submit">
        <label>
          Username
          <input v-model="form.username" autocomplete="username" />
        </label>

        <label>
          Password
          <input v-model="form.password" type="password" autocomplete="current-password" />
        </label>

        <button :disabled="submitting" type="submit">Login</button>
      </form>

      <p v-if="error" class="error">{{ error }}</p>
    </div>
  </div>
</template>

<style scoped>
.view {
  max-width: 460px;
  margin: 5rem auto;
  padding: 1rem;
}

.card {
  border: 1px solid #ddd;
  border-radius: 10px;
  padding: 1.25rem;
  background: #fff;
}

h1 {
  margin: 0 0 0.6rem;
}

.hint {
  margin: 0 0 1rem;
  color: #64748b;
}

.form {
  display: grid;
  gap: 0.8rem;
}

label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

input,
button {
  font: inherit;
}

input {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 0.55rem 0.7rem;
}

button {
  border: none;
  border-radius: 8px;
  padding: 0.6rem 0.9rem;
  background: #1d4ed8;
  color: #fff;
  cursor: pointer;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error {
  margin-top: 0.85rem;
  color: #b91c1c;
}
</style>
