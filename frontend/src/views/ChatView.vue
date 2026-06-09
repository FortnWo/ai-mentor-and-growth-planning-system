<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import CompactActionMenu from '../components/CompactActionMenu'
import { deleteSession, listMessages, listSessions, renameSession, sendMessage, stopMessageGeneration } from '../api/chat'
import { createWebSocket } from '../utils/ws'
import type { ChatMessageRead, ChatSessionRead, MessageDeliveryStatus } from '../api/chat'
import { authState, isFullAdmin, refreshCurrentUser } from '../stores/auth'

const adminMode = computed(() => isFullAdmin(authState.user))
const assistantLabel = computed(() => (adminMode.value ? 'AI管理助手' : 'AI 导师'))
const inputPlaceholder = computed(() =>
  adminMode.value ? '向 AI 管理助手提问…' : '向你的 AI 导师提问…',
)

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
const messagesContainer = ref<HTMLElement | null>(null)
const sessionsPanelOpen = ref<boolean>(true)

const SESSIONS_WIDTH_STORAGE_KEY = 'chat_sessions_panel_width_percent'
const SESSIONS_WIDTH_MIN = 15
const SESSIONS_WIDTH_MAX = 40
const SESSIONS_WIDTH_DEFAULT = 20
const LAYOUT_RESIZER_PX = 10

const chatLayoutRef = ref<HTMLElement | null>(null)
const sessionsWidthPercent = ref<number>(SESSIONS_WIDTH_DEFAULT)
const isResizingSessions = ref<boolean>(false)

let ws: WebSocket | null = null
let pollAbortController: AbortController | null = null

function clampSessionsWidth(value: number) {
  return Math.min(SESSIONS_WIDTH_MAX, Math.max(SESSIONS_WIDTH_MIN, value))
}

function loadSessionsWidth() {
  const raw = localStorage.getItem(SESSIONS_WIDTH_STORAGE_KEY)
  if (!raw) {
    return
  }

  const parsed = Number.parseFloat(raw)
  if (Number.isFinite(parsed)) {
    sessionsWidthPercent.value = clampSessionsWidth(parsed)
  }
}

function saveSessionsWidth() {
  localStorage.setItem(SESSIONS_WIDTH_STORAGE_KEY, String(sessionsWidthPercent.value))
}

const chatLayoutColumns = computed(() => {
  if (!sessionsPanelOpen.value) {
    return '0 0 minmax(0, 1fr)'
  }

  const left = sessionsWidthPercent.value
  return `minmax(0, ${left}%) ${LAYOUT_RESIZER_PX}px minmax(0, 1fr)`
})

function updateSessionsWidthFromPointer(clientX: number) {
  const layout = chatLayoutRef.value
  if (!layout) {
    return
  }

  const rect = layout.getBoundingClientRect()
  const ratio = ((clientX - rect.left) / rect.width) * 100
  sessionsWidthPercent.value = clampSessionsWidth(ratio)
}

function onResizerPointerDown(event: PointerEvent) {
  if (!sessionsPanelOpen.value) {
    return
  }

  isResizingSessions.value = true
  event.preventDefault()
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
  updateSessionsWidthFromPointer(event.clientX)
}

function onResizerPointerMove(event: PointerEvent) {
  if (!isResizingSessions.value) {
    return
  }

  updateSessionsWidthFromPointer(event.clientX)
}

function endSessionsResize(event: PointerEvent) {
  if (!isResizingSessions.value) {
    return
  }

  isResizingSessions.value = false
  if (event.currentTarget instanceof HTMLElement && event.currentTarget.hasPointerCapture(event.pointerId)) {
    event.currentTarget.releasePointerCapture(event.pointerId)
  }
  saveSessionsWidth()
}

function onResizerLostPointerCapture() {
  if (!isResizingSessions.value) {
    return
  }

  isResizingSessions.value = false
  saveSessionsWidth()
}

interface RefreshSessionsOptions {
  loadActiveMessages?: boolean
}

interface LoadMessagesOptions {
  silent?: boolean
  retryDelayMs?: number
}

const ASSISTANT_FAILURE_FALLBACK = '(The assistant failed to respond.)'
const ASSISTANT_STOPPED_MESSAGE = '（已停止生成）'
const DEFAULT_SESSION_TITLE = '未命名会话'

