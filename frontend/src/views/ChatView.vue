<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { listMessages, listSessions, sendMessage } from '../api/chat'
import type { ChatMessageRead, ChatSessionRead } from '../api/chat'
import { authState, refreshCurrentUser } from '../stores/auth'

const sessions = ref<ChatSessionRead[]>([])
const selectedSessionId = ref<number | null>(null)
const messages = ref<ChatMessageRead[]>([])
const input = ref<string>('')
const newSessionTitle = ref<string>('')
const loading = ref<boolean>(false)
const error = ref<string>('')

const activeSession = computed(
  () => sessions.value.find((session) => session.id === selectedSessionId.value) ?? null,
)
const sessionCount = computed(() => sessions.value.length)
const messageCount = computed(() => messages.value.length)

function clearError() {
  error.value = ''
}

function currentUserId(): number | null {
  return authState.user?.id ?? null
}

async function refreshSessions() {
  const userId = currentUserId()
  if (!userId) {
    error.value = 'Please login first.'
    return
  }

  loading.value = true
  clearError()
  try {
    sessions.value = await listSessions(userId)

    if (!sessions.value.length) {
      selectedSessionId.value = null
      messages.value = []
      return
    }

    if (!selectedSessionId.value) {
      selectedSessionId.value = sessions.value[0].id
    }

    await loadMessages(selectedSessionId.value)
  } catch {
    error.value = 'Could not load sessions for current user.'
  } finally {
    loading.value = false
  }
}

async function loadMessages(sessionId: number) {
  const userId = currentUserId()
  if (!userId) {
    error.value = 'Please login first.'
    return
  }

  loading.value = true
  clearError()
  try {
    messages.value = await listMessages(sessionId, userId)
    selectedSessionId.value = sessionId
  } catch {
    error.value = 'Could not load messages for this session.'
  } finally {
    loading.value = false
  }
}

function startNewSession() {
  selectedSessionId.value = null
  messages.value = []
}

async function submitMessage() {
  const text = input.value.trim()
  if (!text) {
    return
  }

  const userId = currentUserId()
  if (!userId) {
    error.value = 'Please login first.'
    return
  }

  clearError()
  loading.value = true
  try {
    const response = await sendMessage({
      user_id: userId,
      session_id: selectedSessionId.value ?? undefined,
      title: newSessionTitle.value.trim() || undefined,
      message: text,
    })

    input.value = ''
    selectedSessionId.value = response.session.id
    await refreshSessions()
    await loadMessages(response.session.id)
  } catch {
    error.value = 'Could not send message.'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (!authState.user) {
    await refreshCurrentUser()
  }
  await refreshSessions()
})
</script>

