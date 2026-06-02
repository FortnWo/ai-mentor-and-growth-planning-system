<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  ADMIN_PERMISSION_OPTIONS,
  type AdminPermissionKey,
} from '../constants/adminPermissions'

const props = withDefaults(
  defineProps<{
    modelValue: string[]
    disabled?: boolean
    placeholder?: string
  }>(),
  {
    disabled: false,
    placeholder: '选择权限…',
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

const rootRef = ref<HTMLElement | null>(null)
const open = ref(false)

const selectedSet = computed(() => new Set(props.modelValue))

const displayText = computed(() => {
  if (!props.modelValue.length) {
    return ''
  }
  return props.modelValue.join(', ')
})

function normalizeSelection(keys: string[]): string[] {
  const allowed = new Set(ADMIN_PERMISSION_OPTIONS.map((option) => option.key))
  const ordered: string[] = []
  for (const key of ADMIN_PERMISSION_OPTIONS) {
    if (keys.includes(key.key) && allowed.has(key.key)) {
      ordered.push(key.key)
    }
  }
  for (const key of keys) {
    if (allowed.has(key as AdminPermissionKey) && !ordered.includes(key)) {
      ordered.push(key)
    }
  }
  return ordered
}

function emitSelection(next: string[]) {
  emit('update:modelValue', normalizeSelection(next))
}

function isSelected(key: AdminPermissionKey): boolean {
  return selectedSet.value.has(key)
}

function toggleOpen() {
  if (props.disabled) {
    return
  }
  open.value = !open.value
}

function togglePermission(key: AdminPermissionKey) {
  if (props.disabled) {
    return
  }
  const next = [...props.modelValue]
  const index = next.indexOf(key)
  if (index >= 0) {
    next.splice(index, 1)
  } else {
    next.push(key)
  }
  emitSelection(next)
}

function handleDocumentClick(event: MouseEvent) {
  const root = rootRef.value
  const target = event.target

  if (!open.value || !(target instanceof Node) || !root) {
    return
  }

  if (!root.contains(target)) {
    open.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleDocumentClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick)
})
</script>

<template>
  <div ref="rootRef" class="permission-picker">
    <button
      type="button"
      class="permission-picker__trigger input"
      :class="{ 'permission-picker__trigger--placeholder': !displayText }"
      :disabled="disabled"
      :aria-expanded="open"
      aria-haspopup="listbox"
      @click.stop="toggleOpen"
    >
      {{ displayText || placeholder }}
    </button>

    <div
      v-show="open"
      class="permission-picker__panel"
      role="listbox"
      aria-multiselectable="true"
      @click.stop
    >
      <label
        v-for="option in ADMIN_PERMISSION_OPTIONS"
        :key="option.key"
        class="permission-picker__option"
        :class="{ 'permission-picker__option--selected': isSelected(option.key) }"
      >
        <input
          class="permission-picker__checkbox"
          type="checkbox"
          :checked="isSelected(option.key)"
          :disabled="disabled"
          @change="togglePermission(option.key)"
        />
        <span class="permission-picker__copy">
          <span class="permission-picker__label">{{ option.label }}</span>
          <span class="permission-picker__key">{{ option.key }}</span>
          <span class="permission-picker__desc">{{ option.description }}</span>
        </span>
      </label>
    </div>
  </div>
</template>

<style scoped>
.permission-picker {
  position: relative;
  width: 100%;
}

.permission-picker__trigger {
  display: block;
  width: 100%;
  text-align: left;
  cursor: pointer;
  box-shadow: none;
  font-weight: 500;
}

.permission-picker__trigger--placeholder {
  color: var(--input-placeholder);
  font-weight: 400;
}

.permission-picker__trigger:disabled {
  opacity: 0.56;
  cursor: not-allowed;
}

.permission-picker__panel {
  position: absolute;
  z-index: 20;
  top: calc(100% + 0.35rem);
  left: 0;
  right: 0;
  max-height: min(16rem, 50vh);
  overflow-y: auto;
  padding: 0.35rem;
  border: 1px solid var(--popover-border, var(--border));
  border-radius: var(--radius-md, 14px);
  background: var(--popover-bg, var(--bg-strong));
  color: var(--popover-text, var(--text));
  box-shadow: var(--popover-shadow, var(--shadow-soft));
}

.permission-picker__option {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
  padding: 0.65rem 0.75rem;
  border-radius: var(--radius-sm, 10px);
  cursor: pointer;
  transition: background 0.15s ease;
}

.permission-picker__option:hover {
  background: rgba(var(--accent-1-rgb), 0.06);
}

.permission-picker__option--selected {
  background: rgba(var(--accent-1-rgb), 0.08);
}

.permission-picker__checkbox {
  margin-top: 0.2rem;
  width: 1rem;
  height: 1rem;
  flex-shrink: 0;
  accent-color: var(--primary);
  cursor: pointer;
}

.permission-picker__copy {
  display: grid;
  gap: 0.15rem;
  min-width: 0;
}

.permission-picker__label {
  color: var(--heading);
  font-weight: 600;
  font-size: 0.92rem;
}

.permission-picker__key {
  font-family: var(--font-mono, monospace);
  font-size: 0.78rem;
  color: var(--text-muted);
}

.permission-picker__desc {
  font-size: 0.8rem;
  color: var(--text-muted);
  line-height: 1.4;
}
</style>