function displaySessionTitle(title?: string | null) {
  const trimmed = title?.trim()
  return trimmed && trimmed !== DEFAULT_SESSION_TITLE ? trimmed : DEFAULT_SESSION_TITLE
}

function updateSessionTitleInList(sessionId: number, title: string) {
  const index = sessions.value.findIndex((session) => session.id === sessionId)
  if (index >= 0) {
    sessions.value[index] = { ...sessions.value[index], title }
  }
}

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

  if (message.content.trim() === ASSISTANT_STOPPED_MESSAGE) {
    return 'cancelled'
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
      return
    }

    if (data?.type === 'session_title_updated') {
      const sessionId = data.session_id
      const title = data.title
      if (typeof sessionId === 'number' && typeof title === 'string') {
        updateSessionTitleInList(sessionId, title)
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
const activeSessionTitle = computed(() => displaySessionTitle(activeSession.value?.title))
const sessionCount = computed(() => sessions.value.length)
const messageCount = computed(() => messages.value.length)

const isGenerating = computed(() =>
  messages.value.some(
    (message) => message.role === 'assistant' && getMessageStatus(message) === 'pending',
  ),
)

const pendingAssistantMessage = computed(() => {
  for (let index = messages.value.length - 1; index >= 0; index -= 1) {
    const message = messages.value[index]
    if (message.role === 'assistant' && getMessageStatus(message) === 'pending') {
      return message
    }
  }
  return null
})

function isFinalAssistantMessage(m: ChatMessageRead): boolean {
  if (m.role !== 'assistant') {
    return false
  }
  const status = getMessageStatus(m)
  return status === 'completed' || status === 'failed' || status === 'cancelled'
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
  newSessionTitle.value = ''
}

function scrollMessagesToBottom() {
  if (!messagesContainer.value) return
  messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
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

  const confirmed = window.confirm(`确定删除会话 ${displaySessionTitle(session.title)} 吗？`)
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

function abortActivePolling() {
  if (pollAbortController) {
    pollAbortController.abort()
    pollAbortController = null
  }
}

async function waitForPendingAssistant(sessionId: number, signal: AbortSignal) {
  const timeoutMs = 60_000
  const pollInterval = 1000
  const start = Date.now()

  while (Date.now() - start < timeoutMs) {
    if (signal.aborted) {
      return
    }

    if (messages.value.some((message) => isFinalAssistantMessage(message))) {
      return
    }

    await new Promise((resolve) => setTimeout(resolve, pollInterval))
    if (signal.aborted) {
      return
    }

    try {
      const msgs = await listMessages(sessionId)
      messages.value = normalizeMessages(msgs)
      if (messages.value.some((message) => isFinalAssistantMessage(message))) {
        return
      }
    } catch {
      // ignore and retry until timeout
    }
  }
}

function startPendingAssistantWatch(sessionId: number) {
  abortActivePolling()
  pollAbortController = new AbortController()
  const signal = pollAbortController.signal

  void (async () => {
    if (ws) {
      const waitStart = Date.now()
      const waitMs = 10_000
      while (Date.now() - waitStart < waitMs && !signal.aborted) {
        await new Promise((resolve) => setTimeout(resolve, 500))
        if (messages.value.some((message) => isFinalAssistantMessage(message))) {
          return
        }
      }
    }

    if (!signal.aborted && !messages.value.some((message) => isFinalAssistantMessage(message))) {
      await waitForPendingAssistant(sessionId, signal)
    }

    if (!signal.aborted) {
      await refreshSessions({ loadActiveMessages: false })
    }
  })()
}

async function pauseGeneration() {
  const pending = pendingAssistantMessage.value
  const sessionId = selectedSessionId.value
  if (!pending || !sessionId) {
    return
  }

  abortActivePolling()
  clearError()

  try {
    await stopMessageGeneration(sessionId, pending.id)
    const index = messages.value.findIndex((message) => message.id === pending.id)
    if (index >= 0) {
      messages.value[index] = normalizeMessage({
        ...messages.value[index],
        content: ASSISTANT_STOPPED_MESSAGE,
        status: 'cancelled',
      })
    }
  } catch {
    error.value = '无法停止生成。'
  }
}

async function submitMessage() {
  if (isGenerating.value) {
    await pauseGeneration()
    return
  }

  const text = input.value.trim()
  if (!text) {
    return
  }

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
    await refreshSessions({ loadActiveMessages: false })

    const nextMessages = await listMessages(response.session.id)
    messages.value = normalizeMessages(nextMessages)
    if (response.assistant_message) {
      const existingIndex = messages.value.findIndex((message) => message.id === response.assistant_message?.id)
      const normalizedAssistant = normalizeMessage(response.assistant_message)
      if (existingIndex >= 0) {
        messages.value[existingIndex] = normalizedAssistant
      } else {
        messages.value.push(normalizedAssistant)
      }
    }

    await nextTick()
    scrollMessagesToBottom()
    ensureWs()
    startPendingAssistantWatch(response.session.id)
  } catch {
    error.value = '无法发送消息。'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  loadSessionsWidth()
  if (!authState.user) {
    await refreshCurrentUser()
  }
  await refreshSessions()
  // ensure websocket connects after we refresh user/session info
  ensureWs()
})

onBeforeUnmount(() => {
  abortActivePolling()
  if (isResizingSessions.value) {
    isResizingSessions.value = false
    saveSessionsWidth()
  }
})

watch(
  () => messages.value.length,
  async () => {
    await nextTick()
    scrollMessagesToBottom()
  },
)
</script>

<template>
  <div class="page page--wide chat-page">
    <p v-if="error" class="feedback feedback--error">{{ error }}</p>

    <section
      ref="chatLayoutRef"
      :class="['grid-2 chat-layout', { 'chat-layout--resizing': isResizingSessions, 'chat-layout--sessions-hidden': !sessionsPanelOpen }]"
      :style="{ gridTemplateColumns: chatLayoutColumns }"
    >
      <aside :class="['panel sessions-panel reveal reveal--delay-1', { 'sessions-panel--hidden': !sessionsPanelOpen }]">
        <div class="title-row">
          <div>
            <p class="eyebrow">会话</p>
            <h2 class="section-title">对话历史</h2>
          </div>

          <div class="sessions-panel__title-tools">
            <button
              class="button button--ghost sessions-refresh-btn"
              :class="{ 'sessions-refresh-btn--loading': loading }"
              :disabled="loading"
              type="button"
              aria-label="刷新会话列表"
              title="刷新"
              @click="refreshSessions"
            >
              <svg class="sessions-refresh-btn__icon" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  fill="none"
                  stroke="currentColor"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M21 12a9 9 0 1 1-2.64-6.36M21 3v6h-6M3 12a9 9 0 1 1 2.64 6.36M3 21v-6h6"
                />
              </svg>
            </button>
            <span class="chip chip--neutral">共 {{ sessionCount }} 条</span>
          </div>
        </div>

        <div class="field sessions-panel__title-field">
          <label class="label" for="session-title">自定义会话标题（可选）</label>
          <input
            id="session-title"
            v-model="newSessionTitle"
            class="input sessions-panel__title-input"
            placeholder="留空则 AI 将在首轮对话后自动生成标题"
          />
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
                <strong class="session-card__title">{{ displaySessionTitle(session.title) }}</strong>
                <small>{{ new Date(session.created_at).toLocaleString() }}</small>
              </button>

              <div class="session-card__actions">
                <CompactActionMenu :aria-label="`Open actions for ${displaySessionTitle(session.title)}`"
                  :items="getSessionActionItems(session)" @select="handleSessionAction(session, $event)" />
              </div>
            </template>
          </div>
        </div>

        <p v-if="!sessions.length" class="empty-state">还没有会话，先发送第一条消息吧。</p>
      </aside>

      <button
        v-if="sessionsPanelOpen"
        type="button"
        class="chat-layout__resizer"
        aria-label="调整会话栏与聊天区域宽度"
        aria-orientation="vertical"
        :aria-valuemin="SESSIONS_WIDTH_MIN"
        :aria-valuemax="SESSIONS_WIDTH_MAX"
        :aria-valuenow="Math.round(sessionsWidthPercent)"
        @pointerdown="onResizerPointerDown"
        @pointermove="onResizerPointerMove"
        @pointerup="endSessionsResize"
        @pointercancel="endSessionsResize"
        @lostpointercapture="onResizerLostPointerCapture"
      />

      <section class="panel chat-panel reveal reveal--delay-2">
        <div class="title-row">
          <div class="chat-panel__heading">
            <button class="button button--ghost sessions-toggle" type="button" @click="sessionsPanelOpen = !sessionsPanelOpen">
              {{ sessionsPanelOpen ? '隐藏会话' : '显示会话' }}
            </button>

            <div>
            <p class="eyebrow">聊天画布</p>
            <h2 class="section-title">{{ activeSessionTitle }}</h2>
            </div>
          </div>

          <div class="chat-panel__title-actions">
            <span v-if="adminMode" class="chip chip--admin admin-badge">管理助手模式</span>
            <button class="button button--primary" :disabled="loading" type="button" @click="startNewSession">
              新建聊天
            </button>
            <span class="chip chip--active">{{ messageCount }} messages</span>
          </div>
        </div>

        <div class="divider"></div>

        <div ref="messagesContainer" class="messages">
          <div v-for="message in messages" :key="message.id" :class="[
            'message-bubble',
            message.role === 'user' ? 'message-bubble--user' : 'message-bubble--assistant',
          ]">
            <strong>{{ message.role === 'user' ? '' : assistantLabel }}</strong>
            <small v-if="message.role === 'assistant' && getMessageStatus(message) === 'pending'">正在生成…</small>
            <small v-if="message.role === 'assistant' && getMessageStatus(message) === 'failed'">生成失败</small>
            <small v-if="message.role === 'assistant' && getMessageStatus(message) === 'cancelled'">已停止</small>
            <p>{{ message.content }}</p>
          </div>

          <p v-if="!messages.length" class="empty-state">开始一段对话后，消息会显示在这里。</p>
        </div>

        <form class="message-form" @submit.prevent="submitMessage">
          <input v-model="input" :disabled="loading || isGenerating" class="input" :placeholder="inputPlaceholder" />
          <button
            class="button button--primary"
            :disabled="loading && !isGenerating"
            :type="isGenerating ? 'button' : 'submit'"
            @click="isGenerating ? pauseGeneration() : undefined"
          >
            {{ isGenerating ? '暂停' : '发送' }}
          </button>
        </form>
      </section>
    </section>
  </div>
</template>

<style scoped>
.chat-layout {
  align-items: stretch;
  min-height: min(68vh, 760px);
}

.chat-layout--resizing {
  cursor: col-resize;
  user-select: none;
}

.chat-layout__resizer {
  align-self: stretch;
  justify-self: center;
  width: 10px;
  margin: 0;
  padding: 0;
  border: 0;
  border-radius: 999px;
  background: transparent;
  cursor: col-resize;
  touch-action: none;
  position: relative;
  z-index: 2;
}

.chat-layout__resizer::before {
  content: '';
  position: absolute;
  top: 10%;
  bottom: 10%;
  left: 50%;
  width: 3px;
  border-radius: 999px;
  background: rgba(var(--accent-1-rgb), 0.16);
  transform: translateX(-50%);
}

.chat-layout__resizer:hover::before,
.chat-layout__resizer:focus-visible::before,
.chat-layout--resizing .chat-layout__resizer::before {
  background: rgba(var(--accent-1-rgb), 0.38);
}

.sessions-panel,
.chat-panel {
  display: grid;
  gap: 1rem;
  min-height: 0;
  max-height: min(78vh, 760px);
}

.sessions-panel {
  grid-template-rows: auto auto minmax(0, 1fr);
  width: 100%;
  min-width: 0;
  transition: none;
}

.sessions-panel--hidden {
  opacity: 0;

  pointer-events: none;
  max-width: 0;
  overflow: hidden;
  padding: 0;
  border-color: transparent;
}

.session-list,
.messages {
  display: grid;
  min-height: 0;
  overflow-y: auto;
  padding-right: 0.25rem;
}

.session-list {
  gap: 0.42rem;
  align-content: start;
}

.messages {
  gap: 0.75rem;
  align-content: start;
}

.message-bubble small {
  color: var(--text-muted);
  font-size: 0.78rem;
}

.message-bubble p {
  margin: 0.35rem 0 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.session-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.38rem;
  align-items: center;
  width: 100%;
  padding: 0;
  border-radius: 14px;
  border: 0;
  color: inherit;
  background: transparent;
}

.session-card--editing {
  grid-template-columns: 1fr;
  align-items: stretch;
}

.session-card.active {
  background: transparent;
}

.session-card strong {
  color: var(--heading);
}

.session-card__title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.95rem;
  line-height: 1.3;
}

