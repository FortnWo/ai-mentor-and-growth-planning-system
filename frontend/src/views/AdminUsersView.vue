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
  <div class="view">
    <h1>Admin User Management</h1>

    <p v-if="feedback" class="success">{{ feedback }}</p>
    <p v-if="error" class="error">{{ error }}</p>

    <section class="card create-section">
      <h2>Create Account</h2>
      <form class="grid" @submit.prevent="submitCreateUser">
        <label>
          Role
          <select v-model="createForm.role">
            <option value="user">Student</option>
            <option value="admin">Admin</option>
          </select>
        </label>

        <label>
          Username
          <input v-model="createForm.username" placeholder="Student: 10-digit ID" />
        </label>

        <label>
          Email
          <input v-model="createForm.email" type="email" />
        </label>

        <label>
          Initial Password
          <input v-model="createForm.password" type="password" />
        </label>

        <label>
          Full Name
          <input v-model="createForm.full_name" />
        </label>

        <label>
          Major
          <input v-model="createForm.major" />
        </label>

        <label>
          Year Of Study
          <input v-model="createForm.year_of_study" type="number" min="1" max="12" />
        </label>

        <label class="inline-label">
          <input v-model="createForm.is_active" type="checkbox" />
          Active
        </label>

        <label class="span-all">
          Bio
          <textarea v-model="createForm.bio" rows="3" />
        </label>

        <template v-if="isAdminCreate">
          <label>
            Admin Permission Level
            <select v-model="createForm.admin_permission_level">
              <option value="full">Full</option>
              <option value="limited">Limited</option>
            </select>
          </label>

          <label>
            Admin Permission Keys (comma separated)
            <input v-model="createForm.admin_permissions" placeholder="user.read,user.update" />
          </label>

          <label>
            Admin Expires At
            <input v-model="createForm.admin_expires_at" type="datetime-local" />
          </label>
        </template>

        <div class="actions span-all">
          <button :disabled="creating" type="submit">Create User</button>
        </div>
      </form>
    </section>

    <section class="card grant-section">
      <h2>Grant / Update Admin Privileges</h2>
      <form class="grant-grid" @submit.prevent="applyGrantForm">
        <label>
          Target User ID
          <input v-model="grantForm.target_user_id" type="number" min="1" />
        </label>

        <label>
          Permission Level
          <select v-model="grantForm.permission_level">
            <option value="full">Full</option>
            <option value="limited">Limited</option>
          </select>
        </label>

        <label>
          Permission Keys
          <input v-model="grantForm.permissions" placeholder="user.read,user.update" />
        </label>

        <label>
          Expires At
          <input v-model="grantForm.expires_at" type="datetime-local" />
        </label>

        <div class="actions">
          <button :disabled="loading" type="submit">Apply Privileges</button>
          <button :disabled="loading" type="button" @click="refreshUsers">Refresh Users</button>
        </div>
      </form>
    </section>

    <section class="card">
      <h2>User List</h2>
      <div class="table-wrap">
        <table>
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
              <td>{{ user.role }}</td>
              <td>{{ user.is_active ? 'active' : 'disabled' }}</td>
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
              <td class="actions">
                <button
                  :disabled="actionLoadingId === user.id"
                  type="button"
                  @click="toggleActive(user)"
                >
                  {{ user.is_active ? 'Disable' : 'Enable' }}
                </button>

                <button
                  v-if="user.role !== 'admin'"
                  :disabled="actionLoadingId === user.id"
                  type="button"
                  @click="quickGrantAdmin(user)"
                >
                  Quick Grant Admin
                </button>

                <button
                  v-else
                  :disabled="actionLoadingId === user.id || user.id === authState.user?.id"
                  type="button"
                  @click="revokeAdmin(user)"
                >
                  Revoke Admin
                </button>

                <button
                  :disabled="actionLoadingId === user.id || user.id === authState.user?.id"
                  class="danger"
                  type="button"
                  @click="removeUser(user)"
                >
                  Delete
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.view {
  max-width: 1200px;
  margin: 2rem auto;
  padding: 1rem;
  text-align: left;
}

.card {
  border: 1px solid #ddd;
  border-radius: 10px;
  background: #fff;
  padding: 1rem;
  margin-bottom: 1rem;
}

h2 {
  margin: 0 0 0.8rem;
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(220px, 1fr));
  gap: 0.75rem;
}

.grant-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(220px, 1fr));
  gap: 0.75rem;
}

label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.inline-label {
  align-self: center;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
}

input,
textarea,
select,
button {
  font: inherit;
}

input,
textarea,
select {
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 0.5rem 0.65rem;
}

.actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

button {
  border: none;
  border-radius: 6px;
  padding: 0.45rem 0.8rem;
  background: #1d4ed8;
  color: #fff;
  cursor: pointer;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

button.danger {
  background: #b91c1c;
}

.table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  min-width: 900px;
}

th,
td {
  border-bottom: 1px solid #e2e8f0;
  padding: 0.6rem;
  text-align: left;
  vertical-align: top;
}

.success {
  color: #166534;
}

.error {
  color: #b91c1c;
}

.span-all {
  grid-column: 1 / -1;
}

@media (max-width: 1000px) {
  .grid,
  .grant-grid {
    grid-template-columns: 1fr;
  }
}
</style>
