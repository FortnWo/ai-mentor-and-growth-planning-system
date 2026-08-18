<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { changeMyPassword, getMyProfile, updateMyProfile } from '../api/profile'
import type { UserRead } from '../api/user'
import { authState, refreshCurrentUser } from '../stores/auth'
import { parseOptionalInteger } from '../utils/number'

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

async function loadMyProfile() {
  clearMessages()

  try {
    submitting.value = true
    const data = await getMyProfile()
    profile.value = data
    syncFormFromProfile(data)
  } catch {
    error.value = '无法加载你的资料。'
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
      year_of_study: parseOptionalInteger(profileForm.year_of_study),
      bio: profileForm.bio.trim() || undefined,
    })

    profile.value = updated
    syncFormFromProfile(updated)
    feedback.value = '资料更新成功。'
  } catch {
    error.value = '资料更新失败。'
  } finally {
    submitting.value = false
  }
}

async function updatePassword() {
  clearMessages()

  if (!passwordForm.current_password.trim() || !passwordForm.new_password.trim()) {
    error.value = '请输入当前密码和新密码。'
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
    feedback.value = '密码修改成功。'
  } catch {
    error.value = '密码修改失败，请检查当前密码和密码规则。'
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
    <section class="page-header glass-card panel hero-frame reveal">
      <div class="title-row">
        <div>
          <p class="page-kicker">个人工作区</p>
          <h1 class="page-title">我的资料</h1>
          <p class="page-subtitle">
            在精致的资料工作区中整理你的学业信息、简介和账号凭据。
          </p>
        </div>
      </div>

      <div v-if="profile" class="stat-grid">
        <article class="stat-card">
          <p class="stat-label">用户名</p>
          <p class="stat-value">{{ profile.username }}</p>
          <p class="stat-note">主要登录标识</p>
        </article>

        <article class="stat-card">
          <p class="stat-label">角色</p>
          <p class="stat-value">{{ profile.role }}</p>
          <p class="stat-note">{{ profile.is_active ? '启用账号' : '禁用账号' }}</p>
        </article>

        <article class="stat-card">
          <p class="stat-label">邮箱</p>
          <p class="stat-value">{{ profile.email }}</p>
          <p class="stat-note">通知渠道</p>
        </article>

        <article class="stat-card">
          <p class="stat-label">最近登录</p>
          <p class="stat-value">{{ profile.last_login_at ? '近期' : '从未' }}</p>
          <p class="stat-note">
            {{ profile.last_login_at ? new Date(profile.last_login_at).toLocaleString() : '暂无登录记录' }}
          </p>
        </article>
      </div>
    </section>

    <p v-if="error" class="feedback feedback--error">{{ error }}</p>
    <p v-if="feedback" class="feedback feedback--success">{{ feedback }}</p>

    <div class="grid-2 profile-grid">
      <section v-if="profile" class="panel profile-summary reveal reveal--delay-1">
        <div class="title-row">
          <div>
            <p class="eyebrow">账号概览</p>
            <h2 class="section-title">身份快照</h2>
          </div>

          <span class="chip" :class="profile.is_active ? 'chip--active' : 'chip--warn'">
            {{ profile.is_active ? '启用' : '禁用' }}
          </span>
        </div>

        <div class="summary-list">
          <p><strong>用户名</strong><span>{{ profile.username }}</span></p>
          <p><strong>邮箱</strong><span>{{ profile.email }}</span></p>
          <p><strong>角色</strong><span>{{ profile.role }}</span></p>
          <p v-if="profile.last_login_at">
            <strong>上次登录</strong><span>{{ new Date(profile.last_login_at).toLocaleString() }}</span>
          </p>
        </div>
      </section>

      <form class="panel form-card reveal reveal--delay-2" @submit.prevent="saveProfile">
        <div class="title-row">
          <div>
            <p class="eyebrow">资料详情</p>
            <h2 class="section-title">编辑你的公开资料</h2>
          </div>
        </div>

        <label class="field">
          <span class="label">姓名</span>
          <input v-model="profileForm.full_name" class="input" />
        </label>

        <label class="field">
          <span class="label">专业</span>
          <input v-model="profileForm.major" class="input" />
        </label>

        <label class="field">
          <span class="label">年级</span>
          <input v-model="profileForm.year_of_study" class="input" type="number" min="1" max="12" />
        </label>

        <label class="field span-2">
          <span class="label">简介</span>
          <textarea v-model="profileForm.bio" class="textarea" rows="4"></textarea>
        </label>

        <div class="actions span-2">
          <button class="button button--primary" :disabled="submitting" type="submit">保存资料</button>
        </div>
      </form>

      <form class="panel form-card reveal reveal--delay-3" @submit.prevent="updatePassword">
        <div class="title-row">
          <div>
            <p class="eyebrow">安全</p>
            <h2 class="section-title">修改密码</h2>
          </div>
        </div>

        <label class="field">
          <span class="label">当前密码</span>
          <input v-model="passwordForm.current_password" class="input" type="password" />
        </label>

        <label class="field">
          <span class="label">新密码</span>
          <input v-model="passwordForm.new_password" class="input" type="password" />
        </label>

        <div class="actions span-2">
          <button class="button button--ghost" :disabled="submitting" type="submit">更新密码</button>
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
  color: var(--heading);
}

.summary-list span {
  text-align: right;
  color: var(--text-muted);
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
