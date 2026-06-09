<script lang="ts">
export default {
  name: 'LlmPresetPanel',
}
</script>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import {
  activateLlmPreset,
  createLlmPreset,
  deleteLlmPreset,
  getLlmPresets,
  type LlmPreset,
} from '../../api/adminSystem'
import { getApiErrorMessage } from '../../utils/apiError'

const props = defineProps<{
  activePresetId: string | null
  formApiKey: string
  formBaseUrl: string
  formModel: string
  busy?: boolean
}>()

const emit = defineEmits<{
  activated: []
  saved: []
  deleted: []
  error: [message: string]
}>()

function formatPresetError(err: unknown, fallback: string): string {
  const msg = getApiErrorMessage(err, fallback)
  if (msg === 'Not Found') {
    return 'LLM 预设接口未找到，请重启后端（uvicorn app.main:app --reload）后再试。'
  }
  return msg
}

const presets = ref<LlmPreset[]>([])
const loading = ref(false)
const presetName = ref('')
const showSaveForm = ref(false)

async function loadPresets() {
  loading.value = true
  try {
    const data = await getLlmPresets()
    presets.value = data.presets
  } catch (err) {
    emit('error', formatPresetError(err, '无法加载 LLM 预设'))
  } finally {
    loading.value = false
  }
}

async function onActivate(presetId: string) {
  if (props.busy || loading.value) return
  loading.value = true
  try {
    await activateLlmPreset(presetId)
    emit('activated')
    await loadPresets()
  } catch (err) {
    emit('error', formatPresetError(err, '切换预设失败'))
  } finally {
    loading.value = false
  }
}

async function onSavePreset() {
  const name = presetName.value.trim()
  if (!name) {
    emit('error', '请输入预设名称')
    return
  }
  if (props.busy || loading.value) return
  loading.value = true
  try {
    const payload: {
      name: string
      llm_api_key?: string
      llm_api_base_url?: string
      llm_model?: string
    } = { name }
    if (props.formApiKey) payload.llm_api_key = props.formApiKey
    if (props.formBaseUrl) payload.llm_api_base_url = props.formBaseUrl
    if (props.formModel) payload.llm_model = props.formModel
    await createLlmPreset(payload)
    presetName.value = ''
    showSaveForm.value = false
    emit('saved')
    await loadPresets()
  } catch (err) {
    emit('error', formatPresetError(err, '保存预设失败'))
  } finally {
    loading.value = false
  }
}

async function onDelete(preset: LlmPreset) {
  if (!window.confirm(`确定删除预设「${preset.name}」？`)) return
  if (props.busy || loading.value) return
  loading.value = true
  try {
    await deleteLlmPreset(preset.id)
    emit('deleted')
    await loadPresets()
  } catch (err) {
    emit('error', formatPresetError(err, '删除预设失败'))
  } finally {
    loading.value = false
  }
}

defineExpose({ loadPresets })

onMounted(() => {
  void loadPresets()
})
</script>

<template>
  <div class="panel llm-preset-panel">
    <div class="title-row">
      <div>
        <p class="eyebrow">快捷切换</p>
        <h3 class="section-title section-title--sm">LLM 预设</h3>
      </div>
      <button
        class="button button--ghost button--sm"
        type="button"
        :disabled="busy || loading"
        @click="showSaveForm = !showSaveForm"
      >
        {{ showSaveForm ? '取消' : '保存为预设' }}
      </button>
    </div>

    <form v-if="showSaveForm" class="preset-save-form" @submit.prevent="onSavePreset">
      <label class="field">
        <span class="label">预设名称</span>
        <input v-model="presetName" class="input input--sm" placeholder="如：OpenAI GPT-4o" required />
      </label>
      <p class="hint-text">将使用左侧表单中的 Base URL、Model；Key 留空则沿用当前活跃 Key。</p>
      <button class="button button--primary button--sm" type="submit" :disabled="busy || loading">
        保存
      </button>
    </form>

    <div v-if="loading && presets.length === 0" class="hint-text">加载中…</div>
    <p v-else-if="presets.length === 0" class="hint-text">暂无预设，可将当前连接参数保存为预设。</p>

    <ul v-else class="preset-list">
      <li
        v-for="preset in presets"
        :key="preset.id"
        class="preset-item"
        :class="{ 'preset-item--active': preset.id === activePresetId }"
      >
        <div class="preset-item__main">
          <p class="preset-item__name">{{ preset.name }}</p>
          <p class="preset-item__meta">
            <span>{{ preset.llm_model || '—' }}</span>
            <span v-if="preset.llm_api_key_masked" class="preset-item__key">{{ preset.llm_api_key_masked }}</span>
          </p>
        </div>
        <div class="preset-item__actions">
          <button
            class="button button--primary button--sm"
            type="button"
            :disabled="busy || loading || preset.id === activePresetId"
            @click="onActivate(preset.id)"
          >
            {{ preset.id === activePresetId ? '使用中' : '切换' }}
          </button>
          <button
            class="button button--ghost button--sm"
            type="button"
            :disabled="busy || loading"
            @click="onDelete(preset)"
          >
            删除
          </button>
        </div>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.llm-preset-panel {
  display: grid;
  gap: 0.75rem;
}

.section-title--sm {
  font-size: 1.05rem;
}

.button--sm {
  padding: 0.35rem 0.75rem;
  font-size: 0.82rem;
}

.preset-save-form {
  display: grid;
  gap: 0.5rem;
  padding: 0.75rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md, 8px);
  background: var(--surface);
}

.hint-text {
  color: var(--text-muted);
  font-size: 0.82rem;
  margin: 0;
}

.preset-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.5rem;
}

.preset-item {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.65rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md, 8px);
  background: var(--surface);
}

.preset-item--active {
  border-color: rgba(var(--accent-1-rgb), 0.45);
  background: rgba(var(--accent-1-rgb), 0.06);
}

.preset-item__name {
  margin: 0;
  font-weight: 600;
  color: var(--heading);
  font-size: 0.9rem;
}

.preset-item__meta {
  margin: 0.15rem 0 0;
  font-size: 0.8rem;
  color: var(--text-muted);
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem 0.75rem;
}

.preset-item__key {
  font-family: var(--font-mono, monospace);
}

.preset-item__actions {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}
</style>
