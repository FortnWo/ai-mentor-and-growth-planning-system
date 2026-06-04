<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { changeMyPassword, getMyInfo, updateMyInfo } from '../api/info'
import type { UserRead } from '../api/user'
import { authState, isFullAdmin, refreshCurrentUser } from '../stores/auth'
import { getApiErrorMessage } from '../utils/apiError'

type StudentFormState = {
  phone: string
  email: string
  bio: string
  address: string
}

type AdminFormState = {
  phone: string
  email: string
}

type PasswordFormState = {
  current_password: string
  new_password: string
  confirm_password: string
}

const userInfo = ref<UserRead | null>(null)
const feedback = ref<string>('')
const errorMsg = ref<string>('')
const submitting = ref<boolean>(false)
const showPasswordForm = ref<boolean>(false)

const admin = computed(() => isFullAdmin(authState.user))

const studentForm = reactive<StudentFormState>({
  phone: '',
  email: '',
  bio: '',
  address: '',
})

const adminForm = reactive<AdminFormState>({
  phone: '',
  email: '',
})

const passwordForm = reactive<PasswordFormState>({
  current_password: '',
  new_password: '',
  confirm_password: '',
})

function clearMessages() {
  feedback.value = ''
  errorMsg.value = ''
}

function syncFormFromInfo(user: UserRead) {
  studentForm.phone = user.phone ?? ''
  studentForm.email = user.email ?? ''
  studentForm.bio = user.bio ?? ''
  studentForm.address = user.address ?? ''

  adminForm.phone = user.phone ?? ''
  adminForm.email = user.email ?? ''
}

async function loadMyInfo() {
  clearMessages()
  try {
    submitting.value = true
    const data = await getMyInfo()
    userInfo.value = data
    syncFormFromInfo(data)
  } catch {
    errorMsg.value = '无法加载资料，请刷新重试。'
  } finally {
    submitting.value = false
  }
}

async function saveStudentInfo() {
  clearMessages()
  try {
    submitting.value = true
    const updated = await updateMyInfo({
      phone: studentForm.phone.trim() || undefined,
      email: studentForm.email.trim() || undefined,
      bio: studentForm.bio.trim() || undefined,
      address: studentForm.address.trim() || undefined,
    })
    userInfo.value = updated
    syncFormFromInfo(updated)
    feedback.value = '资料更新成功。'
  } catch (err) {
    errorMsg.value = getApiErrorMessage(err, '资料更新失败，请检查输入内容。')
  } finally {
    submitting.value = false
  }
}

async function saveAdminInfo() {
  clearMessages()
  try {
    submitting.value = true
    const updated = await updateMyInfo({
      phone: adminForm.phone.trim() || undefined,
      email: adminForm.email.trim() || undefined,
    })
    userInfo.value = updated
    syncFormFromInfo(updated)
    feedback.value = '资料更新成功。'
  } catch (err) {
    errorMsg.value = getApiErrorMessage(err, '资料更新失败，请检查输入内容。')
  } finally {
    submitting.value = false
  }
}

async function updatePassword() {
  clearMessages()

  if (!passwordForm.current_password.trim() || !passwordForm.new_password.trim()) {
    errorMsg.value = '请输入当前密码和新密码。'
    return
  }

  if (passwordForm.new_password !== passwordForm.confirm_password) {
    errorMsg.value = '两次输入的新密码不一致。'
    return
  }

  if (passwordForm.new_password.length < 8) {
    errorMsg.value = '新密码不能少于 8 位。'
    return
  }

  try {
    submitting.value = true
    const updated = await changeMyPassword({
      current_password: passwordForm.current_password,
      new_password: passwordForm.new_password,
    })
    userInfo.value = updated
    passwordForm.current_password = ''
    passwordForm.new_password = ''
    passwordForm.confirm_password = ''
    showPasswordForm.value = false
    feedback.value = '密码修改成功。'
  } catch (err) {
    errorMsg.value = getApiErrorMessage(err, '密码修改失败，请检查当前密码是否正确。')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  if (!authState.user) {
    await refreshCurrentUser()
  }
  await loadMyInfo()
})
</script>

