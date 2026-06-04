<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import AdminPermissionPicker from '../components/AdminPermissionPicker.vue'
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
import { getApiErrorMessage } from '../utils/apiError'
import { parseOptionalInteger } from '../utils/number'

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
  admin_permissions: string[]
  admin_expires_at: string
}

type GrantFormState = {
  target_user_id: string
  permission_level: AdminPermissionLevel
  permissions: string[]
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
  admin_permissions: ['user.read', 'user.update'],
  admin_expires_at: '',
})

const grantForm = reactive<GrantFormState>({
  target_user_id: '',
  permission_level: 'limited',
  permissions: ['user.read'],
  expires_at: '',
})

const isAdminCreate = computed(() => createForm.role === 'admin')

function clearMessages() {
  feedback.value = ''
  error.value = ''
}

function canToggleActive(user: UserRead): boolean {
  return user.role !== 'admin'
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
    error.value = '无法加载用户。'
  } finally {
    loading.value = false
  }
}

function buildCreatePayload(): UserCreatePayload {
  const yearOfStudy = parseOptionalInteger(createForm.year_of_study)
  const payload: UserCreatePayload = {
    username: createForm.username.trim(),
    email: createForm.email.trim(),
    password: createForm.password,
    role: createForm.role,
    is_active: createForm.is_active,
    full_name: createForm.full_name.trim() || undefined,
    major: createForm.major.trim() || undefined,
    year_of_study: yearOfStudy,
    bio: createForm.bio.trim() || undefined,
  }

  if (createForm.role === 'admin') {
    payload.admin_permission_level = createForm.admin_permission_level
    payload.admin_permissions = [...createForm.admin_permissions]
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
  createForm.admin_permissions = ['user.read', 'user.update']
  createForm.admin_expires_at = ''
}

async function submitCreateUser() {
  clearMessages()

  if (!createForm.username.trim() || !createForm.email.trim() || !createForm.password.trim()) {
    error.value = '用户名、邮箱和密码为必填项。'
    return
  }

  const yearOfStudy = parseOptionalInteger(createForm.year_of_study)
  if (createForm.year_of_study !== '' && yearOfStudy === undefined) {
    error.value = '年级必须是 1 到 12 之间的整数。'
    return
  }

  if (createForm.role === 'user' && !/^\d{10}$/.test(createForm.username.trim())) {
    error.value = '学生用户名必须是 10 位学号。'
    return
  }

  try {
    creating.value = true
    const created = await createUser(buildCreatePayload())
    feedback.value = `已创建用户 #${created.id}（${created.username}）。`
    resetCreateForm()
    await refreshUsers()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError, '创建用户失败，请检查唯一性和角色规则。')
  } finally {
    creating.value = false
  }
}

async function toggleActive(user: UserRead) {
  clearMessages()

  if (!canToggleActive(user)) {
    error.value = '管理员账号不可禁用或启用。'
    return
  }

  try {
    actionLoadingId.value = user.id
    const updated = await updateUser(user.id, { is_active: !user.is_active })
    feedback.value = `已更新 #${updated.id} 的状态。`
    await refreshUsers()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError, '更新用户状态失败。')
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
    feedback.value = `已向 #${updated.id} 授予临时管理员权限。`
    await refreshUsers()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError, '授予管理员权限失败。')
  } finally {
    actionLoadingId.value = null
  }
}

async function applyGrantForm() {
  clearMessages()

  const targetId = Number(grantForm.target_user_id)
  if (!Number.isInteger(targetId) || targetId <= 0) {
    error.value = '请输入有效的目标用户 ID。'
    return
  }

  const permissions = [...grantForm.permissions]
  if (grantForm.permission_level === 'limited' && !permissions.length) {
    error.value = '有限权限至少需要一个权限键。'
    return
  }

  try {
    actionLoadingId.value = targetId
    const updated = await grantAdminAccess(targetId, {
      permission_level: grantForm.permission_level,
      permissions,
      expires_at: toIsoString(grantForm.expires_at),
    })
    feedback.value = `已更新 #${updated.id} 的管理员权限。`
    await refreshUsers()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError, '应用管理员权限更新失败。')
  } finally {
    actionLoadingId.value = null
  }
}

async function revokeAdmin(user: UserRead) {
  clearMessages()

  try {
    actionLoadingId.value = user.id
    const updated = await revokeAdminAccess(user.id)
    feedback.value = `已撤销 #${updated.id} 的管理员权限。`
    await refreshUsers()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError, '撤销管理员权限失败。')
  } finally {
    actionLoadingId.value = null
  }
}

