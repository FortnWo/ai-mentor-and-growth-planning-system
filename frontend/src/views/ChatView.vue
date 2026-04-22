<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import CompactActionMenu from '../components/CompactActionMenu.vue'
import { deleteSession, listMessages, listSessions, renameSession, sendMessage } from '../api/chat'
import type { ChatMessageRead, ChatSessionRead } from '../api/chat'
import { authState, refreshCurrentUser } from '../stores/auth'

const sessions = ref<ChatSessionRead[]>([])
const selectedSessionId = ref<number | null>(null)
const messages = ref<ChatMessageRead[]>([])
const input = ref<string>('')
const newSessionTitle = ref<string>('')
const loading = ref<boolean>(false)
const renamingSessionId = ref<number | null>(null)
const renameDraftTitle = ref<string>('')
const deletingSessionId = ref<number | null>(null)
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

function getSessionBusyState(sessionId: number) {
  return loading.value || renamingSessionId.value === sessionId || deletingSessionId.value === sessionId
}

function getSessionActionItems(session: ChatSessionRead) {
  const disabled = getSessionBusyState(session.id)

  return [
    {
      key: 'rename',
      label: 'Rename',
      disabled,
    },
    {
      key: 'delete',
      label: 'Delete',
      tone: 'danger' as const,
      disabled,
    },
  ]
}

function beginRenameSession(session: ChatSessionRead) {
  clearError()
  renamingSessionId.value = session.id
  renameDraftTitle.value = session.title ?? ''
}

function cancelRenameSession() {
  renamingSessionId.value = null
  renameDraftTitle.value = ''
}

async function saveRenameSession(session: ChatSessionRead) {
  const userId = currentUserId()
  if (!userId) {
    error.value = 'Please login first.'
    return
  }

  const trimmedTitle = renameDraftTitle.value.trim()
  if (!trimmedTitle) {
    error.value = 'Session title cannot be empty.'
    return
  }

  const currentTitle = session.title?.trim() || ''
  if (trimmedTitle === currentTitle) {
    return
  }

  clearError()
  try {
    renamingSessionId.value = session.id
    await renameSession(session.id, userId, trimmedTitle)
    await refreshSessions()
    cancelRenameSession()
  } catch {
    error.value = 'Could not rename this session.'
  } finally {
    if (renamingSessionId.value === session.id) {
      renamingSessionId.value = null
    }
  }
}

function handleSessionAction(session: ChatSessionRead, action: string) {
  if (action === 'rename') {
    beginRenameSession(session)
    return
  }

  if (action === 'delete') {
    void deleteCurrentSession(session.id)
  }
}

async function deleteCurrentSession(sessionId: number) {
  const userId = currentUserId()
  if (!userId) {
    error.value = 'Please login first.'
    return
  }

  const session = sessions.value.find((item) => item.id === sessionId)
  if (!session) {
    error.value = 'Session not found.'
    return
  }

  const confirmed = window.confirm(`Delete session ${session.title || `#${session.id}`}?`)
  if (!confirmed) {
    return
  }

  clearError()
  try {
    deletingSessionId.value = sessionId
    await deleteSession(sessionId, userId)

    if (selectedSessionId.value === sessionId) {
      selectedSessionId.value = null
      messages.value = []
    }

    await refreshSessions()
  } catch {
    error.value = 'Could not delete this session.'
  } finally {
    deletingSessionId.value = null
  }
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
    <section class="page-header glass-card panel hero-frame reveal">
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
      <aside class="panel sessions-panel reveal reveal--delay-1">
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
          <div
            v-for="session in sessions"
            :key="session.id"
            :class="['session-card', { active: session.id === selectedSessionId, 'session-card--editing': renamingSessionId === session.id }]"
          >
            <template v-if="renamingSessionId === session.id">
              <div class="session-card__editor">
                <div class="session-card__editor-copy">
                  <strong>Rename session</strong>
                  <small>{{ new Date(session.created_at).toLocaleString() }}</small>
                </div>

                <input
                  v-model="renameDraftTitle"
                  class="input session-card__input"
                  placeholder="Enter a session title"
                  :disabled="loading"
                  type="text"
                  @keydown.enter.prevent="saveRenameSession(session)"
                  @keydown.esc.prevent="cancelRenameSession"
                />

                <div class="session-card__editor-actions">
                  <button class="button button--primary" :disabled="loading" type="button" @click="saveRenameSession(session)">
                    Save
                  </button>
                  <button class="button button--ghost" :disabled="loading" type="button" @click="cancelRenameSession">
                    Cancel
                  </button>
                </div>
              </div>
            </template>

            <template v-else>
              <button class="session-card__main" type="button" @click="loadMessages(session.id)">
                <strong>{{ session.title || `Session #${session.id}` }}</strong>
                <small>{{ new Date(session.created_at).toLocaleString() }}</small>
              </button>

              <div class="session-card__actions">
                <CompactActionMenu
                  :aria-label="`Open actions for ${session.title || `Session #${session.id}`}`"
                  :items="getSessionActionItems(session)"
                  @select="handleSessionAction(session, $event)"
                />
              </div>
            </template>
          </div>
        </div>

        <p v-if="!sessions.length" class="empty-state">No sessions yet. Send your first message.</p>
      </aside>

      <section class="panel chat-panel reveal reveal--delay-2">
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
  grid-template-columns: 1fr auto;
  gap: 0.75rem;
  align-items: center;
  width: 100%;
  padding: 0.95rem 1rem;
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  color: inherit;
  background: rgba(15, 23, 42, 0.48);
}

.session-card--editing {
  grid-template-columns: 1fr;
  align-items: stretch;
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

.session-card__main {
  display: grid;
  gap: 0.3rem;
  width: 100%;
  padding: 0;
  border: 0;
  text-align: left;
  color: inherit;
  background: transparent;
}

.session-card__editor {
  display: grid;
  gap: 0.75rem;
  width: 100%;
}

.session-card__editor-copy {
  display: grid;
  gap: 0.2rem;
}

.session-card__editor-copy strong {
  color: #f8fbff;
}

.session-card__input {
  width: 100%;
}

.session-card__editor-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
}

.session-card__actions {
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
  opacity: 0;
  transform: translateX(4px);
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.session-card:hover .session-card__actions,
.session-card:focus-within .session-card__actions {
  opacity: 1;
  transform: translateX(0);
}

.session-card:hover .session-card__actions :deep(.compact-action-menu__trigger),
.session-card:focus-within .session-card__actions :deep(.compact-action-menu__trigger) {
  box-shadow: 0 0 0 1px rgba(6, 182, 212, 0.18);
}

@media (hover: none) {
  .session-card__actions {
    opacity: 1;
    transform: none;
  }
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