<template>
  <div class="page page--wide info-page">
    <div class="page-header reveal">
      <p class="page-kicker">{{ admin ? '管理员工作区' : '个人工作区' }}</p>
      <h1 class="page-title">{{ admin ? '管理员资料' : '我的资料' }}</h1>
      <p class="page-subtitle">
        {{ admin ? '管理系统账号与联系信息。' : '查看账号信息，编辑联系方式与个人简介。' }}
      </p>
    </div>

    <p v-if="errorMsg" class="feedback feedback--error">{{ errorMsg }}</p>
    <p v-if="feedback" class="feedback feedback--success">{{ feedback }}</p>

    <div v-if="userInfo" class="info-layout">
      <!-- ── 只读账号信息 ── -->
      <section class="panel info-readonly reveal reveal--delay-1">
        <div class="title-row">
          <div>
            <p class="eyebrow">账号概览</p>
            <h2 class="section-title">身份信息</h2>
          </div>
          <span class="chip" :class="userInfo.is_active ? 'chip--active' : 'chip--warn'">
            {{ userInfo.is_active ? '启用' : '禁用' }}
          </span>
        </div>

        <dl class="summary-list">
          <div class="summary-row">
            <dt>用户名{{ admin ? '' : '（学号）' }}</dt>
            <dd>{{ userInfo.username }}</dd>
          </div>
          <div class="summary-row">
            <dt>角色</dt>
            <dd>
              <span class="chip" :class="admin ? 'chip--admin' : 'chip--user'">
                {{ admin ? '管理员' : '学生' }}
              </span>
            </dd>
          </div>
          <div class="summary-row">
            <dt>姓名</dt>
            <dd>{{ userInfo.full_name || '—' }}</dd>
          </div>

          <!-- 普通用户专有只读字段 -->
          <template v-if="!admin">
            <div class="summary-row">
              <dt>专业</dt>
              <dd>{{ userInfo.major || '—' }}</dd>
            </div>
            <div class="summary-row">
              <dt>年级</dt>
              <dd>{{ userInfo.computed_year_of_study ? `大${userInfo.computed_year_of_study}` : '—' }}</dd>
            </div>
          </template>

          <div v-if="userInfo.last_login_at" class="summary-row">
            <dt>上次登录</dt>
            <dd>{{ new Date(userInfo.last_login_at).toLocaleString() }}</dd>
          </div>
          <div class="summary-row">
            <dt>注册时间</dt>
            <dd>{{ new Date(userInfo.created_at).toLocaleDateString() }}</dd>
          </div>
        </dl>

        <!-- 修改密码触发按钮 -->
        <div class="readonly-actions">
          <button
            class="button button--ghost"
            type="button"
            @click="showPasswordForm = !showPasswordForm"
          >
            {{ showPasswordForm ? '取消修改密码' : '修改密码' }}
          </button>
        </div>
      </section>

      <!-- ── 普通用户可编辑表单 ── -->
      <form v-if="!admin" class="panel form-card reveal reveal--delay-2" @submit.prevent="saveStudentInfo">
        <div class="title-row">
          <div>
            <p class="eyebrow">联系信息</p>
            <h2 class="section-title">编辑联系方式</h2>
          </div>
        </div>

        <label class="field">
          <span class="label">手机号码</span>
          <input v-model="studentForm.phone" class="input" type="tel" placeholder="11 位手机号码" maxlength="11" />
        </label>

        <label class="field">
          <span class="label">邮箱</span>
          <input v-model="studentForm.email" class="input" type="email" placeholder="电子邮箱地址" />
        </label>

        <label class="field span-2">
          <span class="label">地址</span>
          <input v-model="studentForm.address" class="input" placeholder="联系地址（选填）" />
        </label>

        <label class="field span-2">
          <span class="label">个人简介</span>
          <textarea v-model="studentForm.bio" class="textarea" rows="4" placeholder="简单介绍自己（选填）"></textarea>
        </label>

        <div class="actions span-2">
          <button class="button button--primary" :disabled="submitting" type="submit">保存</button>
        </div>
      </form>

      <!-- ── 管理员可编辑表单 ── -->
      <form v-else class="panel form-card reveal reveal--delay-2" @submit.prevent="saveAdminInfo">
        <div class="title-row">
          <div>
            <p class="eyebrow">联系信息</p>
            <h2 class="section-title">编辑联系方式</h2>
          </div>
        </div>

        <label class="field">
          <span class="label">邮箱</span>
          <input v-model="adminForm.email" class="input" type="email" placeholder="管理员邮箱" />
        </label>

        <label class="field">
          <span class="label">手机号码</span>
          <input v-model="adminForm.phone" class="input" type="tel" placeholder="11 位手机号码" maxlength="11" />
        </label>

        <div class="actions span-2">
          <button class="button button--primary" :disabled="submitting" type="submit">保存</button>
        </div>
      </form>

      <!-- ── 修改密码面板（通用） ── -->
      <transition name="fade-slide">
        <form
          v-if="showPasswordForm"
          class="panel form-card password-card reveal span-full"
          @submit.prevent="updatePassword"
        >
          <div class="title-row">
            <div>
              <p class="eyebrow">安全</p>
              <h2 class="section-title">修改密码</h2>
            </div>
          </div>

          <label class="field">
            <span class="label">当前密码</span>
            <input v-model="passwordForm.current_password" class="input" type="password" autocomplete="current-password" />
          </label>

          <label class="field">
            <span class="label">新密码</span>
            <input v-model="passwordForm.new_password" class="input" type="password" autocomplete="new-password" />
          </label>

          <label class="field">
            <span class="label">确认新密码</span>
            <input v-model="passwordForm.confirm_password" class="input" type="password" autocomplete="new-password" />
          </label>

          <div class="actions span-2">
            <button class="button button--primary" :disabled="submitting" type="submit">确认修改</button>
            <button class="button button--ghost" type="button" @click="showPasswordForm = false">取消</button>
          </div>
        </form>
      </transition>
    </div>

    <div v-else-if="!submitting" class="panel reveal">
      <p class="feedback feedback--error">无法加载资料，请刷新页面重试。</p>
    </div>
  </div>
