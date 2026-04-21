<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { changeMyPassword, getMyProfile, updateMyProfile } from '../api/profile'
import type { UserRead } from '../api/user'
import { authState, refreshCurrentUser } from '../stores/auth'

type ProfileFormState = {
  full_name: string
  major: string
  year_of_study: string
  bio: string
}

type PasswordFormState = {
  current_password: string
  new_password: string
}

const profile = ref<UserRead | null>(null)
const feedback = ref<string>('')
const error = ref<string>('')
const submitting = ref<boolean>(false)

const profileForm = reactive<ProfileFormState>({
  full_name: '',
  major: '',
  year_of_study: '',
  bio: '',
})

const passwordForm = reactive<PasswordFormState>({
  current_password: '',
  new_password: '',
})

function clearMessages() {
  feedback.value = ''
  error.value = ''
}

function syncFormFromProfile(user: UserRead) {
  profileForm.full_name = user.full_name ?? ''
  profileForm.major = user.major ?? ''
  profileForm.year_of_study = user.year_of_study ? String(user.year_of_study) : ''
  profileForm.bio = user.bio ?? ''
}

function toNullableNumber(value: string): number | undefined {
  if (!value.trim()) {
    return undefined
  }

  const parsed = Number(value)
  return Number.isInteger(parsed) ? parsed : undefined
}

async function loadMyProfile() {
  clearMessages()

  try {
    submitting.value = true
    const data = await getMyProfile()
    profile.value = data
    syncFormFromProfile(data)
  } catch {
    error.value = 'Could not load your profile.'
  } finally {
    submitting.value = false
  }
}

async function saveProfile() {
  clearMessages()

  try {
    submitting.value = true
    const updated = await updateMyProfile({
      full_name: profileForm.full_name.trim() || undefined,
      major: profileForm.major.trim() || undefined,
      year_of_study: toNullableNumber(profileForm.year_of_study),
      bio: profileForm.bio.trim() || undefined,
    })

    profile.value = updated
    syncFormFromProfile(updated)
    feedback.value = 'Profile updated successfully.'
  } catch {
    error.value = 'Profile update failed.'
  } finally {
    submitting.value = false
  }
}

async function updatePassword() {
  clearMessages()

  if (!passwordForm.current_password.trim() || !passwordForm.new_password.trim()) {
    error.value = 'Please enter both current and new password.'
    return
  }

  try {
    submitting.value = true
    const updated = await changeMyPassword({
      current_password: passwordForm.current_password,
      new_password: passwordForm.new_password,
    })

    profile.value = updated
    passwordForm.current_password = ''
    passwordForm.new_password = ''
    feedback.value = 'Password changed successfully.'
  } catch {
    error.value = 'Password change failed. Check your current password and password policy.'
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  if (!authState.user) {
    await refreshCurrentUser()
  }
  await loadMyProfile()
})
</script>

<template>
  <div class="view">
    <h1>My Profile</h1>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="feedback" class="success">{{ feedback }}</p>

    <div v-if="profile" class="card basic">
      <p><strong>Username:</strong> {{ profile.username }}</p>
      <p><strong>Email:</strong> {{ profile.email }}</p>
      <p><strong>Role:</strong> {{ profile.role }}</p>
      <p><strong>Status:</strong> {{ profile.is_active ? 'Active' : 'Disabled' }}</p>
      <p v-if="profile.last_login_at"><strong>Last Login:</strong> {{ new Date(profile.last_login_at).toLocaleString() }}</p>
    </div>

    <form class="card form" @submit.prevent="saveProfile">
      <h2>Profile Details</h2>

      <label>
        Full Name
        <input v-model="profileForm.full_name" />
      </label>

      <label>
        Major
        <input v-model="profileForm.major" />
      </label>

      <label>
        Year Of Study
        <input v-model="profileForm.year_of_study" type="number" min="1" max="12" />
      </label>

      <label class="span-2">
        Bio
        <textarea v-model="profileForm.bio" rows="4" />
      </label>

      <div class="actions span-2">
        <button :disabled="submitting" type="submit">Save Profile</button>
      </div>
    </form>

    <form class="card form" @submit.prevent="updatePassword">
      <h2>Change Password</h2>

      <label>
        Current Password
        <input v-model="passwordForm.current_password" type="password" />
      </label>

      <label>
        New Password
        <input v-model="passwordForm.new_password" type="password" />
      </label>

      <div class="actions span-2">
        <button :disabled="submitting" type="submit">Update Password</button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.view {
  max-width: 820px;
  margin: 2rem auto;
  padding: 1rem;
  text-align: left;
}

.card {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1rem;
  background: #fff;
}

.basic p {
  margin: 0.3rem 0;
}

.form {
  display: grid;
  grid-template-columns: repeat(2, minmax(220px, 1fr));
  gap: 0.75rem;
}

h2 {
  grid-column: 1 / -1;
  margin: 0;
}

label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.9rem;
}

input,
textarea,
button {
  font: inherit;
}

input,
textarea {
  border: 1px solid #ccc;
  border-radius: 6px;
  padding: 0.5rem 0.65rem;
}

.actions {
  display: flex;
  gap: 0.5rem;
}

button {
  border: none;
  border-radius: 6px;
  padding: 0.55rem 0.95rem;
  background: #1a56db;
  color: #fff;
  cursor: pointer;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.success {
  color: #166534;
}

.error {
  color: #b91c1c;
}

.span-2 {
  grid-column: 1 / -1;
}

@media (max-width: 900px) {
  .form {
    grid-template-columns: 1fr;
  }
}
</style>