.session-card small {
  color: color-mix(in srgb, var(--text-muted) 82%, transparent);
  font-size: 0.76rem;
  line-height: 1.25;
}

.session-card__main {
  display: grid;
  gap: 0.18rem;
  width: 100%;
  padding: 0.6rem 0.76rem;
  border: 1px solid rgba(var(--accent-1-rgb), 0.12);
  border-radius: 13px;
  text-align: left;
  color: inherit;
  background: rgba(var(--accent-1-rgb), 0.02);
  transition:
    none;
}

.session-card:hover .session-card__main,
.session-card:focus-within .session-card__main {
  border-color: rgba(var(--accent-1-rgb), 0.18);
  background: rgba(var(--accent-1-rgb), 0.05);
}

.session-card.active .session-card__main {
  border-color: rgba(var(--accent-1-rgb), 0.22);
  background: rgba(var(--accent-1-rgb), 0.07);
}

.session-card__editor {
  display: grid;
  gap: 0.75rem;
  width: 100%;
  padding: 0.68rem 0.76rem;
  border: 1px solid rgba(var(--accent-1-rgb), 0.22);
  border-radius: 13px;
  background: rgba(var(--accent-1-rgb), 0.05);
}

.session-card__editor-copy {
  display: grid;
  gap: 0.2rem;
}

