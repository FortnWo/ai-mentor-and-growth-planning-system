<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getProfile } from '../api'
import type { UserRead } from '../api'

const profile = ref<UserRead | null>(null)
const error = ref<string>('')

onMounted(async () => {
  try {
    // Stub: load profile for user ID 1 until auth is implemented
    profile.value = await getProfile(1)
  } catch {
    error.value = 'Profile not found. Create one via the API first.'
  }
})
</script>

<template>
  <div class="view">
    <h1>My Profile</h1>

    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="profile" class="card">
      <p><strong>Username:</strong> {{ profile.username }}</p>
      <p><strong>Email:</strong> {{ profile.email }}</p>
      <p v-if="profile.full_name"><strong>Name:</strong> {{ profile.full_name }}</p>
      <p v-if="profile.major"><strong>Major:</strong> {{ profile.major }}</p>
      <p v-if="profile.year_of_study"><strong>Year:</strong> {{ profile.year_of_study }}</p>
      <p v-if="profile.bio"><strong>Bio:</strong> {{ profile.bio }}</p>
    </div>

    <p v-else-if="!error" class="loading">Loading…</p>
  </div>
</template>

<style scoped>
.view { max-width: 600px; margin: 2rem auto; padding: 1rem; }
.card { border: 1px solid #ddd; border-radius: 6px; padding: 1rem; }
.card p { margin: 0.4rem 0; }
.error { color: #b91c1c; }
.loading { color: #666; }
</style>
