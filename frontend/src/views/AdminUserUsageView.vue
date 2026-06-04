<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { getAiUsageLogs, type UsageDetailEntry, type UsageLogPeriod, type UsageStatEntry } from '../api/adminSystem'
import { getUser, type UserRead } from '../api/user'
import UsageStatsPanel from '../components/admin/UsageStatsPanel.vue'
import { getApiErrorMessage } from '../utils/apiError'

const route = useRoute()

const userId = computed(() => Number(route.params.userId))
const user = ref<UserRead | null>(null)
const usageStats = ref<UsageStatEntry[]>([])
const userDetail = ref<UsageDetailEntry[] | null>(null)
const logPeriod = ref<UsageLogPeriod>('week')
const loading = ref(false)
const pageLoading = ref(false)
const errorMsg = ref('')

const userSubtitle = computed(() => {
  if (!user.value) return ''
  const parts: string[] = []
  if (user.value.major) parts.push(user.value.major)
  if (user.value.enrollment_year) parts.push(`${user.value.enrollment_year} 级`)
  return parts.join(' · ')
})

const displayTitle = computed(() => {
  if (!user.value) return '加载中…'
  const name = user.value.full_name?.trim()
  return name ? `${name}（${user.value.username}）` : user.value.username
})

async function loadUser() {
  if (!Number.isFinite(userId.value) || userId.value <= 0) {
    errorMsg.value = '无效的用户 ID'
    return
  }
  pageLoading.value = true
  try {
    user.value = await getUser(userId.value)
  } catch (err) {
    errorMsg.value = getApiErrorMessage(err, '无法加载用户信息')
    user.value = null
  } finally {
    pageLoading.value = false
  }
}

async function loadUsage() {
  if (!user.value?.username) return
  loading.value = true
  errorMsg.value = ''
  try {
    const data = await getAiUsageLogs(logPeriod.value, user.value.username)
    usageStats.value = data.stats
    userDetail.value = data.user_detail ?? null
  } catch (err) {
    errorMsg.value = getApiErrorMessage(err, '无法加载使用量统计')
    usageStats.value = []
    userDetail.value = null
  } finally {
    loading.value = false
  }
}

async function initPage() {
  await loadUser()
  await loadUsage()
}

watch(logPeriod, () => {
  void loadUsage()
})

watch(userId, () => {
  void initPage()
})

onMounted(() => {
  void initPage()
})
</script>

<template>
  <div class="page page--wide admin-user-usage-page">
    <div class="page-header reveal">
      <RouterLink class="back-link" to="/admin/users">← 返回用户列表</RouterLink>
      <p class="page-kicker">用户 AI 用量</p>
      <h1 class="page-title">{{ displayTitle }}</h1>
      <p v-if="userSubtitle" class="page-subtitle">{{ userSubtitle }}</p>
    </div>

    <p v-if="errorMsg" class="feedback feedback--error">{{ errorMsg }}</p>

    <div v-if="pageLoading" class="panel">
      <p class="hint-text">加载用户信息…</p>
    </div>

    <div v-else-if="user" class="panel reveal reveal--delay-1">
      <div class="title-row">
        <div>
          <p class="eyebrow">AI 使用量</p>
          <h2 class="section-title">流量统计</h2>
        </div>
      </div>

      <UsageStatsPanel
        v-model:period="logPeriod"
        :loading="loading"
        :stats="usageStats"
        :user-detail="userDetail"
        detail-title="按模型 / 任务明细"
        @refresh="loadUsage"
      />
    </div>
  </div>
</template>

<style scoped>
.admin-user-usage-page {
  width: min(1180px, 100%);
  margin: 0 auto;
  display: grid;
  gap: 1rem;
}

.back-link {
  display: inline-block;
  margin-bottom: 0.5rem;
  font-size: 0.9rem;
  color: var(--text-muted);
  text-decoration: none;
}

.back-link:hover {
  color: var(--nav-active-text);
}

.section-title {
  margin: 0;
  font-family: var(--font-display);
  color: var(--heading);
  font-size: clamp(1.2rem, 2vw, 1.5rem);
}

.hint-text {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin: 0;
}
</style>
