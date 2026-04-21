<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import {
  createUser,
  deleteUser,
  grantAdminAccess,
  listUsers,
  revokeAdminAccess,
  updateUser,
} from '../api/user'
import type {
  AdminPermissionLevel,
  UserCreatePayload,
  UserRead,
  UserRole,
} from '../api/user'
import { authState, refreshCurrentUser } from '../stores/auth'

type CreateFormState = {
  username: string
  email: string
  password: string
  role: UserRole
  full_name: string
  major: string
  year_of_study: string
  bio: string
  is_active: boolean
  admin_permission_level: AdminPermissionLevel
  admin_permissions: string
  admin_expires_at: string
}

type GrantFormState = {
  target_user_id: string
  permission_level: AdminPermissionLevel
  permissions: string
  expires_at: string
}

const users = ref<UserRead[]>([])
const loading = ref(false)
const creating = ref(false)
const actionLoadingId = ref<number | null>(null)
const feedback = ref('')
const error = ref('')

const createForm = reactive<CreateFormState>({
  username: '',
  email: '',
  password: '',
  role: 'user',
  full_name: '',
  major: '',
  year_of_study: '',
  bio: '',
  is_active: true,
  admin_permission_level: 'limited',
  admin_permissions: 'user.read,user.update',
  admin_expires_at: '',
})

const grantForm = reactive<GrantFormState>({
  target_user_id: '',
  permission_level: 'limited',
  permissions: 'user.read',
  expires_at: '',
})

const isAdminCreate = computed(() => createForm.role === 'admin')
const userStats = computed(() => ({
  total: users.value.length,
  active: users.value.filter((user) => user.is_active).length,
  admins: users.value.filter((user) => user.role === 'admin').length,
  students: users.value.filter((user) => user.role !== 'admin').length,
}))

function clearMessages() {
  feedback.value = ''
  error.value = ''
}

function toNullableNumber(value: string): number | undefined {
  if (!value.trim()) {
    return undefined
  }

  const parsed = Number(value)
  return Number.isInteger(parsed) ? parsed : undefined
}