</template>

<style scoped>
.info-page {
  width: min(1180px, 100%);
  margin: 0 auto;
}

.page-header {
  margin-bottom: 2rem;
}

.info-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.6fr);
  gap: 1.5rem;
  align-items: start;
}

.span-full {
  grid-column: 1 / -1;
}

.info-readonly,
.form-card {
  display: grid;
  gap: 1rem;
}

.summary-list {
  display: grid;
  gap: 0;
  margin: 0;
}

.summary-row {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.85rem 0;
  border-bottom: 1px solid var(--table-row-border);
}

.summary-row dt {
  color: var(--label-text);
  font-weight: 500;
}

.summary-row dd {
  margin: 0;
  text-align: right;
  color: var(--heading);
}

.readonly-actions {
  display: flex;
  gap: 0.75rem;
  padding-top: 0.5rem;
}

.form-card {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-content: start;
}

.password-card {
  grid-template-columns: repeat(2, minmax(0, 1fr));
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

.chip--admin {
  background: rgba(var(--accent-1-rgb), 0.15);
  color: var(--primary);
  border: 1px solid rgba(var(--accent-1-rgb), 0.3);
}

.chip--user {
  background: rgba(52, 211, 153, 0.12);
  color: #34d399;
  border: 1px solid rgba(52, 211, 153, 0.3);
}

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

@media (max-width: 900px) {
  .info-layout {
    grid-template-columns: 1fr;
  }

  .form-card,
  .password-card {
    grid-template-columns: 1fr;
  }
}
</style>
