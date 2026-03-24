<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ping } from '../api'

const status = ref<string>('Checking…')
const messages = ref<{ role: string; content: string }[]>([])
const input = ref<string>('')

onMounted(async () => {
  try {
    const res = await ping()
    status.value = `API ${res.status} — ${res.message}`
  } catch {
    status.value = 'API unreachable'
  }
})

async function sendMessage() {
  const text = input.value.trim()
  if (!text) return
  messages.value.push({ role: 'user', content: text })
  input.value = ''

  try {
    const { sendMessage: send } = await import('../api')
    const res = await send({ message: text })
    messages.value.push({ role: res.role, content: res.content })
  } catch {
    messages.value.push({ role: 'assistant', content: 'Error: could not reach API.' })
  }
}
</script>

<template>
  <div class="view">
    <h1>AI Mentor Chat</h1>
    <p class="status">{{ status }}</p>

    <div class="messages">
      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        :class="['message', msg.role]"
      >
        <strong>{{ msg.role === 'user' ? 'You' : 'AI Mentor' }}:</strong>
        {{ msg.content }}
      </div>
    </div>

    <form class="input-row" @submit.prevent="sendMessage">
      <input v-model="input" placeholder="Type your message…" />
      <button type="submit">Send</button>
    </form>
  </div>
</template>

<style scoped>
.view { max-width: 700px; margin: 2rem auto; padding: 1rem; }
.status { color: #666; font-size: 0.85rem; margin-bottom: 1rem; }
.messages { border: 1px solid #ddd; border-radius: 6px; padding: 1rem; min-height: 200px; margin-bottom: 1rem; }
.message { margin-bottom: 0.5rem; }
.message.user { color: #1a56db; }
.message.assistant { color: #166534; }
.input-row { display: flex; gap: 0.5rem; }
.input-row input { flex: 1; padding: 0.5rem 0.75rem; border: 1px solid #ddd; border-radius: 4px; }
.input-row button { padding: 0.5rem 1rem; background: #1a56db; color: white; border: none; border-radius: 4px; cursor: pointer; }
</style>
