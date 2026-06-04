<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import {
  getMyProfile,
  getMyProfileInsights,
  TRAIT_SOURCE_LABELS,
  TRAIT_TYPE_LABELS,
  TRAIT_TYPE_ORDER,
  updateMyProfile,
  type Profile,
  type ProfileInsights,
  type UserTrait,
} from '../api/profile'
import { authState, refreshCurrentUser } from '../stores/auth'

type ProfileFormState = {
  interests: string
  skills: string
  goals: string
  study_habits: string
  personality: string
  preferences: string
}

const profile = ref<Profile | null>(null)
const insights = ref<ProfileInsights | null>(null)
const feedback = ref<string>('')
const error = ref<string>('')
const insightsError = ref<string>('')
const loading = ref<boolean>(false)
const insightsLoading = ref<boolean>(false)
const saving = ref<boolean>(false)

const formCardRef = ref<HTMLFormElement | null>(null)
const insightsPanelStyle = ref<Record<string, string>>({})

const PROFILE_GRID_STACK_MQ = '(max-width: 1024px)'

let formResizeObserver: ResizeObserver | null = null
let stackMediaQuery: MediaQueryList | null = null

function syncInsightsPanelHeight() {
  const form = formCardRef.value
  if (!form || stackMediaQuery?.matches) {
    insightsPanelStyle.value = {}
    return
  }

  insightsPanelStyle.value = { height: `${form.offsetHeight}px` }
}

async function setupInsightsHeightSync() {
  stackMediaQuery = window.matchMedia(PROFILE_GRID_STACK_MQ)
  stackMediaQuery.addEventListener('change', syncInsightsPanelHeight)

  await nextTick()

  formResizeObserver = new ResizeObserver(() => syncInsightsPanelHeight())
  if (formCardRef.value) {
    formResizeObserver.observe(formCardRef.value)
  }

  syncInsightsPanelHeight()
}

function teardownInsightsHeightSync() {
  formResizeObserver?.disconnect()
  formResizeObserver = null
  stackMediaQuery?.removeEventListener('change', syncInsightsPanelHeight)
  stackMediaQuery = null
}

const form = reactive<ProfileFormState>({
  interests: '',
  skills: '',
  goals: '',
  study_habits: '',
  personality: '',
  preferences: '',
})

const groupedTraits = computed(() => {
  const traits = insights.value?.traits ?? []
  const groups = new Map<string, UserTrait[]>()

  for (const trait of traits) {
    const list = groups.get(trait.trait_type) ?? []
    list.push(trait)
    groups.set(trait.trait_type, list)
  }

  return TRAIT_TYPE_ORDER.filter((type) => groups.has(type)).map((type) => ({
    type,
    label: TRAIT_TYPE_LABELS[type] ?? type,
    items: groups.get(type) ?? [],
  }))
})

const lastExtractedLabel = computed(() => {
  const value = insights.value?.last_extracted_at
  return value ? new Date(value).toLocaleString() : '从未'
})

function clearMessages() {
  feedback.value = ''
  error.value = ''
}

function formatList(values: string[]): string {
  return values.join('\n')
}

function parseList(text: string): string[] {
  const parts = text
    .split(/[\n,;，；]+/)
    .map((part) => part.trim())
    .filter((part) => part.length > 0)

  return Array.from(new Set(parts))
}

function syncForm(nextProfile: Profile) {
  form.interests = formatList(nextProfile.interests)
  form.skills = formatList(nextProfile.skills)
  form.goals = formatList(nextProfile.goals)
  form.study_habits = formatList(nextProfile.study_habits)
  form.personality = formatList(nextProfile.personality)
  form.preferences = formatList(nextProfile.preferences)
}

