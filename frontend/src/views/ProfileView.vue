<script setup lang="ts">
import { reactive, ref } from 'vue'
import { createUser, deleteUser, getUser, updateUser } from '../api/user'
import type { UserCreatePayload, UserRead, UserUpdatePayload } from '../api/user'

type ProfileFormState = {
  username: string
  email: string
  full_name: string
  major: string
  year_of_study: string
  bio: string
}

const profile = ref<UserRead | null>(null)
const profileLookupId = ref<string>('1')
const feedback = ref<string>('')
const error = ref<string>('')
const submitting = ref<boolean>(false)

const form = reactive<ProfileFormState>({
  username: '',
  email: '',
  full_name: '',
  major: '',
  year_of_study: '',
  bio: '',
})

function clearMessages() {
  feedback.value = ''
  error.value = ''
}

function syncFormFromProfile(user: UserRead) {
  form.username = user.username
  form.email = user.email
  form.full_name = user.full_name ?? ''
  form.major = user.major ?? ''
  form.year_of_study = user.year_of_study ? String(user.year_of_study) : ''
  form.bio = user.bio ?? ''
}

function toNullableNumber(value: string): number | undefined {
  if (!value.trim()) {
    return undefined
  }

  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : undefined
}

function buildCreatePayload(): UserCreatePayload {
  return {
    username: form.username.trim(),
    email: form.email.trim(),
    full_name: form.full_name.trim() || undefined,
    major: form.major.trim() || undefined,
    year_of_study: toNullableNumber(form.year_of_study),
    bio: form.bio.trim() || undefined,
  }
}

function buildUpdatePayload(): UserUpdatePayload {
  return {
    username: form.username.trim() || undefined,
    email: form.email.trim() || undefined,
    full_name: form.full_name.trim() || undefined,
    major: form.major.trim() || undefined,
    year_of_study: toNullableNumber(form.year_of_study),
    bio: form.bio.trim() || undefined,
  }
}

async function loadUser() {
  clearMessages()

  const id = Number(profileLookupId.value)
  if (!Number.isInteger(id) || id <= 0) {
    error.value = 'Please enter a valid numeric user ID.'
    return
  }

  try {
    submitting.value = true
    const user = await getUser(id)
    profile.value = user
    syncFormFromProfile(user)
    feedback.value = `Loaded profile #${user.id}.`
  } catch {
    profile.value = null
    error.value = 'User not found for that ID.'
  } finally {
    submitting.value = false
  }
}

async function saveProfile() {
  clearMessages()

  if (!form.username.trim() || !form.email.trim()) {
    error.value = 'Username and email are required.'
    return
  }

  try {
    submitting.value = true
    if (profile.value) {
      const updated = await updateUser(profile.value.id, buildUpdatePayload())
      profile.value = updated
      syncFormFromProfile(updated)
      feedback.value = `Profile #${updated.id} updated.`
    } else {
      const created = await createUser(buildCreatePayload())
      profile.value = created
      profileLookupId.value = String(created.id)
      syncFormFromProfile(created)
      feedback.value = `Profile #${created.id} created.`
    }
  } catch {
    error.value = 'Save failed. Check whether username/email are unique and valid.'
  } finally {
    submitting.value = false
  }
}

async function removeProfile() {
  if (!profile.value) {
    error.value = 'No loaded profile to delete.'
    return
  }

  clearMessages()

  try {
    submitting.value = true
    await deleteUser(profile.value.id)
    feedback.value = `Profile #${profile.value.id} deleted.`
    profile.value = null
  } catch {
    error.value = 'Delete failed.'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="view">
    <h1>Profile</h1>

    <div class="toolbar card">
      <label>
        Load User ID
        <input v-model="profileLookupId" type="number" min="1" placeholder="e.g. 1" />
      </label>
      <button :disabled="submitting" @click="loadUser">Load</button>
    </div>

    <form class="card form" @submit.prevent="saveProfile">
      <label>
        Username *
        <input v-model="form.username" required />
      </label>

      <label>
        Email *
        <input v-model="form.email" required type="email" />
      </label>

      <label>
        Full Name
        <input v-model="form.full_name" />
      </label>

      <label>
        Major
        <input v-model="form.major" />
      </label>

      <label>
        Year Of Study
        <input v-model="form.year_of_study" type="number" min="1" max="12" />
      </label>

      <label>
        Bio
        <textarea v-model="form.bio" rows="4" />
      </label>

      <div class="actions">
        <button :disabled="submitting" type="submit">
          {{ profile ? 'Update Profile' : 'Create Profile' }}
        </button>
        <button :disabled="submitting || !profile" class="danger" type="button" @click="removeProfile">
          Delete
        </button>
      </div>
    </form>

    <p v-if="feedback" class="success">{{ feedback }}</p>
    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="profile" class="card details">
      <p><strong>ID:</strong> {{ profile.id }}</p>
      <p><strong>Username:</strong> {{ profile.username }}</p>
      <p><strong>Email:</strong> {{ profile.email }}</p>
      <p v-if="profile.full_name"><strong>Name:</strong> {{ profile.full_name }}</p>
      <p v-if="profile.major"><strong>Major:</strong> {{ profile.major }}</p>
      <p v-if="profile.year_of_study"><strong>Year:</strong> {{ profile.year_of_study }}</p>
      <p v-if="profile.bio"><strong>Bio:</strong> {{ profile.bio }}</p>
      <p><strong>Created:</strong> {{ new Date(profile.created_at).toLocaleString() }}</p>
      <p><strong>Updated:</strong> {{ new Date(profile.updated_at).toLocaleString() }}</p>
    </div>
  </div>
</template>

<style scoped>
.view {
  max-width: 760px;
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

.toolbar {
  display: flex;
  gap: 0.75rem;
  align-items: end;
}

.form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.75rem;
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
  align-items: end;
  gap: 0.5rem;
  grid-column: 1 / -1;
}

button {
  border: none;
  border-radius: 6px;
  padding: 0.55rem 0.95rem;
  background: #1a56db;
  color: #fff;
  cursor: pointer;
}

.danger {
  background: #b91c1c;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.details p {
  margin: 0.3rem 0;
}

.success {
  color: #166534;
}

.error {
  color: #b91c1c;
}
</style>