.session-card__editor-copy strong {
  color: var(--heading);
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
  align-items: center;
  justify-content: flex-end;
  opacity: 0;
  transform: translateX(4px);
  transition:
    none;
}

.session-card:hover .session-card__actions,
.session-card:focus-within .session-card__actions {
  opacity: 1;
  transform: translateX(0);
}

.session-card:hover .session-card__actions :deep(.compact-action-menu__trigger),
.session-card:focus-within .session-card__actions :deep(.compact-action-menu__trigger) {
  box-shadow: 0 0 0 1px rgba(var(--accent-1-rgb), 0.18);
}

@media (hover: none) {
  .session-card__actions {
    opacity: 1;
    transform: none;
  }
}

.chat-panel {
  grid-template-rows: auto auto minmax(0, 1fr) auto;
  overflow: hidden;
  position: relative;
}

.sessions-panel__title-tools {
  display: flex;
  align-items: center;
  gap: 0.55rem;
}

.sessions-refresh-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.5rem;
  min-width: 2.5rem;
  height: 2.5rem;
  min-height: 2.5rem;
  padding: 0;
  color: var(--heading);
}

.sessions-refresh-btn__icon {
  width: 1.15rem;
  height: 1.15rem;
  flex-shrink: 0;
}

.sessions-refresh-btn--loading .sessions-refresh-btn__icon {
  animation: sessions-refresh-spin 0.8s linear infinite;
}

