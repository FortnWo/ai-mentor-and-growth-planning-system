<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import AdminPermissionCheckboxes from '../components/AdminPermissionCheckboxes.vue'
import AdminPermissionPicker from '../components/AdminPermissionPicker.vue'
import {
  ADMIN_PERMISSION_KEYS,
  DEFAULT_ONE_CLICK_ADMIN_PERMISSIONS,
  type AdminPermissionKey,
} from '../constants/adminPermissions'
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
import { authState, isFullAdmin, refreshCurrentUser } from '../stores/auth'
import { getApiErrorMessage } from '../utils/apiError'

// ── Types ─────────────────────────────────────────────────────────────────────

type ActiveTab = 'list' | 'register'
type RegisterSubTab = 'single' | 'excel'

type CreateFormState = {
  username: string
  email: string
  password: string
  role: UserRole
  full_name: string
  major: string
  enrollment_year: string
  phone: string
  bio: string
  is_active: boolean
  admin_permission_level: AdminPermissionLevel
  admin_permissions: string[]
  admin_expires_at: string
}

type EditFormState = {
  id?: number
  username?: string
  email?: string
  role?: UserRole
  full_name: string
  major: string
  enrollment_year: string | number
  phone: string
  bio: string
  is_active: boolean
  admin_permissions: AdminPermissionKey[]
}

// ── State ─────────────────────────────────────────────────────────────────────

const router = useRouter()
const fullAdmin = computed(() => isFullAdmin(authState.user))

const activeTab = ref<ActiveTab>('list')
const registerSubTab = ref<RegisterSubTab>('single')

const users = ref<UserRead[]>([])
const loading = ref(false)
const feedback = ref('')
const error = ref('')

// Search filters
const searchUsername = ref('')
const searchMajor = ref('')
const searchYear = ref('')
const searchActive = ref<'' | 'true' | 'false'>('')

// Bulk selection
const selectedIds = ref<Set<number>>(new Set())
const bulkPassword = ref('usth123456')
const bulkLoading = ref(false)
const showBulkPanel = ref(false)

// Row edit state
const editingUserId = ref<number | null>(null)
const editForm = reactive<EditFormState>({
  full_name: '',
  major: '',
  enrollment_year: '',
  phone: '',
  bio: '',
  is_active: true,
  admin_permissions: [],
})
const editOriginalRole = ref<UserRole>('user')
const editOriginalPermissions = ref<AdminPermissionKey[]>([])
const editLoading = ref(false)

// Create form
const creating = ref(false)
const createForm = reactive<CreateFormState>({
  username: '',
  email: '',
  password: 'usth123456',
  role: 'user',
  full_name: '',
  major: '',
  enrollment_year: '',
  phone: '',
  bio: '',
  is_active: true,
  admin_permission_level: 'limited',
  admin_permissions: ['user.read', 'user.update'],
  admin_expires_at: '',
})

// Excel import state
const excelFile = ref<File | null>(null)
const excelLoading = ref(false)
const excelResult = ref<{ success_count: number; failed: { row: number; reason: string }[] } | null>(null)
const dropActive = ref(false)

// ── Computed ─────────────────────────────────────────────────────────────────

const allSelected = computed(() =>
  users.value.length > 0 && users.value.every((u) => selectedIds.value.has(u.id)),
)

const isAdminCreate = computed(() => createForm.role === 'admin')

const isSystemAdminUsername = computed(() => createForm.username.trim() === 'admin')

// ── Helpers ───────────────────────────────────────────────────────────────────

function clearMessages() {
  feedback.value = ''
  error.value = ''
}

function toIsoString(value: string): string | undefined {
  if (!value.trim()) return undefined
  const d = new Date(value)
  return isNaN(d.getTime()) ? undefined : d.toISOString()
}

function goToUserUsage(user: UserRead) {
  if (!fullAdmin.value) return
  void router.push({ name: 'AdminUserUsage', params: { userId: user.id } })
}

function formatDate(iso: string | undefined | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString()
}

// ── Fetch ────────────────────────────────────────────────────────────────────