async function removeUser(user: UserRead) {
  if (user.id === authState.user?.id) {
    error.value = '你不能在这里删除自己的账号。'
    return
  }

  const confirmed = window.confirm(`确定删除用户 #${user.id}（${user.username}）吗？`)
  if (!confirmed) {
    return
  }

  clearMessages()
  try {
    actionLoadingId.value = user.id
    await deleteUser(user.id)
    feedback.value = `已删除用户 #${user.id}。`
    await refreshUsers()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError, '删除用户失败。')
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
    <p v-if="feedback" class="feedback feedback--success">{{ feedback }}</p>
    <p v-if="error" class="feedback feedback--error">{{ error }}</p>

    <div class="grid-2 admin-grid">
      <section class="panel form-panel reveal reveal--delay-1">
        <div class="title-row">
          <div>
            <p class="eyebrow">创建账号</p>
            <h2 class="section-title">新用户</h2>
          </div>

          <span class="chip" :class="isAdminCreate ? 'chip--warn' : 'chip--active'">
            {{ isAdminCreate ? '管理员流程' : '学生流程' }}
          </span>
        </div>

        <form class="form-grid" @submit.prevent="submitCreateUser">
          <label class="field">
            <span class="label">角色</span>
            <select v-model="createForm.role" class="select">
              <option value="user">学生</option>
              <option value="admin">管理员</option>
            </select>
          </label>

          <div class="field">
            <span class="label">账号状态</span>
            <div class="status-segmented" role="radiogroup" aria-label="账号状态">
              <button
                type="button"
                class="status-seg-btn"
                :class="{ 'status-seg-btn--active': createForm.is_active }"
                :aria-pressed="createForm.is_active"
                @click="createForm.is_active = true"
              >
                启用
              </button>
              <button
                type="button"
                class="status-seg-btn"
                :class="{ 'status-seg-btn--active': !createForm.is_active }"
                :aria-pressed="!createForm.is_active"
                @click="createForm.is_active = false"
              >
                禁用
              </button>
            </div>
            <small class="hint">禁用后该用户无法登录。</small>
          </div>

          <label class="field">
            <span class="label">用户名</span>
            <input v-model="createForm.username" class="input" placeholder="学生：10 位学号" />
          </label>

          <label class="field">
            <span class="label">邮箱</span>
            <input v-model="createForm.email" class="input" type="email" />
          </label>

          <label class="field">
            <span class="label">初始密码</span>
            <input v-model="createForm.password" class="input" type="password" />
            <small class="hint">至少 8 个字符。</small>
          </label>

          <label class="field">
            <span class="label">姓名</span>
            <input v-model="createForm.full_name" class="input" />
          </label>

          <label class="field">
            <span class="label">专业</span>
            <input v-model="createForm.major" class="input" />
          </label>

          <label class="field">
            <span class="label">年级</span>
            <input
              v-model="createForm.year_of_study"
              class="input"
              type="number"
              min="1"
              max="12"
              step="1"
            />
            <small class="hint">输入 1 到 12 的整数，或留空。</small>
          </label>

          <label class="field span-all">
            <span class="label">简介</span>
            <textarea v-model="createForm.bio" class="textarea" rows="3"></textarea>
          </label>

          <template v-if="isAdminCreate">
            <label class="field">
              <span class="label">管理员权限级别</span>
              <select v-model="createForm.admin_permission_level" class="select">
                <option value="full">完整</option>
                <option value="limited">有限</option>
              </select>
            </label>

            <div v-if="createForm.admin_permission_level === 'limited'" class="field">
              <span class="label">管理员权限键</span>
              <AdminPermissionPicker v-model="createForm.admin_permissions" />
            </div>
            <div v-else class="field span-all">
              <span class="label">管理员权限键</span>
              <small class="hint">完整权限包含全部操作，无需单独勾选。</small>
            </div>

            <label class="field span-all">
              <span class="label">管理员过期时间</span>
              <input v-model="createForm.admin_expires_at" class="input" type="datetime-local" />
            </label>
          </template>

          <div class="actions span-all">
            <button class="button button--primary" :disabled="creating" type="submit">创建用户</button>
          </div>
        </form>
      </section>

      <section class="panel form-panel reveal reveal--delay-2">
        <div class="title-row">
          <div>
            <p class="eyebrow">权限控制</p>
            <h2 class="section-title">授予 / 更新管理员权限</h2>
          </div>
        </div>

        <form class="form-grid" @submit.prevent="applyGrantForm">
          <label class="field">
            <span class="label">目标用户 ID</span>
            <input v-model="grantForm.target_user_id" class="input" type="number" min="1" />
          </label>

          <label class="field">
            <span class="label">权限级别</span>
            <select v-model="grantForm.permission_level" class="select">
              <option value="full">完整</option>
              <option value="limited">有限</option>
            </select>
          </label>

          <div v-if="grantForm.permission_level === 'limited'" class="field">
            <span class="label">权限键</span>
            <AdminPermissionPicker v-model="grantForm.permissions" />
          </div>
          <div v-else class="field">
            <span class="label">权限键</span>
            <small class="hint">完整权限包含全部操作，无需单独勾选。</small>
          </div>

          <label class="field">
            <span class="label">过期时间</span>
            <input v-model="grantForm.expires_at" class="input" type="datetime-local" />
          </label>

          <div class="actions span-all">
            <button class="button button--primary" :disabled="loading" type="submit">应用权限</button>
            <button class="button button--ghost" :disabled="loading" type="button" @click="refreshUsers">
              刷新用户
            </button>
          </div>
        </form>
      </section>
    </div>

    <section class="panel table-panel reveal reveal--delay-3">
      <div class="title-row">
        <div>
          <p class="eyebrow">用户列表</p>
          <h2 class="section-title">审计并管理名单</h2>
        </div>

        <div class="table-panel__actions">
          <span class="chip chip--neutral">{{ users.length }} records</span>
          <button class="button button--ghost" :disabled="loading" type="button" @click="refreshUsers">
            刷新用户
          </button>
        </div>
      </div>

      <div class="table-shell">
        <div class="table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>用户名</th>
                <th>角色</th>
                <th>状态</th>
                <th>管理员范围</th>
                <th>管理员过期时间</th>
                <th>操作</th>
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
                    {{ user.is_active ? '启用' : '禁用' }}
                  </span>
                </td>
                <td>
                  <span v-if="user.role !== 'admin'">-</span>
                  <span v-else>
                    {{ user.admin_permission_level || '完整' }}
                    <template v-if="user.admin_permissions.length">
                      （{{ user.admin_permissions.join(', ') }}）
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
                      :disabled="actionLoadingId === user.id || !canToggleActive(user)"
                      :title="!canToggleActive(user) ? '管理员账号不可变更启用状态' : undefined"
                      type="button"
                      @click="toggleActive(user)"
                    >
                      {{ user.is_active ? '禁用' : '启用' }}
                    </button>

                    <button
                      v-if="user.role !== 'admin'"
                      class="button button--ghost"
                      :disabled="actionLoadingId === user.id"
                      type="button"
                      @click="quickGrantAdmin(user)"
                    >
                      快速授予管理员
                    </button>

                    <button
                      v-else
                      class="button button--ghost"
                      :disabled="actionLoadingId === user.id || user.id === authState.user?.id"
                      type="button"
                      @click="revokeAdmin(user)"
                    >
                      撤销管理员
                    </button>

                    <button
                      class="button button--danger"
                      :disabled="actionLoadingId === user.id || user.id === authState.user?.id"
                      type="button"
                      @click="removeUser(user)"
                    >
                      删除
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

.table-panel__actions {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  flex-wrap: wrap;
}

.section-title {
  margin: 0;
  font-family: var(--font-display);
  color: var(--heading);
  font-size: clamp(1.2rem, 2vw, 1.6rem);
}

.hint {
  color: var(--text-muted);
  font-size: 0.78rem;
  line-height: 1.4;
}

.span-all {
  grid-column: 1 / -1;
}

.status-segmented {
  display: flex;
  width: 100%;
  padding: 3px;
  border-radius: var(--radius-md, 14px);
  background: var(--chip-bg);
  border: 1px solid var(--table-row-border);
}

.status-seg-btn {
  flex: 1;
  border: none;
  cursor: pointer;
  padding: 0.65rem 0.9rem;
  min-height: 44px;
  border-radius: var(--radius-sm, 10px);
  font: inherit;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-muted);
  background: transparent;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease;
}

.status-seg-btn--active {
  color: var(--heading);
  background: rgba(var(--accent-1-rgb), 0.12);
  box-shadow: 0 0 0 1px rgba(var(--accent-1-rgb), 0.22);
}

.status-seg-btn:not(.status-seg-btn--active):hover {
  color: var(--heading);
  background: rgba(var(--accent-1-rgb), 0.06);
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