<template>
  <div class="page page--wide chat-page">
    <section class="page-header glass-card panel">
      <div class="title-row">
        <div>
          <p class="page-kicker">AI mentor chat</p>
          <h1 class="page-title">Conversational guidance, designed like a studio tool.</h1>
          <p class="page-subtitle">
            Keep sessions organized, review history, and send messages in a calm, high-contrast workspace.
          </p>
        </div>

        <div class="hero-actions">
          <button class="button button--primary" :disabled="loading" type="button" @click="refreshSessions">
            Refresh Sessions
          </button>
          <button class="button button--ghost" :disabled="loading" type="button" @click="startNewSession">
            New Chat
          </button>
        </div>
      </div>

      <div class="stat-grid">
        <article class="stat-card">
          <p class="stat-label">Sessions</p>
          <p class="stat-value">{{ sessionCount }}</p>
          <p class="stat-note">Saved conversation threads</p>
        </article>

        <article class="stat-card">
          <p class="stat-label">Messages</p>
          <p class="stat-value">{{ messageCount }}</p>
          <p class="stat-note">Visible in the current thread</p>
        </article>

        <article class="stat-card">
          <p class="stat-label">Active session</p>
          <p class="stat-value">{{ activeSession?.title || `Session #${activeSession?.id ?? '-'}` }}</p>
          <p class="stat-note">
            {{ activeSession ? new Date(activeSession.created_at).toLocaleString() : 'Start a new conversation' }}
          </p>
        </article>
      </div>
    </section>

    <p v-if="error" class="feedback feedback--error">{{ error }}</p>

    <section class="grid-2 chat-layout">
      <aside class="panel sessions-panel">
        <div class="title-row">
          <div>
            <p class="eyebrow">Sessions</p>
            <h2 class="section-title">Conversation history</h2>
          </div>

          <span class="chip chip--neutral">{{ sessionCount }} total</span>
        </div>

        <div class="field">
          <label class="label" for="session-title">New Session Title (optional)</label>
          <input
            id="session-title"
            v-model="newSessionTitle"
            class="input"
            placeholder="e.g. Midterm recovery plan"
          />
        </div>

        <div class="button-row">
          <button class="button button--ghost" :disabled="loading" type="button" @click="refreshSessions">
            Refresh
          </button>
          <button class="button button--primary" :disabled="loading" type="button" @click="startNewSession">
            New Chat
          </button>
        </div>

        <div class="session-list">
          <button
            v-for="session in sessions"
            :key="session.id"
            :class="['session-card', { active: session.id === selectedSessionId }]"
            type="button"
            @click="loadMessages(session.id)"
          >
            <strong>{{ session.title || `Session #${session.id}` }}</strong>
            <small>{{ new Date(session.created_at).toLocaleString() }}</small>
          </button>
        </div>

        <p v-if="!sessions.length" class="empty-state">No sessions yet. Send your first message.</p>
      </aside>

      <section class="panel chat-panel">
        <div class="title-row">
          <div>
            <p class="eyebrow">Chat canvas</p>
            <h2 class="section-title">{{ activeSession?.title || 'Untitled session' }}</h2>
          </div>

          <span class="chip chip--active">{{ messageCount }} messages</span>
        </div>

        <div class="divider"></div>

        <div class="messages">
          <div
            v-for="message in messages"
            :key="message.id"
            :class="[
              'message-bubble',
              message.role === 'user' ? 'message-bubble--user' : 'message-bubble--assistant',
            ]"
          >
            <strong>{{ message.role === 'user' ? 'You' : 'AI Mentor' }}</strong>
            <p>{{ message.content }}</p>
          </div>

          <p v-if="!messages.length" class="empty-state">Start a conversation to see messages here.</p>
        </div>

        <form class="message-form" @submit.prevent="submitMessage">
          <input v-model="input" :disabled="loading" class="input" placeholder="Ask your AI mentor anything..." />
          <button class="button button--primary" :disabled="loading" type="submit">Send</button>
        </form>
      </section>
    </section>
  </div>
</template>

<style scoped>
.chat-layout {
  align-items: start;
}

.sessions-panel,
.chat-panel {
  display: grid;
  gap: 1rem;
}

.session-list,
.messages {
  display: grid;
  gap: 0.75rem;
}

.session-card {
  display: grid;
  gap: 0.3rem;
  width: 100%;
  padding: 0.95rem 1rem;
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  text-align: left;
  color: inherit;
  background: rgba(15, 23, 42, 0.48);
}

.session-card.active {
  border-color: rgba(6, 182, 212, 0.28);
  background: rgba(6, 182, 212, 0.08);
}

.session-card strong {
  color: #f8fbff;
}

.session-card small {
  color: var(--text-muted);
}

.chat-panel {
  min-height: 640px;
}

.message-form {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.75rem;
  align-items: end;
}

.section-title {
  margin: 0;
  font-family: var(--font-display);
  color: var(--heading);
  font-size: clamp(1.25rem, 2vw, 1.7rem);
  letter-spacing: -0.03em;
}

@media (max-width: 1024px) {
  .message-form {
    grid-template-columns: 1fr;
  }
}
</style>
