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
  <div class="page page--wide profile-page">
    <section class="page-header glass-card panel">
      <div class="title-row">
        <div>
          <p class="page-kicker">Personal workspace</p>
          <h1 class="page-title">My Profile</h1>
          <p class="page-subtitle">
            Keep your academic details, bio, and credentials organized in a polished profile workspace.
          </p>
        </div>
      </div>

      <div v-if="profile" class="stat-grid">
        <article class="stat-card">
          <p class="stat-label">Username</p>
          <p class="stat-value">{{ profile.username }}</p>
          <p class="stat-note">Primary login identifier</p>
        </article>

        <article class="stat-card">
          <p class="stat-label">Role</p>
          <p class="stat-value">{{ profile.role }}</p>
          <p class="stat-note">{{ profile.is_active ? 'Active account' : 'Disabled account' }}</p>
        </article>

        <article class="stat-card">
          <p class="stat-label">Email</p>
          <p class="stat-value">{{ profile.email }}</p>
          <p class="stat-note">Notification channel</p>
        </article>

        <article class="stat-card">
          <p class="stat-label">Last login</p>
          <p class="stat-value">{{ profile.last_login_at ? 'Recent' : 'Never' }}</p>
          <p class="stat-note">
            {{ profile.last_login_at ? new Date(profile.last_login_at).toLocaleString() : 'No login record yet' }}
          </p>
        </article>
      </div>
    </section>

    <p v-if="error" class="feedback feedback--error">{{ error }}</p>
    <p v-if="feedback" class="feedback feedback--success">{{ feedback }}</p>

    <div class="grid-2 profile-grid">
      <section v-if="profile" class="panel profile-summary">
        <div class="title-row">
          <div>
            <p class="eyebrow">Account summary</p>
            <h2 class="section-title">Identity snapshot</h2>
          </div>

          <span class="chip" :class="profile.is_active ? 'chip--active' : 'chip--warn'">
            {{ profile.is_active ? 'Active' : 'Disabled' }}
          </span>
        </div>

        <div class="summary-list">
          <p><strong>Username</strong><span>{{ profile.username }}</span></p>
          <p><strong>Email</strong><span>{{ profile.email }}</span></p>
          <p><strong>Role</strong><span>{{ profile.role }}</span></p>
          <p v-if="profile.last_login_at">
            <strong>Last Login</strong><span>{{ new Date(profile.last_login_at).toLocaleString() }}</span>
          </p>
        </div>
      </section>

      <form class="panel form-card" @submit.prevent="saveProfile">
        <div class="title-row">
          <div>
            <p class="eyebrow">Profile details</p>
            <h2 class="section-title">Edit your public profile</h2>
          </div>
        </div>

        <label class="field">
          <span class="label">Full Name</span>
          <input v-model="profileForm.full_name" class="input" />
        </label>

        <label class="field">
          <span class="label">Major</span>
          <input v-model="profileForm.major" class="input" />
        </label>

        <label class="field">
          <span class="label">Year Of Study</span>
          <input v-model="profileForm.year_of_study" class="input" type="number" min="1" max="12" />
        </label>

        <label class="field span-2">
          <span class="label">Bio</span>
          <textarea v-model="profileForm.bio" class="textarea" rows="4"></textarea>
        </label>

        <div class="actions span-2">
          <button class="button button--primary" :disabled="submitting" type="submit">Save Profile</button>
        </div>
      </form>

      <form class="panel form-card" @submit.prevent="updatePassword">
        <div class="title-row">
          <div>
            <p class="eyebrow">Security</p>
            <h2 class="section-title">Change password</h2>
          </div>
        </div>

        <label class="field">
          <span class="label">Current Password</span>
          <input v-model="passwordForm.current_password" class="input" type="password" />
        </label>

        <label class="field">
          <span class="label">New Password</span>
          <input v-model="passwordForm.new_password" class="input" type="password" />
        </label>

        <div class="actions span-2">
          <button class="button button--ghost" :disabled="submitting" type="submit">Update Password</button>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
.profile-page {
  width: min(1180px, 100%);
  margin: 0 auto;
}

.profile-summary,
.form-card {
  display: grid;
  gap: 1rem;
}

.summary-list {
  display: grid;
  gap: 0.8rem;
}

.summary-list p {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 1rem;
  margin: 0;
  padding: 0.85rem 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.summary-list strong {
  color: #d8e7f7;
}

.summary-list span {
  text-align: right;
  color: #f8fbff;
}

.form-card {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-content: start;
}

.section-title {
  margin: 0;
  font-family: var(--font-display);
  color: var(--heading);
  font-size: clamp(1.2rem, 2vw, 1.55rem);
}

.actions {
  display: flex;
  gap: 0.75rem;
}

.span-2 {
  grid-column: 1 / -1;
}

@media (max-width: 1024px) {
  .form-card {
    grid-template-columns: 1fr;
  }
}
</style>
