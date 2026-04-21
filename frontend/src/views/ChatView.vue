<script setup lang="ts">
import { onMounted, ref } from 'vue'

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
  <div class="view">
    <h1>AI Mentor Chat</h1>

    <div class="controls card">
      <div class="session-actions">
        <button :disabled="loading" @click="refreshSessions">Refresh Sessions</button>
        <button :disabled="loading" @click="startNewSession">New Chat</button>
      </div>
      <label>
        New Session Title (optional)
        <input v-model="newSessionTitle" placeholder="e.g. Midterm recovery plan" />
      </label>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div class="layout">
      <aside class="card sessions">
        <h2>Sessions</h2>
        <button
          v-for="session in sessions"
          :key="session.id"
          :class="['session-item', { active: session.id === selectedSessionId }]"
          @click="loadMessages(session.id)"
        >
          <strong>{{ session.title || `Session #${session.id}` }}</strong>
          <small>{{ new Date(session.created_at).toLocaleString() }}</small>
        </button>

        <p v-if="!sessions.length" class="hint">No sessions yet. Send your first message.</p>
      </aside>

      <section class="card chat-panel">
        <div class="messages">
          <div
            v-for="message in messages"
            :key="message.id"
            :class="['message', message.role]"
          >
            <strong>{{ message.role === 'user' ? 'You' : 'AI Mentor' }}</strong>
            <p>{{ message.content }}</p>
          </div>

          <p v-if="!messages.length" class="hint">Start a conversation to see messages here.</p>
        </div>

        <form class="input-row" @submit.prevent="submitMessage">
          <input v-model="input" :disabled="loading" placeholder="Ask your AI mentor anything..." />
          <button :disabled="loading" type="submit">Send</button>
        </form>
      </section>
    </div>
  </div>
</template>

<style scoped>
.view {
  max-width: 980px;
  margin: 2rem auto;
  padding: 1rem;
  text-align: left;
}

.card {
  border: 1px solid #ddd;
  border-radius: 10px;
  background: #fff;
  padding: 1rem;
}

.controls {
  display: grid;
  grid-template-columns: auto minmax(220px, 1fr);
  gap: 0.65rem;
  align-items: end;
  margin-bottom: 1rem;
}

.session-actions {
  display: flex;
  gap: 0.65rem;
}

label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.9rem;
}

input,
button {
  font: inherit;
}

input {
  border: 1px solid #ccc;
  border-radius: 6px;
  padding: 0.5rem 0.65rem;
}

button {
  border: none;
  border-radius: 6px;
  padding: 0.55rem 0.95rem;
  background: #1a56db;
  color: #fff;
  cursor: pointer;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 0.75rem;
}

.sessions {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.sessions h2 {
  margin: 0 0 0.2rem;
}

.session-item {
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  background: #f3f4f6;
  color: #0f172a;
}

.session-item.active {
  background: #bfdbfe;
}

.chat-panel {
  display: flex;
  flex-direction: column;
  min-height: 460px;
}

.messages {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  flex: 1;
  overflow-y: auto;
  margin-bottom: 0.85rem;
}

.message {
  border-radius: 8px;
  padding: 0.65rem 0.75rem;
}

.message p {
  margin: 0.25rem 0 0;
  white-space: pre-wrap;
}

.message.user {
  background: #dbeafe;
}

.message.assistant {
  background: #dcfce7;
}

.input-row {
  display: flex;
  gap: 0.5rem;
}

.input-row input {
  flex: 1;
}

.hint {
  color: #666;
  font-size: 0.9rem;
}

.error {
  color: #b91c1c;
  margin-bottom: 0.75rem;
}

@media (max-width: 900px) {
  .controls {
    grid-template-columns: 1fr;
  }

  .layout {
    grid-template-columns: 1fr;
  }
}
</style>