@keyframes sessions-refresh-spin {
  to {
    transform: rotate(360deg);
  }
}

.sessions-panel__title-field .label {
  font-size: 0.8rem;
}

.sessions-panel__title-input {
  font-size: 0.82rem;
  padding: 0.52rem 0.72rem;
}

.sessions-panel__title-input::placeholder {
  font-size: 0.78rem;
}

.chat-panel__heading {
  display: flex;
  align-items: flex-start;
  gap: 0.7rem;
}

.chat-panel__title-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 0.65rem;
}

.sessions-toggle {
  flex-shrink: 0;
  min-width: 6.2rem;
  padding-inline: 0.7rem;
}

.message-form {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.75rem;
  align-items: end;
  min-width: 0;
}

.section-title {
  margin: 0;
  font-family: var(--font-display);
  color: var(--heading);
  font-size: clamp(1.25rem, 2vw, 1.7rem);
  letter-spacing: -0.03em;
}

@media (max-width: 1024px) {
  .chat-layout {
    grid-template-columns: 1fr !important;
    min-height: unset;
    transition: none;
  }

  .chat-layout__resizer {
    display: none;
  }

  .sessions-panel,
  .chat-panel {
    max-height: none;
  }

  .session-list,
  .messages {
    overflow: visible;
    max-height: none;
  }

  .sessions-panel--hidden {
    max-height: 0;
    margin: 0;
  }

  .message-form {
    grid-template-columns: 1fr;
  }
}

.chip--admin {
  background: rgba(var(--accent-1-rgb), 0.15);
  color: var(--primary);
  border: 1px solid rgba(var(--accent-1-rgb), 0.3);
}

.admin-badge {
  font-size: 0.78rem;
  padding: 0.25rem 0.65rem;
}
</style>
