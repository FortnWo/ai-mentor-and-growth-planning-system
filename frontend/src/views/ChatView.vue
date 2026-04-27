<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import CompactActionMenu from '../components/CompactActionMenu.vue'
import { deleteSession, listMessages, listSessions, renameSession, sendMessage } from '../api/chat'
import { createWebSocket } from '../utils/ws'
import type { ChatMessageRead, ChatSessionRead, MessageDeliveryStatus } from '../api/chat'
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

let ws: WebSocket | null = null

interface RefreshSessionsOptions {
  loadActiveMessages?: boolean
}

interface LoadMessagesOptions {
  silent?: boolean
  retryDelayMs?: number
}

const ASSISTANT_FAILURE_FALLBACK = '(The assistant failed to respond.)'

function getMessageStatus(message: ChatMessageRead): MessageDeliveryStatus {
  if (message.status) {
    return message.status
  }

  if (message.role !== 'assistant') {
    return 'completed'
  }

  if (!message.content.trim()) {
    return 'pending'
  }

  if (message.content.trim() === ASSISTANT_FAILURE_FALLBACK) {
    return 'failed'
  }

  return 'completed'
}

function normalizeMessage(message: ChatMessageRead): ChatMessageRead {
  const status = getMessageStatus(message)
  if (status === 'pending') {
    return { ...message, status, content: message.content.trim() ? message.content : '…' }
  }
  return { ...message, status }
}

function ensureWs() {
  const tokenNow = localStorage.getItem('ai_mentor_access_token') || ''
  if (!tokenNow) return
  if (ws) return
  ws = createWebSocket(tokenNow, (data: any) => {
    if (data?.type === 'typing') {
      const msgId = data.message_id
      const sid = data.session_id
      // clear any transient load errors when we start receiving typing from server
      clearError()
      if (sid !== selectedSessionId.value) return
      const idx = messages.value.findIndex((m) => m.id === msgId)
      if (idx === -1) {
        messages.value.push(normalizeMessage({
          id: msgId,
          session_id: sid,
          role: 'assistant',
          content: '…',
          status: 'pending',
          created_at: new Date().toISOString(),
        }))
      } else {
        const existing = messages.value[idx]
        if (!isFinalAssistantMessage(existing)) {
          messages.value[idx] = normalizeMessage({ ...existing, status: 'pending' })
        }
      }
      return
    }

    if (data?.type === 'new_message') {
      const msg = data.message
      // receiving a final message means prior load failures are now irrelevant
      clearError()
      if (msg && msg.session_id === selectedSessionId.value) {
        const idx = messages.value.findIndex((m) => m.id === msg.id)
        const normalized = normalizeMessage(msg)
        if (idx >= 0) {
          // replace placeholder or existing entry with final message
          messages.value[idx] = normalized
        } else {
          messages.value.push(normalized)
        }
      }
    }
  })
  // clear on close so ensureWs can reconnect later
  ws.onopen = () => {
    console.debug('[WS] open')
  }
  ws.onclose = (ev) => {
    console.debug('[WS] closed', ev)
    ws = null
  }
  ws.onerror = (ev) => {
    console.error('[WS] error', ev)
    // mark ws null so future ensureWs attempts can reconnect
    ws = null
  }
}

const activeSession = computed(
  () => sessions.value.find((session) => session.id === selectedSessionId.value) ?? null,
)
const sessionCount = computed(() => sessions.value.length)
const messageCount = computed(() => messages.value.length)

function isFinalAssistantMessage(m: ChatMessageRead): boolean {
  if (m.role !== 'assistant') {
    return false
  }
  const status = getMessageStatus(m)
  return status === 'completed' || status === 'failed'
}

function normalizeMessages(msgs: ChatMessageRead[]): ChatMessageRead[] {
  return msgs.map((m) => normalizeMessage(m))
}

function clearError() {
  error.value = ''
}

async function refreshSessions(optionsOrEvent: RefreshSessionsOptions | Event = {}) {
  const options = optionsOrEvent instanceof Event ? {} : optionsOrEvent
  const loadActiveMessages = options.loadActiveMessages ?? true

  loading.value = true
  clearError()
  try {
    sessions.value = await listSessions()

    if (!sessions.value.length) {
      selectedSessionId.value = null
      messages.value = []
      return
    }

    if (!selectedSessionId.value) {
      selectedSessionId.value = sessions.value[0].id
    }

    if (loadActiveMessages) {
      await loadMessages(selectedSessionId.value)
    }
  } catch {
    error.value = 'Could not load sessions for current user.'
  } finally {
    loading.value = false
  }
}