async function refreshUsers() {
  clearMessages()
  loading.value = true
  try {
    const filters: {
      username_like?: string
      major?: string
      year?: number
      is_active?: boolean
    } = {}
    if (searchUsername.value.trim()) filters.username_like = searchUsername.value.trim()
    if (searchMajor.value.trim()) filters.major = searchMajor.value.trim()
    if (searchYear.value.trim()) {
      const yr = parseInt(searchYear.value.trim(), 10)
      if (!Number.isNaN(yr)) filters.year = yr
    }
    if (searchActive.value !== '') filters.is_active = searchActive.value === 'true'

    users.value = await listUsers(0, 200, filters)
    selectedIds.value.clear()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError, '无法加载用户列表，请刷新重试。')
  } finally {
    loading.value = false
  }
}

// ── Selection ────────────────────────────────────────────────────────────────

function toggleSelect(id: number) {
  if (selectedIds.value.has(id)) {
    selectedIds.value.delete(id)
  } else {
    selectedIds.value.add(id)
  }
}

function toggleSelectAll() {
  if (allSelected.value) {
    selectedIds.value.clear()
  } else {
    users.value.forEach((u) => selectedIds.value.add(u.id))
  }
}

// ── Bulk operations ──────────────────────────────────────────────────────────

async function handleBulkResetPassword() {
  if (selectedIds.value.size === 0) {
    error.value = '请先选择用户。'
    return
  }
  if (!bulkPassword.value || bulkPassword.value.length < 8) {
    error.value = '批量重置密码不能少于 8 位。'
    return
  }
  clearMessages()
  bulkLoading.value = true
  try {
    const { default: apiClient } = await import('../api/client')
    const res = await apiClient.post('/admin/users/bulk-reset-password', {
      user_ids: Array.from(selectedIds.value),
      new_password: bulkPassword.value,
    })
    const data = res.data as { success_count: number; failed_ids: number[] }
    feedback.value = `批量重置成功 ${data.success_count} 个，失败 ${data.failed_ids.length} 个。`
    selectedIds.value.clear()
    showBulkPanel.value = false
  } catch (err) {
    error.value = getApiErrorMessage(err, '批量重置失败，请重试。')
  } finally {
    bulkLoading.value = false
  }
}

// ── Row edit ────────────────────────────────────────────────────────────────

function normalizePermissionKeys(permissions: string[] | undefined): AdminPermissionKey[] {
  const allowed = new Set(ADMIN_PERMISSION_KEYS)
  return (permissions ?? []).filter((key): key is AdminPermissionKey =>
    allowed.has(key as AdminPermissionKey),
  )
}

function permissionsChanged(current: AdminPermissionKey[], original: AdminPermissionKey[]): boolean {
  if (current.length !== original.length) {
    return true
  }
  const sortedCurrent = [...current].sort()
  const sortedOriginal = [...original].sort()
  return sortedCurrent.some((key, index) => key !== sortedOriginal[index])
}

function startEdit(user: UserRead) {
  const permissions = normalizePermissionKeys(user.admin_permissions)
  editingUserId.value = user.id
  editOriginalRole.value = user.role
  editOriginalPermissions.value = [...permissions]
  Object.assign(editForm, {
    id: user.id,
    username: user.username,
    email: user.email,
    role: user.role,
    full_name: user.full_name ?? '',
    major: user.major ?? '',
    enrollment_year: user.enrollment_year ?? '',
    phone: user.phone ?? '',
    bio: user.bio ?? '',
    is_active: user.is_active,
    admin_permissions: [...permissions],
  })
}

function cancelEdit() {
  editingUserId.value = null
}

async function saveEdit(userId: number) {
  const targetUser = users.value.find((user) => user.id === userId)
  if (!targetUser) {
    return
  }

  clearMessages()
  editLoading.value = true
  try {
    await updateUser(userId, {
      full_name: (editForm.full_name as string) || undefined,
      major: (editForm.major as string) || undefined,
      enrollment_year: editForm.enrollment_year ? Number(editForm.enrollment_year) : undefined,
      phone: (editForm.phone as string) || undefined,
      bio: (editForm.bio as string) || undefined,
      is_active: editForm.is_active as boolean,
    })

    const nextPermissions = [...(editForm.admin_permissions ?? [])]
    const roleChanged = editOriginalRole.value !== editForm.role
    const permsChanged = permissionsChanged(nextPermissions, editOriginalPermissions.value)

    if (!targetUser.is_system_admin && (roleChanged || permsChanged)) {
      if (nextPermissions.length === 0) {
        if (editOriginalRole.value === 'admin' || targetUser.role === 'admin') {
          await revokeAdminAccess(userId)
        }
      } else {
        await grantAdminAccess(userId, {
          permission_level: 'limited',
          permissions: nextPermissions,
        })
      }
    }

    if (authState.user?.id === userId) {
      await refreshCurrentUser()
    }

    feedback.value = '用户信息更新成功。'
    editingUserId.value = null
    await refreshUsers()
  } catch (err) {
    error.value = getApiErrorMessage(err, '更新失败，请检查输入内容。')
  } finally {
    editLoading.value = false
  }
}