function parsePermissions(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function toIsoString(value: string): string | undefined {
  if (!value.trim()) {
    return undefined
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return undefined
  }

  return date.toISOString()
}

async function refreshUsers() {
  clearMessages()

  try {
    loading.value = true
    users.value = await listUsers(0, 200)
  } catch {
    error.value = 'Could not load users.'
  } finally {
    loading.value = false
  }
}

function buildCreatePayload(): UserCreatePayload {
  const payload: UserCreatePayload = {
    username: createForm.username.trim(),
    email: createForm.email.trim(),
    password: createForm.password,
    role: createForm.role,
    is_active: createForm.is_active,
    full_name: createForm.full_name.trim() || undefined,
    major: createForm.major.trim() || undefined,
    year_of_study: toNullableNumber(createForm.year_of_study),
    bio: createForm.bio.trim() || undefined,
  }

  if (createForm.role === 'admin') {
    payload.admin_permission_level = createForm.admin_permission_level
    payload.admin_permissions = parsePermissions(createForm.admin_permissions)
    payload.admin_expires_at = toIsoString(createForm.admin_expires_at)
  }

  return payload
}

function resetCreateForm() {
  createForm.username = ''
  createForm.email = ''
  createForm.password = ''
  createForm.role = 'user'
  createForm.full_name = ''
  createForm.major = ''
  createForm.year_of_study = ''
  createForm.bio = ''
  createForm.is_active = true
  createForm.admin_permission_level = 'limited'
  createForm.admin_permissions = 'user.read,user.update'
  createForm.admin_expires_at = ''
}

async function submitCreateUser() {
  clearMessages()

  if (!createForm.username.trim() || !createForm.email.trim() || !createForm.password.trim()) {
    error.value = 'Username, email and password are required.'
    return
  }

  if (createForm.role === 'user' && !/^\d{10}$/.test(createForm.username.trim())) {
    error.value = 'Student username must be a 10-digit student ID.'
    return
  }

  try {
    creating.value = true
    const created = await createUser(buildCreatePayload())
    feedback.value = `Created user #${created.id} (${created.username}).`
    resetCreateForm()
    await refreshUsers()
  } catch {
    error.value = 'Create user failed. Check uniqueness and role rules.'
  } finally {
    creating.value = false
  }
}

async function toggleActive(user: UserRead) {
  clearMessages()

  try {
    actionLoadingId.value = user.id
    const updated = await updateUser(user.id, { is_active: !user.is_active })
    feedback.value = `Updated status for #${updated.id}.`
    await refreshUsers()
  } catch {
    error.value = 'Failed to update user status.'
  } finally {
    actionLoadingId.value = null
  }
}

async function quickGrantAdmin(user: UserRead) {
  clearMessages()

  try {
    actionLoadingId.value = user.id
    const expiresAt = new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString()
    const updated = await grantAdminAccess(user.id, {
      permission_level: 'limited',
      permissions: ['user.read', 'user.update'],
      expires_at: expiresAt,
    })
    feedback.value = `Granted temporary admin access to #${updated.id}.`
    await refreshUsers()
  } catch {
    error.value = 'Failed to grant admin access.'
  } finally {
    actionLoadingId.value = null
  }
}

async function applyGrantForm() {
  clearMessages()

  const targetId = Number(grantForm.target_user_id)
  if (!Number.isInteger(targetId) || targetId <= 0) {
    error.value = 'Please enter a valid target user ID.'
    return
  }

  const permissions = parsePermissions(grantForm.permissions)
  if (grantForm.permission_level === 'limited' && !permissions.length) {
    error.value = 'Limited permissions require at least one permission key.'
    return
  }

  try {
    actionLoadingId.value = targetId
    const updated = await grantAdminAccess(targetId, {
      permission_level: grantForm.permission_level,
      permissions,
      expires_at: toIsoString(grantForm.expires_at),
    })
    feedback.value = `Updated admin privileges for #${updated.id}.`
    await refreshUsers()
  } catch {
    error.value = 'Failed to apply admin privilege update.'
  } finally {
    actionLoadingId.value = null
  }
}

async function revokeAdmin(user: UserRead) {
  clearMessages()

  try {
    actionLoadingId.value = user.id
    const updated = await revokeAdminAccess(user.id)
    feedback.value = `Revoked admin access for #${updated.id}.`
    await refreshUsers()
  } catch {
    error.value = 'Failed to revoke admin access.'
  } finally {
    actionLoadingId.value = null
  }
}

async function removeUser(user: UserRead) {
  if (user.id === authState.user?.id) {
    error.value = 'You cannot delete your own account here.'
    return
  }

  const confirmed = window.confirm(`Delete user #${user.id} (${user.username})?`)
  if (!confirmed) {
    return
  }

  clearMessages()
  try {
    actionLoadingId.value = user.id
    await deleteUser(user.id)
    feedback.value = `Deleted user #${user.id}.`
    await refreshUsers()
  } catch {
    error.value = 'Failed to delete user.'
  } finally {
    actionLoadingId.value = null
  }
}

onMounted(async () => {
  if (!authState.user) {
    await refreshCurrentUser()
  }
  await refreshUsers()
})
</script>

<template>
  <div class="page page--wide admin-page">
    <section class="page-header glass-card panel">
      <div class="title-row">
        <div>
          <p class="page-kicker">Admin console</p>
          <h1 class="page-title">Manage users with a high-density control surface.</h1>
          <p class="page-subtitle">
            Create accounts, grant privileges, and audit the roster from one calm interface.
          </p>
        </div>

        <div class="hero-actions">
          <button class="button button--ghost" :disabled="loading" type="button" @click="refreshUsers">
            Refresh Users
          </button>
        </div>
      </div>

      <div class="stat-grid">
        <article class="stat-card">
          <p class="stat-label">Total users</p>
          <p class="stat-value">{{ userStats.total }}</p>
          <p class="stat-note">Accounts currently in the system</p>
        </article>

        <article class="stat-card">
          <p class="stat-label">Active</p>
          <p class="stat-value">{{ userStats.active }}</p>
          <p class="stat-note">Enabled logins</p>
        </article>

        <article class="stat-card">
          <p class="stat-label">Admins</p>
          <p class="stat-value">{{ userStats.admins }}</p>
          <p class="stat-note">Privileged accounts</p>
        </article>

        <article class="stat-card">
          <p class="stat-label">Students</p>
          <p class="stat-value">{{ userStats.students }}</p>
          <p class="stat-note">Ordinary user accounts</p>
        </article>
      </div>
    </section>

    <p v-if="feedback" class="feedback feedback--success">{{ feedback }}</p>
    <p v-if="error" class="feedback feedback--error">{{ error }}</p>

    <div class="grid-2 admin-grid">
      <section class="panel form-panel">
        <div class="title-row">
          <div>
            <p class="eyebrow">Create account</p>
            <h2 class="section-title">New user</h2>
          </div>

          <span class="chip" :class="isAdminCreate ? 'chip--warn' : 'chip--active'">
            {{ isAdminCreate ? 'admin flow' : 'student flow' }}
          </span>
        </div>

        <form class="form-grid" @submit.prevent="submitCreateUser">
          <label class="field">
            <span class="label">Role</span>
            <select v-model="createForm.role" class="select">
              <option value="user">Student</option>
              <option value="admin">Admin</option>
            </select>
          </label>

          <label class="field">
            <span class="label">Username</span>
            <input v-model="createForm.username" class="input" placeholder="Student: 10-digit ID" />
          </label>

          <label class="field">
            <span class="label">Email</span>
            <input v-model="createForm.email" class="input" type="email" />
          </label>

          <label class="field">
            <span class="label">Initial Password</span>
            <input v-model="createForm.password" class="input" type="password" />
          </label>

          <label class="field">
            <span class="label">Full Name</span>
            <input v-model="createForm.full_name" class="input" />
          </label>

          <label class="field">
            <span class="label">Major</span>
            <input v-model="createForm.major" class="input" />
          </label>

          <label class="field">
            <span class="label">Year Of Study</span>
            <input v-model="createForm.year_of_study" class="input" type="number" min="1" max="12" />
          </label>

          <label class="field field--inline">
            <input v-model="createForm.is_active" type="checkbox" />
            <span class="label">Active</span>
          </label>

          <label class="field span-all">
            <span class="label">Bio</span>
            <textarea v-model="createForm.bio" class="textarea" rows="3"></textarea>
          </label>

          <template v-if="isAdminCreate">
            <label class="field">
              <span class="label">Admin Permission Level</span>
              <select v-model="createForm.admin_permission_level" class="select">
                <option value="full">Full</option>
                <option value="limited">Limited</option>
              </select>
            </label>

            <label class="field">
              <span class="label">Admin Permission Keys</span>
              <input v-model="createForm.admin_permissions" class="input" placeholder="user.read,user.update" />
            </label>

            <label class="field span-all">
              <span class="label">Admin Expires At</span>
              <input v-model="createForm.admin_expires_at" class="input" type="datetime-local" />
            </label>
          </template>

          <div class="actions span-all">
            <button class="button button--primary" :disabled="creating" type="submit">Create User</button>
          </div>
        </form>
      </section>

      <section class="panel form-panel">
        <div class="title-row">
          <div>
            <p class="eyebrow">Privilege control</p>
            <h2 class="section-title">Grant / update admin access</h2>
          </div>
        </div>

        <form class="form-grid" @submit.prevent="applyGrantForm">
          <label class="field">
            <span class="label">Target User ID</span>
            <input v-model="grantForm.target_user_id" class="input" type="number" min="1" />
          </label>

          <label class="field">
            <span class="label">Permission Level</span>
            <select v-model="grantForm.permission_level" class="select">
              <option value="full">Full</option>
              <option value="limited">Limited</option>
            </select>
          </label>

          <label class="field">
            <span class="label">Permission Keys</span>
            <input v-model="grantForm.permissions" class="input" placeholder="user.read,user.update" />
          </label>

          <label class="field">
            <span class="label">Expires At</span>
            <input v-model="grantForm.expires_at" class="input" type="datetime-local" />
          </label>

          <div class="actions span-all">
            <button class="button button--primary" :disabled="loading" type="submit">Apply Privileges</button>
            <button class="button button--ghost" :disabled="loading" type="button" @click="refreshUsers">
              Refresh Users
            </button>
          </div>
        </form>
      </section>
    </div>

    <section class="panel table-panel">
      <div class="title-row">
        <div>
          <p class="eyebrow">User list</p>
          <h2 class="section-title">Audit and manage the roster</h2>
        </div>

        <span class="chip chip--neutral">{{ users.length }} records</span>
      </div>

      <div class="table-shell">
        <div class="table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Username</th>
                <th>Role</th>
                <th>Status</th>
                <th>Admin Scope</th>
                <th>Admin Expiry</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in users" :key="user.id">
                <td>{{ user.id }}</td>
                <td>{{ user.username }}</td>
                <td>
                  <span class="chip" :class="user.role === 'admin' ? 'chip--warn' : 'chip--neutral'">
                    {{ user.role }}
                  </span>
                </td>
                <td>
                  <span class="chip" :class="user.is_active ? 'chip--active' : 'chip--warn'">
                    {{ user.is_active ? 'active' : 'disabled' }}
                  </span>
                </td>
                <td>
                  <span v-if="user.role !== 'admin'">-</span>
                  <span v-else>
                    {{ user.admin_permission_level || 'full' }}
                    <template v-if="user.admin_permissions.length">
                      ({{ user.admin_permissions.join(', ') }})
                    </template>
                  </span>
                </td>
                <td>
                  {{ user.admin_expires_at ? new Date(user.admin_expires_at).toLocaleString() : '-' }}
                </td>
                <td>
                  <div class="actions table-actions">
                    <button
                      class="button button--ghost"
                      :disabled="actionLoadingId === user.id"
                      type="button"
                      @click="toggleActive(user)"
                    >
                      {{ user.is_active ? 'Disable' : 'Enable' }}
                    </button>

                    <button
                      v-if="user.role !== 'admin'"
                      class="button button--ghost"
                      :disabled="actionLoadingId === user.id"
                      type="button"
                      @click="quickGrantAdmin(user)"
                    >
                      Quick Grant Admin
                    </button>

                    <button
                      v-else
                      class="button button--ghost"
                      :disabled="actionLoadingId === user.id || user.id === authState.user?.id"
                      type="button"
                      @click="revokeAdmin(user)"
                    >
                      Revoke Admin
                    </button>

                    <button
                      class="button button--danger"
                      :disabled="actionLoadingId === user.id || user.id === authState.user?.id"
                      type="button"
                      @click="removeUser(user)"
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.admin-page {
  width: min(1360px, 100%);
  margin: 0 auto;
}

.admin-grid {
  align-items: start;
}

.form-panel,
.table-panel {
  display: grid;
  gap: 1rem;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.9rem;
}

.table-actions {
  min-width: 300px;
}

.section-title {
  margin: 0;
  font-family: var(--font-display);
  color: var(--heading);
  font-size: clamp(1.2rem, 2vw, 1.6rem);
}

.span-all {
  grid-column: 1 / -1;
}

@media (max-width: 1100px) {
  .form-grid {
    grid-template-columns: 1fr;
  }

  .table-actions {
    min-width: 0;
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