async function loadMessages(sessionId: number, options: LoadMessagesOptions = {}) {
  const silent = options.silent ?? false
  const retryDelayMs = options.retryDelayMs ?? 200

  loading.value = true
  clearError()
  try {
    console.debug('[loadMessages] sessionId=', sessionId)
    const msgs = await listMessages(sessionId)
    messages.value = normalizeMessages(msgs)
    selectedSessionId.value = sessionId
  } catch {
    console.error('[loadMessages] failed for', sessionId)
    // single short retry for transient issues
    try {
      await new Promise((res) => setTimeout(res, retryDelayMs))
      const retryMsgs = await listMessages(sessionId)
      messages.value = normalizeMessages(retryMsgs)
      selectedSessionId.value = sessionId
      return
    } catch (err) {
      console.error('[loadMessages] retry failed for', sessionId, err)
    }
    if (!silent) {
      error.value = 'Could not load messages for this session.'
    }
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
  // user must be logged in (authState.user) — backend uses token for identity

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
    await renameSession(session.id, trimmedTitle)
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
  // user must be logged in (authState.user) — backend uses token for identity

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
    await deleteSession(sessionId)

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

  // connect before sending so we won't miss early typing/new_message pushes
  ensureWs()

  clearError()
  loading.value = true
  try {
    const response = await sendMessage({
      session_id: selectedSessionId.value ?? undefined,
      title: newSessionTitle.value.trim() || undefined,
      message: text,
    })

    input.value = ''
    selectedSessionId.value = response.session.id
    // refresh sessions list without triggering a second immediate messages fetch
    await refreshSessions({ loadActiveMessages: false })
    // initial post-send fetch is best-effort and should not flash an error banner
    await loadMessages(response.session.id, { silent: true })

    // ensure websocket connected to receive assistant reply in real time
    ensureWs()

    // if assistant message is not present yet, prefer WS push; fall back to polling
    if (!response.assistant_message) {
      // if ws is connected, wait briefly for the push (avoid duplicate polling)
      if (ws) {
        const waitStart = Date.now()
        const waitMs = 10_000 // wait up to 10s for websocket push
        while (Date.now() - waitStart < waitMs) {
          await new Promise((res) => setTimeout(res, 500))
          if (messages.value.some((m) => isFinalAssistantMessage(m))) {
            break
          }
        }

        // if we already received assistant via WS, skip polling
        if (messages.value.some((m) => isFinalAssistantMessage(m))) {
          // done
        } else {
          // fallback to polling for the rest of the timeout window
          const start = Date.now()
          const timeoutMs = 60_000
          const pollInterval = 1000

          while (Date.now() - start < timeoutMs) {
            await new Promise((res) => setTimeout(res, pollInterval))
            try {
              const msgs = await listMessages(response.session.id)
              messages.value = normalizeMessages(msgs)
              if (messages.value.some((m) => isFinalAssistantMessage(m))) {
                break
              }
            } catch {
              // ignore and retry until timeout
            }
          }
        }
      } else {
        // no ws available: poll as before
        const start = Date.now()
        const timeoutMs = 60_000 // match backend behavior / client timeout
        const pollInterval = 1000

        while (Date.now() - start < timeoutMs) {
          await new Promise((res) => setTimeout(res, pollInterval))
          try {
            const msgs = await listMessages(response.session.id)
            messages.value = normalizeMessages(msgs)
            // count final assistant message only (pending placeholders do not count)
            const hasAssistant = messages.value.some((m) => isFinalAssistantMessage(m))
            if (hasAssistant) {
              break
            }
          } catch {
            // ignore and retry until timeout
          }
        }
      }
    }
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
  // ensure websocket connects after we refresh user/session info
  ensureWs()
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
            <small v-if="message.role === 'assistant' && getMessageStatus(message) === 'pending'">Generating...</small>
            <small v-if="message.role === 'assistant' && getMessageStatus(message) === 'failed'">Generation failed</small>
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

.message-bubble small {
  color: var(--text-muted);
  font-size: 0.78rem;
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