async function handleDeleteUser(userId: number, username: string) {
  if (!confirm(`确认删除用户「${username}」？此操作不可撤销。`)) return
  clearMessages()
  try {
    await deleteUser(userId)
    feedback.value = `用户 ${username} 已删除。`
    await refreshUsers()
  } catch (err) {
    error.value = getApiErrorMessage(err, '删除失败。')
  }
}

async function handleGrantAdmin(userId: number) {
  clearMessages()
  try {
    await grantAdminAccess(userId, {
      permission_level: 'limited',
      permissions: [...DEFAULT_ONE_CLICK_ADMIN_PERMISSIONS],
    })
    if (authState.user?.id === userId) {
      await refreshCurrentUser()
    }
    feedback.value = '已授予临时管理权限（查看 / 创建 / 更新用户）。'
    await refreshUsers()
  } catch (err) {
    error.value = getApiErrorMessage(err, '授权失败。')
  }
}

async function handleRevokeAdmin(userId: number) {
  clearMessages()
  try {
    await revokeAdminAccess(userId)
    if (authState.user?.id === userId) {
      await refreshCurrentUser()
    }
    feedback.value = '已撤销管理员权限。'
    await refreshUsers()
  } catch (err) {
    error.value = getApiErrorMessage(err, '撤销失败。')
  }
}

// ── Single register ───────────────────────────────────────────────────────────

function resetCreateForm() {
  createForm.username = ''
  createForm.email = ''
  createForm.password = 'usth123456'
  createForm.role = 'user'
  createForm.full_name = ''
  createForm.major = ''
  createForm.enrollment_year = ''
  createForm.phone = ''
  createForm.bio = ''
  createForm.is_active = true
  createForm.admin_permission_level = 'limited'
  createForm.admin_permissions = ['user.read', 'user.update']
  createForm.admin_expires_at = ''
}

async function submitCreateUser() {
  clearMessages()
  if (!createForm.username.trim() || !createForm.email.trim()) {
    error.value = '用户名和邮箱为必填项。'
    return
  }
  creating.value = true
  try {
    const payload: UserCreatePayload = {
      username: createForm.username.trim(),
      email: createForm.email.trim(),
      password: createForm.password || 'usth123456',
      role: createForm.role,
      is_active: createForm.is_active,
      full_name: createForm.full_name.trim() || undefined,
      major: createForm.major.trim() || undefined,
      enrollment_year: createForm.enrollment_year ? Number(createForm.enrollment_year) : undefined,
      phone: createForm.phone.trim() || undefined,
      bio: createForm.bio.trim() || undefined,
    }
    if (createForm.role === 'admin') {
      if (payload.username === 'admin') {
        payload.admin_permission_level = 'full'
        payload.admin_permissions = []
        payload.admin_expires_at = undefined
      } else {
        payload.admin_permission_level = createForm.admin_permission_level
        payload.admin_permissions = [...createForm.admin_permissions]
        payload.admin_expires_at = toIsoString(createForm.admin_expires_at)
      }
    }
    await createUser(payload)
    feedback.value = `用户「${payload.username}」注册成功。`
    resetCreateForm()
    await refreshUsers()
    activeTab.value = 'list'
  } catch (err) {
    error.value = getApiErrorMessage(err, '注册失败，请检查输入内容。')
  } finally {
    creating.value = false
  }
}

// ── Excel import ──────────────────────────────────────────────────────────────

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  excelFile.value = input.files?.[0] ?? null
  excelResult.value = null
}

function onDrop(e: DragEvent) {
  dropActive.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) {
    excelFile.value = file
    excelResult.value = null
  }
}

