<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import {
    getMyExtendedProfile,
    refreshMyExtendedProfileFromChat,
    updateMyExtendedProfile,
    type ExtendedProfile,
    type ExtendedProfileExtractionResult,
} from '../api/extendedProfile'
import { authState, refreshCurrentUser } from '../stores/auth'

type ExtendedProfileFormState = {
    interests: string
    skills: string
    goals: string
    study_habits: string
    personality: string
    preferences: string
}

const profile = ref<ExtendedProfile | null>(null)
const extracted = ref<ExtendedProfileExtractionResult | null>(null)
const feedback = ref<string>('')
const error = ref<string>('')
const loading = ref<boolean>(false)
const saving = ref<boolean>(false)
const refreshing = ref<boolean>(false)

const form = reactive<ExtendedProfileFormState>({
    interests: '',
    skills: '',
    goals: '',
    study_habits: '',
    personality: '',
    preferences: '',
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

function syncForm(nextProfile: ExtendedProfile) {
    form.interests = formatList(nextProfile.interests)
    form.skills = formatList(nextProfile.skills)
    form.goals = formatList(nextProfile.goals)
    form.study_habits = formatList(nextProfile.study_habits)
    form.personality = formatList(nextProfile.personality)
    form.preferences = formatList(nextProfile.preferences)
}

async function loadProfile() {
    clearMessages()

    try {
        loading.value = true
        const data = await getMyExtendedProfile()
        profile.value = data
        syncForm(data)
    } catch {
        error.value = '无法加载你的用户画像。'
    } finally {
        loading.value = false
    }
}

async function saveProfile() {
    clearMessages()

    try {
        saving.value = true
        const updated = await updateMyExtendedProfile({
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
    } catch {
        error.value = '无法更新用户画像。'
    } finally {
        saving.value = false
    }
}

async function refreshFromChat() {
    clearMessages()

    try {
        refreshing.value = true
        const result = await refreshMyExtendedProfileFromChat()
        profile.value = result.profile
        extracted.value = result.extracted
        syncForm(result.profile)
        feedback.value = '已根据聊天历史刷新画像。'
    } catch {
        error.value = '聊天抽取失败，请检查聊天记录后重试。'
    } finally {
        refreshing.value = false
    }
}

onMounted(async () => {
    if (!authState.user) {
        await refreshCurrentUser()
    }

    await loadProfile()
})
</script>

<template>
    <div class="page page--wide profile-page">
        <section class="page-header glass-card panel hero-frame reveal">
            <div class="title-row">
                <div>
                    <p class="page-kicker">结构化画像</p>
                    <h1 class="page-title">用户画像</h1>
                    <p class="page-subtitle">
                        维护一个关于兴趣、技能、目标和偏好的结构化画像。你可以手动编辑，也可以触发 AI 从最近聊天中抽取信息。
                    </p>
                </div>

                <div class="hero-actions">
                    <button class="button button--ghost" :disabled="refreshing || loading" type="button"
                        @click="loadProfile">
                        重新加载
                    </button>
                    <button class="button button--primary" :disabled="refreshing || loading" type="button"
                        @click="refreshFromChat">
                        从聊天刷新
                    </button>
                </div>
            </div>

            <div v-if="profile" class="stat-grid">
                <article class="stat-card">
                    <p class="stat-label">兴趣</p>
                    <p class="stat-value">{{ profile.interests.length }}</p>
                    <p class="stat-note">当前结构化条目</p>
                </article>

                <article class="stat-card">
                    <p class="stat-label">技能</p>
                    <p class="stat-value">{{ profile.skills.length }}</p>
                    <p class="stat-note">自动识别或手动整理</p>
                </article>

                <article class="stat-card">
                    <p class="stat-label">目标</p>
                    <p class="stat-value">{{ profile.goals.length }}</p>
                    <p class="stat-note">面向行动的成长目标</p>
                </article>

                <article class="stat-card">
                                        <p class="stat-label">最近抽取</p>
                                        <p class="stat-value">{{ profile.last_extracted_at ? '已更新' : '从未' }}</p>
                    <p class="stat-note">
                        {{
                            profile.last_extracted_at
                                ? new Date(profile.last_extracted_at).toLocaleString()
                                                            : '暂无自动抽取'
                        }}
                    </p>
                </article>
            </div>
        </section>

        <p v-if="error" class="feedback feedback--error">{{ error }}</p>
        <p v-if="feedback" class="feedback feedback--success">{{ feedback }}</p>

        <div class="grid-2 profile-grid">
            <form class="panel form-card reveal reveal--delay-1" @submit.prevent="saveProfile">
                <div class="title-row">
                    <div>
                        <p class="eyebrow">手动编辑</p>
                        <h2 class="section-title">编辑画像字段</h2>
                    </div>
                </div>

                <label class="field">
                    <span class="label">兴趣</span>
                    <textarea v-model="form.interests" class="textarea" rows="4"
                        placeholder="每行一项"></textarea>
                </label>

                <label class="field">
                    <span class="label">技能</span>
                    <textarea v-model="form.skills" class="textarea" rows="4"
                        placeholder="每行一项"></textarea>
                </label>

                <label class="field">
                    <span class="label">目标</span>
                    <textarea v-model="form.goals" class="textarea" rows="4" placeholder="每行一项"></textarea>
                </label>

                <label class="field">
                    <span class="label">学习习惯</span>
                    <textarea v-model="form.study_habits" class="textarea" rows="4"
                        placeholder="每行一项"></textarea>
                </label>

                <label class="field">
                    <span class="label">性格</span>
                    <textarea v-model="form.personality" class="textarea" rows="4"
                        placeholder="每行一项"></textarea>
                </label>

                <label class="field">
                    <span class="label">偏好</span>
                    <textarea v-model="form.preferences" class="textarea" rows="4"
                        placeholder="每行一项"></textarea>
                </label>

                <div class="actions span-2">
                    <button class="button button--primary" :disabled="saving || loading" type="submit">保存画像</button>
                </div>
            </form>

            <section class="panel profile-summary reveal reveal--delay-2">
                <div class="title-row">
                    <div>
                        <p class="eyebrow">抽取洞察</p>
                        <h2 class="section-title">最新抽取增量</h2>
                    </div>
                </div>

                <p class="muted">
                    点击“从聊天刷新”即可基于最近的对话历史重新抽取画像。新增条目会合并，不会删除已有内容。
                </p>

                <div v-if="extracted" class="summary-list">
                    <p>
                        <strong>兴趣</strong>
                        <span>{{ extracted.interests.join(', ') || '无' }}</span>
                    </p>
                    <p>
                        <strong>技能</strong>
                        <span>{{ extracted.skills.join(', ') || '无' }}</span>
                    </p>
                    <p>
                        <strong>目标</strong>
                        <span>{{ extracted.goals.join(', ') || '无' }}</span>
                    </p>
                    <p>
                        <strong>学习习惯</strong>
                        <span>{{ extracted.study_habits.join(', ') || '无' }}</span>
                    </p>
                    <p>
                        <strong>性格</strong>
                        <span>{{ extracted.personality.join(', ') || '无' }}</span>
                    </p>
                    <p>
                        <strong>偏好</strong>
                        <span>{{ extracted.preferences.join(', ') || '无' }}</span>
                    </p>
                </div>

                <p v-else class="muted">暂时没有抽取结果。</p>
            </section>
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
}
</style>
