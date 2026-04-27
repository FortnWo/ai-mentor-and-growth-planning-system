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
        error.value = 'Could not load your extended profile.'
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
        feedback.value = 'Extended profile updated successfully.'
    } catch {
        error.value = 'Could not update extended profile.'
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
        feedback.value = 'Profile refreshed from chat history.'
    } catch {
        error.value = 'Chat extraction failed. Please check your chat history or try again later.'
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
                    <p class="page-kicker">Structured profile</p>
                    <h1 class="page-title">Extended Profile</h1>
                    <p class="page-subtitle">
                        Maintain a structured profile of interests, skills, goals, and preferences. You can edit
                        manually and
                        trigger AI extraction from recent chats.
                    </p>
                </div>

                <div class="hero-actions">
                    <button class="button button--ghost" :disabled="refreshing || loading" type="button"
                        @click="loadProfile">
                        Reload
                    </button>
                    <button class="button button--primary" :disabled="refreshing || loading" type="button"
                        @click="refreshFromChat">
                        Refresh From Chat
                    </button>
                </div>
            </div>

            <div v-if="profile" class="stat-grid">
                <article class="stat-card">
                    <p class="stat-label">Interests</p>
                    <p class="stat-value">{{ profile.interests.length }}</p>
                    <p class="stat-note">Current structured entries</p>
                </article>

                <article class="stat-card">
                    <p class="stat-label">Skills</p>
                    <p class="stat-value">{{ profile.skills.length }}</p>
                    <p class="stat-note">Detected or manually curated</p>
                </article>

                <article class="stat-card">
                    <p class="stat-label">Goals</p>
                    <p class="stat-value">{{ profile.goals.length }}</p>
                    <p class="stat-note">Action oriented growth targets</p>
                </article>

                <article class="stat-card">
                    <p class="stat-label">Last extraction</p>
                    <p class="stat-value">{{ profile.last_extracted_at ? 'Updated' : 'Never' }}</p>
                    <p class="stat-note">
                        {{
                            profile.last_extracted_at
                                ? new Date(profile.last_extracted_at).toLocaleString()
                                : 'No automatic extraction yet'
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
                        <p class="eyebrow">Manual edit</p>
                        <h2 class="section-title">Edit profile fields</h2>
                    </div>
                </div>

                <label class="field">
                    <span class="label">Interests</span>
                    <textarea v-model="form.interests" class="textarea" rows="4"
                        placeholder="One item per line"></textarea>
                </label>

                <label class="field">
                    <span class="label">Skills</span>
                    <textarea v-model="form.skills" class="textarea" rows="4"
                        placeholder="One item per line"></textarea>
                </label>

                <label class="field">
                    <span class="label">Goals</span>
                    <textarea v-model="form.goals" class="textarea" rows="4" placeholder="One item per line"></textarea>
                </label>

                <label class="field">
                    <span class="label">Study Habits</span>
                    <textarea v-model="form.study_habits" class="textarea" rows="4"
                        placeholder="One item per line"></textarea>
                </label>

                <label class="field">
                    <span class="label">Personality</span>
                    <textarea v-model="form.personality" class="textarea" rows="4"
                        placeholder="One item per line"></textarea>
                </label>

                <label class="field">
                    <span class="label">Preferences</span>
                    <textarea v-model="form.preferences" class="textarea" rows="4"
                        placeholder="One item per line"></textarea>
                </label>

                <div class="actions span-2">
                    <button class="button button--primary" :disabled="saving || loading" type="submit">Save
                        Profile</button>
                </div>
            </form>

            <section class="panel profile-summary reveal reveal--delay-2">
                <div class="title-row">
                    <div>
                        <p class="eyebrow">Extraction insight</p>
                        <h2 class="section-title">Latest extracted increment</h2>
                    </div>
                </div>

                <p class="muted">
                    Trigger “Refresh From Chat” to re-run profile extraction from your recent conversation history. New
                    items are
                    merged without removing existing entries.
                </p>

                <div v-if="extracted" class="summary-list">
                    <p>
                        <strong>Interests</strong>
                        <span>{{ extracted.interests.join(', ') || 'None' }}</span>
                    </p>
                    <p>
                        <strong>Skills</strong>
                        <span>{{ extracted.skills.join(', ') || 'None' }}</span>
                    </p>
                    <p>
                        <strong>Goals</strong>
                        <span>{{ extracted.goals.join(', ') || 'None' }}</span>
                    </p>
                    <p>
                        <strong>Study Habits</strong>
                        <span>{{ extracted.study_habits.join(', ') || 'None' }}</span>
                    </p>
                    <p>
                        <strong>Personality</strong>
                        <span>{{ extracted.personality.join(', ') || 'None' }}</span>
                    </p>
                    <p>
                        <strong>Preferences</strong>
                        <span>{{ extracted.preferences.join(', ') || 'None' }}</span>
                    </p>
                </div>

                <p v-else class="muted">No extracted increment yet.</p>
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
    color: #d8e7f7;
}

.summary-list span {
    text-align: right;
    color: #f8fbff;
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
