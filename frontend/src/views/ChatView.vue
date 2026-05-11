<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import CompactActionMenu from '../components/CompactActionMenu'
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
    error.value = '无法加载当前用户的会话。'
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
      error.value = '无法加载该会话的消息。'
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
    error.value = '会话标题不能为空。'
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
    error.value = '无法重命名该会话。'
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
    error.value = '未找到会话。'
    return
  }

  const confirmed = window.confirm(`确定删除会话 ${session.title || `#${session.id}`} 吗？`)
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
    error.value = '无法删除该会话。'
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
    error.value = '无法发送消息。'
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
          <p class="page-kicker">AI 导师聊天</p>
          <h1 class="page-title">像工作台一样设计的对话指导。</h1>
          <p class="page-subtitle">
            在安静而高对比度的工作区中整理会话、回看历史并发送消息。
          </p>
        </div>

        <div class="hero-actions">
          <button class="button button--primary" :disabled="loading" type="button" @click="refreshSessions">
            刷新会话
          </button>
          <button class="button button--ghost" :disabled="loading" type="button" @click="startNewSession">
            新建聊天
          </button>
        </div>
      </div>

      <div class="stat-grid">
        <article class="stat-card">
          <p class="stat-label">会话</p>
          <p class="stat-value">{{ sessionCount }}</p>
          <p class="stat-note">已保存的对话线程</p>
        </article>

        <article class="stat-card">
          <p class="stat-label">消息</p>
          <p class="stat-value">{{ messageCount }}</p>
          <p class="stat-note">当前线程中的可见消息</p>
        </article>

        <article class="stat-card">
          <p class="stat-label">当前会话</p>
          <p class="stat-value">{{ activeSession?.title || `Session #${activeSession?.id ?? '-'}` }}</p>
          <p class="stat-note">
            {{ activeSession ? new Date(activeSession.created_at).toLocaleString() : '开始一个新的对话' }}
          </p>
        </article>
      </div>
    </section>

    <p v-if="error" class="feedback feedback--error">{{ error }}</p>

    <section class="grid-2 chat-layout">
      <aside class="panel sessions-panel reveal reveal--delay-1">
        <div class="title-row">
          <div>
            <p class="eyebrow">会话</p>
            <h2 class="section-title">对话历史</h2>
          </div>

          <span class="chip chip--neutral">共 {{ sessionCount }} 条</span>
        </div>

        <div class="field">
          <label class="label" for="session-title">新会话标题（可选）</label>
          <input id="session-title" v-model="newSessionTitle" class="input" placeholder="例如：期中复盘计划" />
        </div>

        <div class="button-row">
          <button class="button button--ghost" :disabled="loading" type="button" @click="refreshSessions">
            刷新
          </button>
          <button class="button button--primary" :disabled="loading" type="button" @click="startNewSession">
            新建聊天
          </button>
        </div>

        <div class="session-list">
          <div v-for="session in sessions" :key="session.id"
            :class="['session-card', { active: session.id === selectedSessionId, 'session-card--editing': renamingSessionId === session.id }]">
            <template v-if="renamingSessionId === session.id">
              <div class="session-card__editor">
                <div class="session-card__editor-copy">
                  <strong>重命名会话</strong>
                  <small>{{ new Date(session.created_at).toLocaleString() }}</small>
                </div>

                <input v-model="renameDraftTitle" class="input session-card__input" placeholder="请输入会话标题"
                  :disabled="loading" type="text" @keydown.enter.prevent="saveRenameSession(session)"
                  @keydown.esc.prevent="cancelRenameSession" />

                <div class="session-card__editor-actions">
                  <button class="button button--primary" :disabled="loading" type="button"
                    @click="saveRenameSession(session)">
                    保存
                  </button>
                  <button class="button button--ghost" :disabled="loading" type="button" @click="cancelRenameSession">
                    取消
                  </button>
                </div>
              </div>
            </template>

            <template v-else>
              <button class="session-card__main" type="button" @click="loadMessages(session.id)">
                <strong>{{ session.title || `会话 #${session.id}` }}</strong>
                <small>{{ new Date(session.created_at).toLocaleString() }}</small>
              </button>

              <div class="session-card__actions">
                <CompactActionMenu :aria-label="`Open actions for ${session.title || `Session #${session.id}`}`"
                  :items="getSessionActionItems(session)" @select="handleSessionAction(session, $event)" />
              </div>
            </template>
          </div>
        </div>

        <p v-if="!sessions.length" class="empty-state">还没有会话，先发送第一条消息吧。</p>
      </aside>

      <section class="panel chat-panel reveal reveal--delay-2">
        <div class="title-row">
          <div>
            <p class="eyebrow">聊天画布</p>
            <h2 class="section-title">{{ activeSession?.title || '未命名会话' }}</h2>
          </div>

          <span class="chip chip--active">{{ messageCount }} messages</span>
        </div>

        <div class="divider"></div>

        <div class="messages">
          <div v-for="message in messages" :key="message.id" :class="[
            'message-bubble',
            message.role === 'user' ? 'message-bubble--user' : 'message-bubble--assistant',
          ]">
            <strong>{{ message.role === 'user' ? '你' : 'AI 导师' }}</strong>
            <small v-if="message.role === 'assistant' && getMessageStatus(message) === 'pending'">正在生成…</small>
            <small v-if="message.role === 'assistant' && getMessageStatus(message) === 'failed'">生成失败</small>
            <p>{{ message.content }}</p>
          </div>

          <p v-if="!messages.length" class="empty-state">开始一段对话后，消息会显示在这里。</p>
        </div>

        <form class="message-form" @submit.prevent="submitMessage">
          <input v-model="input" :disabled="loading" class="input" placeholder="向你的 AI 导师提问…" />
          <button class="button button--primary" :disabled="loading" type="submit">发送</button>
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