function formatTraitTime(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

function formatConfidence(value: number | null): string {
  if (value === null || Number.isNaN(value)) return '—'
  return `${Math.round(value * 100)}%`
}

function sourceLabel(source: string): string {
  return TRAIT_SOURCE_LABELS[source] ?? source
}

async function loadInsights() {
  insightsError.value = ''

  try {
    insightsLoading.value = true
    insights.value = await getMyProfileInsights()
  } catch {
    insightsError.value = '无法加载特质洞察。'
  } finally {
    insightsLoading.value = false
  }
}

async function loadProfile() {
  clearMessages()

  try {
    loading.value = true
    const data = await getMyProfile()
    profile.value = data
    syncForm(data)
    await loadInsights()
  } catch {
    error.value = '无法加载你的用户画像。'
  } finally {
    loading.value = false
    await nextTick()
    syncInsightsPanelHeight()
  }
}

async function saveProfile() {
  clearMessages()

  try {
    saving.value = true
    const updated = await updateMyProfile({
      interests: parseList(form.interests),
      skills: parseList(form.skills),
      goals: parseList(form.goals),
      study_habits: parseList(form.study_habits),
      personality: parseList(form.personality),
      preferences: parseList(form.preferences),
    })

    profile.value = updated
    syncForm(updated)
    feedback.value = '用户画像更新成功。'
    await loadInsights()
  } catch {
    error.value = '无法更新用户画像。'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  if (!authState.user) {
    await refreshCurrentUser()
  }

  await loadProfile()
  await setupInsightsHeightSync()
})

onBeforeUnmount(() => {
  teardownInsightsHeightSync()
})
</script>

<template>
  <div class="page page--wide profile-page">
    <p v-if="error" class="feedback feedback--error">{{ error }}</p>
    <p v-if="feedback" class="feedback feedback--success">{{ feedback }}</p>

    <div class="grid-2 profile-grid">
      <form
        ref="formCardRef"
        class="panel form-card reveal reveal--delay-1"
        @submit.prevent="saveProfile"
      >
        <div class="title-row">
          <div>
            <p class="eyebrow">手动编辑</p>
            <h2 class="section-title">编辑画像字段</h2>
          </div>

          <div class="hero-actions">
            <button class="button button--ghost" :disabled="loading || saving" type="button" @click="loadProfile">
              重新加载
            </button>
          </div>
        </div>

        <p class="muted form-hint">与 AI 导师对话后，画像会通过工作流自动同步；也可在此手动补充并保存。</p>

        <label class="field">
          <span class="label">兴趣</span>
          <textarea v-model="form.interests" class="textarea" rows="4" placeholder="每行一项"></textarea>
        </label>

        <label class="field">
          <span class="label">技能</span>
          <textarea v-model="form.skills" class="textarea" rows="4" placeholder="每行一项"></textarea>
        </label>

        <label class="field">
          <span class="label">目标</span>
          <textarea v-model="form.goals" class="textarea" rows="4" placeholder="每行一项"></textarea>
        </label>

        <label class="field">
          <span class="label">学习习惯</span>
          <textarea v-model="form.study_habits" class="textarea" rows="4" placeholder="每行一项"></textarea>
        </label>

        <label class="field">
          <span class="label">性格</span>
          <textarea v-model="form.personality" class="textarea" rows="4" placeholder="每行一项"></textarea>
        </label>

        <label class="field">
          <span class="label">偏好</span>
          <textarea v-model="form.preferences" class="textarea" rows="4" placeholder="每行一项"></textarea>
        </label>

        <div class="actions span-2">
          <button class="button button--primary" :disabled="saving || loading" type="submit">保存画像</button>
        </div>
      </form>

      <section
        class="panel profile-insights reveal reveal--delay-2"
        :style="insightsPanelStyle"
      >
        <div class="title-row">
          <div>
            <p class="eyebrow">特质洞察</p>
            <h2 class="section-title">画像概要</h2>
          </div>
        </div>

        <div class="profile-insights-scroll">
          <p v-if="insightsError" class="feedback feedback--error">{{ insightsError }}</p>
          <p v-else-if="insightsLoading" class="muted">正在加载洞察…</p>

          <template v-else>
            <p v-if="insights?.portrait_summary" class="portrait-summary">{{ insights.portrait_summary }}</p>
            <p v-else class="muted">
              与 AI 导师对话或编辑左侧字段后，特质将自动更新。
            </p>

            <div v-if="groupedTraits.length" class="trait-groups">
              <div v-for="group in groupedTraits" :key="group.type" class="trait-group">
                <h3 class="trait-group-title">{{ group.label }}</h3>
                <ul class="trait-list">
                  <li v-for="trait in group.items" :key="`${trait.trait_type}-${trait.trait_key}`" class="trait-item">
                    <span class="trait-key">{{ trait.trait_key }}</span>
                    <span class="trait-meta">
                      <span class="trait-badge">{{ sourceLabel(trait.source) }}</span>
                      <span>置信 {{ formatConfidence(trait.confidence) }}</span>
                      <span>{{ formatTraitTime(trait.last_observed_at) }}</span>
                    </span>
                  </li>
                </ul>
              </div>
            </div>

            <p v-else-if="insights?.portrait_summary" class="muted">暂无结构化特质条目。</p>

            <p class="insights-footer muted">最近自动抽取：{{ lastExtractedLabel }}</p>
          </template>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.profile-page {
  width: min(1180px, 100%);
  margin: 0 auto;
}

.profile-grid {
  align-items: start;
}

.profile-insights {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.profile-insights .title-row {
  flex-shrink: 0;
}

.profile-insights-scroll {
  flex: 1;
  min-height: 0;
  display: grid;
  gap: 1rem;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 0.35rem;
}

.form-card {
  display: grid;
  gap: 1rem;
}

.form-hint {
  grid-column: 1 / -1;
}

.portrait-summary {
  margin: 0;
  line-height: 1.65;
  color: var(--heading);
}

.trait-groups {
  display: grid;
  gap: 1.25rem;
}

.trait-group-title {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
  color: var(--label-text);
  font-weight: 600;
}

.trait-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.5rem;
}

.trait-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.45rem;
  padding: 0.75rem 0.85rem;
  border: 1px solid var(--table-row-border);
  border-radius: 0.5rem;
}

.trait-key {
  width: 100%;
  color: var(--heading);
  font-weight: 500;
  line-height: 1.45;
}

.trait-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 0.75rem;
  width: 100%;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.trait-badge {
  display: inline-block;
  padding: 0.15rem 0.45rem;
  border-radius: 999px;
  background: var(--surface-muted, rgba(0, 0, 0, 0.06));
  color: var(--label-text);
  font-size: 0.8rem;
}

.insights-footer {
  margin-top: 0.25rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--table-row-border);
}

.muted {
  margin: 0;
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

  .profile-insights {
    max-height: min(70vh, 720px);
  }
}
</style>
