import { computed, onMounted, ref } from 'vue'

import { listActionPlans } from '../api/actionPlans'
import { listSessions } from '../api/chat'
import { listGoals } from '../api/goals'
import { getGrowthStats, listGrowthRecords } from '../api/growthRecords'
import { getMyInfo } from '../api/info'
import { getMyProfile } from '../api/profile'
import type { WorkspaceModuleId } from '../constants/workspaceModules'
import { authState, refreshCurrentUser } from '../stores/auth'
import { formatLocalDate } from '../utils/localDate'

export interface ModuleMetric {
  label: string
  value: string
}

export interface ModuleDashboardSlice {
  loading: boolean
  error: boolean
  metrics: ModuleMetric[]
}

function weeklyRange() {
  const end = new Date()
  const start = new Date(end)
  start.setDate(end.getDate() - 6)
  return {
    start_date: formatLocalDate(start),
    end_date: formatLocalDate(end),
  }
}

function emptySlice(): ModuleDashboardSlice {
  return { loading: true, error: false, metrics: [] }
}

export function useHomeDashboard() {
  const loading = ref(true)
  const chat = ref<ModuleDashboardSlice>(emptySlice())
  const profile = ref<ModuleDashboardSlice>(emptySlice())
  const plan = ref<ModuleDashboardSlice>(emptySlice())
  const growth = ref<ModuleDashboardSlice>(emptySlice())
  const info = ref<ModuleDashboardSlice>(emptySlice())

  const slicesById = computed<Record<WorkspaceModuleId, ModuleDashboardSlice>>(() => ({
    chat: chat.value,
    profile: profile.value,
    plan: plan.value,
    growth: growth.value,
    info: info.value,
  }))

  async function loadChat() {
    chat.value = { ...emptySlice(), loading: true }
    try {
      const sessions = await listSessions()
      const latest = sessions[0]
      chat.value = {
        loading: false,
        error: false,
        metrics: [
          { label: '会话总数', value: String(sessions.length) },
          {
            label: '最近会话',
            value: latest?.title?.trim() || (latest ? `会话 #${latest.id}` : '暂无'),
          },
        ],
      }
    } catch {
      chat.value = {
        loading: false,
        error: true,
        metrics: [
          { label: '会话总数', value: '—' },
          { label: '最近会话', value: '—' },
        ],
      }
    }
  }

  async function loadProfile() {
    profile.value = { ...emptySlice(), loading: true }
    try {
      const data = await getMyProfile()
      const extractedLabel = data.last_extracted_at
        ? new Date(data.last_extracted_at).toLocaleString()
        : '从未'
      profile.value = {
        loading: false,
        error: false,
        metrics: [
          { label: '兴趣条目', value: String(data.interests.length) },
          { label: '技能条目', value: String(data.skills.length) },
          { label: '目标条目', value: String(data.goals.length) },
          { label: '最近抽取', value: extractedLabel },
        ],
      }
    } catch {
      profile.value = {
        loading: false,
        error: true,
        metrics: [
          { label: '兴趣条目', value: '—' },
          { label: '技能条目', value: '—' },
          { label: '目标条目', value: '—' },
          { label: '最近抽取', value: '—' },
        ],
      }
    }
  }

  async function loadPlan() {
    plan.value = { ...emptySlice(), loading: true }
    try {
      const [goals, plans] = await Promise.all([listGoals(), listActionPlans()])
      plan.value = {
        loading: false,
        error: false,
        metrics: [
          { label: '目标数', value: String(goals.length) },
          { label: '行动计划', value: String(plans.length) },
        ],
      }
    } catch {
      plan.value = {
        loading: false,
        error: true,
        metrics: [
          { label: '目标数', value: '—' },
          { label: '行动计划', value: '—' },
        ],
      }
    }
  }

  async function loadGrowth() {
    growth.value = { ...emptySlice(), loading: true }
    try {
      const range = weeklyRange()
      const [stats, records] = await Promise.all([
        getGrowthStats(range),
        listGrowthRecords({ limit: 20 }),
      ])
      growth.value = {
        loading: false,
        error: false,
        metrics: [
          { label: '本周成长积分', value: String(stats.growth_score ?? 0) },
          { label: '连续活跃', value: `${stats.consecutive_days ?? 0} 天` },
          { label: '成长记录', value: String(records.length) },
        ],
      }
    } catch {
      growth.value = {
        loading: false,
        error: true,
        metrics: [
          { label: '本周成长积分', value: '—' },
          { label: '连续活跃', value: '—' },
          { label: '成长记录', value: '—' },
        ],
      }
    }
  }

  async function loadInfo() {
    info.value = { ...emptySlice(), loading: true }
    try {
      const user = await getMyInfo()
      const displayName = user.full_name?.trim() || user.username
      const loginLabel = user.last_login_at
        ? new Date(user.last_login_at).toLocaleString()
        : '从未'
      info.value = {
        loading: false,
        error: false,
        metrics: [
          { label: '显示名', value: displayName },
          { label: '角色', value: user.role },
          { label: '最近登录', value: loginLabel },
        ],
      }
    } catch {
      info.value = {
        loading: false,
        error: true,
        metrics: [
          { label: '显示名', value: '—' },
          { label: '角色', value: '—' },
          { label: '最近登录', value: '—' },
        ],
      }
    }
  }

  async function refresh() {
    loading.value = true
    await Promise.allSettled([loadChat(), loadProfile(), loadPlan(), loadGrowth(), loadInfo()])
    loading.value = false
  }

  onMounted(async () => {
    if (!authState.user) {
      await refreshCurrentUser()
    }
    await refresh()
  })

  return {
    loading,
    slicesById,
    refresh,
  }
}