async function submitExcelImport() {
  if (!excelFile.value) {
    error.value = '请选择 Excel 文件。'
    return
  }
  clearMessages()
  excelLoading.value = true
  excelResult.value = null
  try {
    const formData = new FormData()
    formData.append('file', excelFile.value)
    const { default: apiClient } = await import('../api/client')
    const res = await apiClient.post('/admin/users/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    excelResult.value = res.data
    if (res.data.success_count > 0) {
      await refreshUsers()
      activeTab.value = 'list'
    }
  } catch (err) {
    error.value = getApiErrorMessage(err, 'Excel 导入失败，请检查文件格式。')
  } finally {
    excelLoading.value = false
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────

onMounted(async () => {
  if (!authState.user) await refreshCurrentUser()
  await refreshUsers()
})
</script>

<template>
  <div class="page page--wide admin-users-page">

    <div class="page-header reveal">
      <p class="page-kicker">管理员工作区</p>
      <h1 class="page-title">用户管理</h1>
      <p class="page-subtitle">查看、注册、搜索和批量管理学生账号。</p>
    </div>

    <p v-if="error" class="feedback feedback--error">{{ error }}</p>
    <p v-if="feedback" class="feedback feedback--success">{{ feedback }}</p>

    <!-- ── Tab bar ── -->
    <div class="tab-bar reveal reveal--delay-1">
      <button
        class="tab-btn"
        :class="{ 'tab-btn--active': activeTab === 'list' }"
        type="button"
        @click="activeTab = 'list'"
      >
        用户列表
        <span class="tab-badge">{{ users.length }}</span>
      </button>
      <button
        class="tab-btn"
        :class="{ 'tab-btn--active': activeTab === 'register' }"
        type="button"
        @click="activeTab = 'register'"
      >
        注册用户
      </button>
    </div>

    <!-- ════════════════════ TAB: LIST ════════════════════ -->
    <div v-if="activeTab === 'list'" class="tab-content reveal reveal--delay-2">

      <!-- Search bar -->
      <div class="search-bar panel">
        <label class="field field--inline">
          <span class="label">学号</span>
          <input v-model="searchUsername" class="input input--sm" placeholder="模糊搜索" @keydown.enter="refreshUsers" />
        </label>
        <label class="field field--inline">
          <span class="label">专业</span>
          <input v-model="searchMajor" class="input input--sm" placeholder="专业名称" @keydown.enter="refreshUsers" />
        </label>
        <label class="field field--inline">
          <span class="label">入学年份</span>
          <input v-model="searchYear" class="input input--sm" type="number" placeholder="如 2022" @keydown.enter="refreshUsers" />
        </label>
        <label class="field field--inline">
          <span class="label">状态</span>
          <select v-model="searchActive" class="input input--sm">
            <option value="">全部</option>
            <option value="true">启用</option>
            <option value="false">禁用</option>
          </select>
        </label>
        <button class="button button--primary" :disabled="loading" type="button" @click="refreshUsers">
          {{ loading ? '搜索中…' : '搜索' }}
        </button>
        <button class="button button--ghost" type="button" @click="() => { searchUsername = ''; searchMajor = ''; searchYear = ''; searchActive = ''; refreshUsers() }">
          清除
        </button>
      </div>

      <!-- Bulk action bar -->
      <div v-if="selectedIds.size > 0" class="bulk-bar panel">
        <span class="bulk-count">已选 {{ selectedIds.size }} 个用户</span>
        <button class="button button--ghost" type="button" @click="showBulkPanel = !showBulkPanel">
          {{ showBulkPanel ? '收起' : '批量重置密码' }}
        </button>
        <button class="button button--ghost" type="button" @click="selectedIds.clear()">取消选择</button>
      </div>

      <transition name="fade-slide">
        <div v-if="showBulkPanel && selectedIds.size > 0" class="bulk-panel panel">
          <label class="field">
            <span class="label">新密码（适用于所有选中用户）</span>
            <input v-model="bulkPassword" class="input" type="password" placeholder="不少于 8 位" />
          </label>
          <div class="actions">
            <button class="button button--primary" :disabled="bulkLoading" type="button" @click="handleBulkResetPassword">
              {{ bulkLoading ? '重置中…' : `确认重置 ${selectedIds.size} 个账号` }}
            </button>
          </div>
        </div>
      </transition>

      <!-- Users table -->
      <div class="panel table-panel">
        <div class="table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th class="col-check">
                  <input type="checkbox" :checked="allSelected" @change="toggleSelectAll" />
                </th>
                <th>学号</th>
                <th>姓名</th>
                <th>专业</th>
                <th>入学年</th>
                <th>手机</th>
                <th>邮箱</th>
                <th>角色</th>
                <th>状态</th>
                <th>注册时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <template v-if="users.length === 0">
                <tr>
                  <td colspan="11" class="empty-row">{{ loading ? '加载中…' : '暂无用户数据' }}</td>
                </tr>
              </template>
              <template v-for="user in users">
                <!-- View row -->
                <tr
                  v-if="editingUserId !== user.id"
                  :key="`${user.id}-view`"
                  class="data-row"
                  :class="{ 'data-row--clickable': fullAdmin }"
                  @click="goToUserUsage(user)"
                >
                  <td class="col-check" @click.stop>
                    <input type="checkbox" :checked="selectedIds.has(user.id)" @change="toggleSelect(user.id)" />
                  </td>
                  <td class="mono">{{ user.username }}</td>
                  <td>{{ user.full_name || '—' }}</td>
                  <td>{{ user.major || '—' }}</td>
                  <td>{{ user.enrollment_year || '—' }}</td>
                  <td>{{ user.phone || '—' }}</td>
                  <td class="text-ellipsis">{{ user.email }}</td>
                  <td>
                    <span class="chip" :class="user.role === 'admin' ? 'chip--admin' : 'chip--user'">
                      {{ user.is_system_admin ? '系统管理员' : user.role === 'admin' ? '管理员' : '学生' }}
                    </span>
                    <span v-if="user.is_system_admin" class="chip chip--locked" title="权限固定为完整，不可修改">FULL</span>
                  </td>
                  <td>
                    <span class="chip" :class="user.is_active ? 'chip--active' : 'chip--warn'">
                      {{ user.is_active ? '启用' : '禁用' }}
                    </span>
                  </td>
                  <td>{{ formatDate(user.created_at) }}</td>
                  <td @click.stop>
                    <div class="row-actions">
                      <button class="btn-icon" title="编辑" type="button" @click="startEdit(user)">✏️</button>
                      <button
                        v-if="user.role !== 'admin' && !user.is_system_admin"
                        class="btn-icon"
                        title="一键授予临时管理权限（查看/创建/更新用户）"
                        type="button"
                        @click="handleGrantAdmin(user.id)"
                      >🔑</button>
                      <button
                        v-if="user.role === 'admin' && !user.is_system_admin"
                        class="btn-icon"
                        title="撤销管理员"
                        type="button"
                        @click="handleRevokeAdmin(user.id)"
                      >🚫</button>
                      <button
                        v-if="!user.is_system_admin"
                        class="btn-icon btn-icon--danger"
                        title="删除"
                        type="button"
                        @click="handleDeleteUser(user.id, user.username)"
                      >🗑️</button>
                    </div>
                  </td>
                </tr>

                <!-- Edit row -->
                <tr v-else :key="`${user.id}-edit`" class="data-row data-row--editing">
                  <td class="col-check">
                    <input type="checkbox" disabled />
                  </td>
                  <td class="mono">{{ user.username }}</td>
                  <td><input v-model="editForm.full_name" class="input input--xs" placeholder="姓名" /></td>
                  <td><input v-model="editForm.major" class="input input--xs" placeholder="专业" /></td>
                  <td><input v-model="editForm.enrollment_year" class="input input--xs" type="number" placeholder="入学年" /></td>
                  <td><input v-model="editForm.phone" class="input input--xs" placeholder="手机" maxlength="11" /></td>
                  <td>{{ user.email }}</td>
                  <td class="col-role-edit">
                    <p class="role-edit-label">
                      {{
                        user.is_system_admin
                          ? '系统管理员'
                          : user.role === 'admin'
                            ? '管理员'
                            : '学生'
                      }}
                    </p>
                    <p v-if="user.is_system_admin" class="role-edit-hint">FULL 锁定</p>
                    <div v-else class="role-edit-perms">
                      <AdminPermissionCheckboxes
                        v-model="editForm.admin_permissions"
                        popover
                      />
                    </div>
                  </td>
                  <td>
                    <select
                      v-model="editForm.is_active"
                      class="input input--xs"
                      :disabled="user.is_system_admin"
                    >
                      <option :value="true">启用</option>
                      <option :value="false">禁用</option>
                    </select>
                  </td>
                  <td>{{ formatDate(user.created_at) }}</td>
                  <td>
                    <div class="row-actions">
                      <button class="btn-icon" title="保存" :disabled="editLoading" type="button" @click="saveEdit(user.id)">💾</button>
                      <button class="btn-icon" title="取消" type="button" @click="cancelEdit">✖️</button>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ════════════════════ TAB: REGISTER ════════════════════ -->
    <div v-else-if="activeTab === 'register'" class="tab-content reveal reveal--delay-2">

      <!-- Sub-tabs -->
      <div class="sub-tab-bar">
        <button
          class="tab-btn tab-btn--sm"
          :class="{ 'tab-btn--active': registerSubTab === 'single' }"
          type="button"
          @click="registerSubTab = 'single'"
        >
          单个注册
        </button>
        <button
          class="tab-btn tab-btn--sm"
          :class="{ 'tab-btn--active': registerSubTab === 'excel' }"
          type="button"
          @click="registerSubTab = 'excel'"
        >
          Excel 批量导入
        </button>
      </div>

      <!-- Single register form -->
      <div v-if="registerSubTab === 'single'" class="panel register-form">
        <div class="title-row">
          <div>
            <p class="eyebrow">新用户注册</p>
            <h2 class="section-title">单个账号注册</h2>
          </div>
        </div>

        <form class="form-grid" @submit.prevent="submitCreateUser">
          <label class="field">
            <span class="label">用户名（学号）<span class="required">*</span></span>
            <input v-model="createForm.username" class="input" placeholder="10 位学号（学生）或自定义（管理员）" maxlength="100" />
          </label>

          <label class="field">
            <span class="label">邮箱 <span class="required">*</span></span>
            <input v-model="createForm.email" class="input" type="email" placeholder="电子邮箱" />
          </label>

          <label class="field">
            <span class="label">姓名</span>
            <input v-model="createForm.full_name" class="input" placeholder="真实姓名（选填）" />
          </label>

          <label class="field">
            <span class="label">手机号码</span>
            <input v-model="createForm.phone" class="input" type="tel" placeholder="11 位手机号" maxlength="11" />
          </label>

          <label class="field">
            <span class="label">专业</span>
            <input v-model="createForm.major" class="input" placeholder="所在专业（选填）" />
          </label>

          <label class="field">
            <span class="label">入学年份</span>
            <input v-model="createForm.enrollment_year" class="input" type="number" placeholder="如 2022" min="2000" max="2100" />
          </label>

          <label class="field">
            <span class="label">初始密码</span>
            <input v-model="createForm.password" class="input" type="text" placeholder="默认 usth123456" />
          </label>

          <label class="field">
            <span class="label">角色</span>
            <select v-model="createForm.role" class="input">
              <option value="user">学生</option>
              <option value="admin">管理员</option>
            </select>
          </label>

          <label class="field span-2">
            <span class="label">简介（选填）</span>
            <textarea v-model="createForm.bio" class="textarea" rows="3"></textarea>
          </label>

          <template v-if="isAdminCreate">
            <p v-if="isSystemAdminUsername" class="form-hint span-2">
              系统管理员账号（admin）权限固定为完整（FULL），不可配置。
            </p>
            <div v-else class="span-2">
              <AdminPermissionPicker
                :level="createForm.admin_permission_level"
                :permissions="createForm.admin_permissions"
                @update:level="createForm.admin_permission_level = $event"
                @update:permissions="createForm.admin_permissions = $event"
              />
            </div>
            <label v-if="!isSystemAdminUsername" class="field">
              <span class="label">管理员权限到期时间（留空永久）</span>
              <input v-model="createForm.admin_expires_at" class="input" type="datetime-local" />
            </label>
          </template>

          <label class="field">
            <span class="label">账号状态</span>
            <select v-model="createForm.is_active" class="input">
              <option :value="true">启用</option>
              <option :value="false">禁用</option>
            </select>
          </label>

          <div class="actions span-2">
            <button class="button button--primary" :disabled="creating" type="submit">
              {{ creating ? '注册中…' : '创建账号' }}
            </button>
            <button class="button button--ghost" type="button" @click="resetCreateForm">重置表单</button>
          </div>
        </form>
      </div>

      <!-- Excel import -->
      <div v-else-if="registerSubTab === 'excel'" class="panel excel-panel">
        <div class="title-row">
          <div>
            <p class="eyebrow">批量导入</p>
            <h2 class="section-title">从 Excel 导入用户</h2>
          </div>
        </div>

        <div class="excel-hint panel">
          <p class="eyebrow">Excel 表头说明</p>
          <p>第一行为表头，支持以下列名（中英文均可，大小写不敏感）：</p>
          <table class="hint-table">
            <thead><tr><th>字段</th><th>中文别名</th><th>说明</th></tr></thead>
            <tbody>
              <tr><td>username</td><td>学号 / 用户名</td><td>必填，10 位学号</td></tr>
              <tr><td>full_name</td><td>姓名 / name</td><td>选填</td></tr>
              <tr><td>phone</td><td>手机 / 手机号</td><td>选填，11 位</td></tr>
              <tr><td>major</td><td>专业</td><td>选填</td></tr>
              <tr><td>enrollment_year</td><td>入学年份 / 入学年</td><td>选填，如 2022</td></tr>
              <tr><td>email</td><td>邮箱</td><td>选填（缺省自动生成占位邮箱）</td></tr>
              <tr><td>password</td><td>密码 / 初始密码</td><td>选填（缺省 usth123456）</td></tr>
            </tbody>
          </table>
        </div>

        <div
          class="drop-zone"
          :class="{ 'drop-zone--active': dropActive }"
          @dragover.prevent="dropActive = true"
          @dragleave="dropActive = false"
          @drop.prevent="onDrop"
        >
          <p v-if="!excelFile">拖拽 Excel 文件到此处，或</p>
          <p v-else>已选择：<strong>{{ excelFile.name }}</strong></p>
          <label class="button button--ghost file-label">
            选择文件
            <input type="file" accept=".xlsx,.xls" class="hidden-input" @change="onFileChange" />
          </label>
        </div>

        <div class="actions">
          <button
            class="button button--primary"
            :disabled="!excelFile || excelLoading"
            type="button"
            @click="submitExcelImport"
          >
            {{ excelLoading ? '导入中…' : '开始导入' }}
          </button>
          <button
            v-if="excelFile"
            class="button button--ghost"
            type="button"
            @click="() => { excelFile = null; excelResult = null }"
          >
            清除
          </button>
        </div>

        <!-- Import result -->
        <div v-if="excelResult" class="import-result panel">
          <p class="feedback feedback--success">导入成功：{{ excelResult.success_count }} 条</p>
          <div v-if="excelResult.failed.length > 0">
            <p class="feedback feedback--error">失败 {{ excelResult.failed.length }} 条：</p>
            <table class="data-table data-table--sm">
              <thead><tr><th>行号</th><th>失败原因</th></tr></thead>
              <tbody>
                <tr v-for="f in excelResult.failed" :key="f.row">
                  <td>{{ f.row }}</td>
                  <td>{{ f.reason }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-users-page {
  width: min(1440px, 100%);
  margin: 0 auto;
  display: grid;
  gap: 1rem;
}

.page-header {
  margin-bottom: 0.5rem;
}

.section-title {
  margin: 0;
  font-family: var(--font-display);
  color: var(--heading);
  font-size: clamp(1.2rem, 2vw, 1.55rem);
}

/* Tabs */
.tab-bar,
.sub-tab-bar {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.tab-btn {
  padding: 0.55rem 1.1rem;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.tab-btn:hover,
.tab-btn--active {
  border-color: rgba(var(--accent-1-rgb), 0.35);
  background: rgba(var(--accent-1-rgb), 0.08);
  color: var(--nav-active-text);
}

.tab-btn--sm {
  padding: 0.4rem 0.85rem;
  font-size: 0.88rem;
}

.tab-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.4rem;
  height: 1.4rem;
  padding: 0 0.3rem;
  border-radius: 999px;
  background: rgba(var(--accent-1-rgb), 0.15);
  color: var(--primary);
  font-size: 0.75rem;
  font-weight: 600;
}

.tab-content {
  display: grid;
  gap: 1rem;
}

/* Search bar */
.search-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: flex-end;
}

.field--inline {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
}

.field--inline .label {
  white-space: nowrap;
  font-size: 0.85rem;
}

/* Bulk bar */
.bulk-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
  padding: 0.65rem 1rem;
  background: rgba(var(--accent-1-rgb), 0.06);
  border-color: rgba(var(--accent-1-rgb), 0.25);
}

.bulk-count {
  font-weight: 500;
  color: var(--primary);
}

.bulk-panel {
  display: grid;
  gap: 0.75rem;
  max-width: 480px;
}

/* Table */
.table-panel {
  overflow: hidden;
  padding: 0;
}

.table-panel:has(.data-row--editing) {
  overflow: visible;
}

.table-scroll {
  overflow-x: auto;
}

.table-scroll:has(.data-row--editing) {
  overflow-y: visible;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.data-table th {
  padding: 0.7rem 0.75rem;
  text-align: left;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--label-text);
  background: var(--surface);
  border-bottom: 1px solid var(--table-row-border);
  white-space: nowrap;
}

.data-table td {
  padding: 0.65rem 0.75rem;
  border-bottom: 1px solid var(--table-row-border);
  vertical-align: middle;
}

.data-table--sm td,
.data-table--sm th {
  padding: 0.4rem 0.6rem;
  font-size: 0.82rem;
}

.data-row:hover td {
  background: rgba(var(--accent-1-rgb), 0.04);
}

.data-row--clickable {
  cursor: pointer;
}

.data-row--editing td {
  background: rgba(var(--accent-1-rgb), 0.07);
}

.col-check {
  width: 2.5rem;
  text-align: center;
}

.mono {
  font-family: var(--font-mono, monospace);
  font-size: 0.82rem;
}

.text-ellipsis {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty-row {
  text-align: center;
  padding: 2rem;
  color: var(--text-muted);
}

.row-actions {
  display: flex;
  gap: 0.25rem;
}

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.2rem 0.3rem;
  border-radius: 6px;
  font-size: 1rem;
  transition: background 0.15s;
}

.btn-icon:hover {
  background: rgba(var(--accent-1-rgb), 0.1);
}

.btn-icon--danger:hover {
  background: rgba(239, 68, 68, 0.1);
}

/* Register form */
.register-form {
  max-width: 900px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.span-2 {
  grid-column: 1 / -1;
}

.actions {
  display: flex;
  gap: 0.75rem;
}

.required {
  color: #ef4444;
}

/* Inputs sizing */
.input--sm {
  max-width: 160px;
}

.input--xs {
  max-width: 120px;
  padding: 0.3rem 0.5rem;
  font-size: 0.82rem;
}

/* Excel panel */
.excel-panel {
  max-width: 860px;
  display: grid;
  gap: 1rem;
}

.excel-hint {
  font-size: 0.88rem;
}

.hint-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 0.5rem;
  font-size: 0.82rem;
}

.hint-table th,
.hint-table td {
  padding: 0.4rem 0.65rem;
  border: 1px solid var(--table-row-border);
  text-align: left;
}

.hint-table th {
  background: var(--surface);
  font-weight: 600;
}

.drop-zone {
  display: grid;
  place-items: center;
  gap: 0.75rem;
  padding: 2rem;
  border: 2px dashed var(--border);
  border-radius: var(--radius-xl);
  text-align: center;
  color: var(--text-muted);
  transition: border-color 0.2s, background 0.2s;
}

.drop-zone--active {
  border-color: var(--primary);
  background: rgba(var(--accent-1-rgb), 0.06);
}

.file-label {
  cursor: pointer;
}

.hidden-input {
  display: none;
}

.import-result {
  display: grid;
  gap: 0.75rem;
}

/* Chips */
.chip--admin {
  background: rgba(var(--accent-1-rgb), 0.15);
  color: var(--primary);
  border: 1px solid rgba(var(--accent-1-rgb), 0.3);
}

.chip--locked {
  margin-left: 0.35rem;
  background: rgba(148, 163, 184, 0.15);
  color: #94a3b8;
  border: 1px solid rgba(148, 163, 184, 0.35);
  font-size: 0.7rem;
}

.form-hint {
  margin: 0;
  color: var(--muted);
  font-size: 0.9rem;
}

.col-role-edit {
  min-width: 10.5rem;
  vertical-align: top;
  overflow: visible;
}

.role-edit-label {
  margin: 0 0 0.35rem;
  font-weight: 600;
  font-size: 0.82rem;
  color: var(--heading);
}

.role-edit-hint {
  margin: 0;
  font-size: 0.75rem;
  color: var(--text-muted);
}

.role-edit-perms {
  position: relative;
  margin-top: 0.25rem;
}

.chip--user {
  background: rgba(52, 211, 153, 0.12);
  color: #34d399;
  border: 1px solid rgba(52, 211, 153, 0.3);
}

/* Transition */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

@media (max-width: 768px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
  .span-2 {
    grid-column: 1;
  }
}
</style>
