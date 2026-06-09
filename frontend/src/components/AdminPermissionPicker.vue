<script lang="ts">
export default {
  name: 'AdminPermissionPicker',
}
</script>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import type { AdminPermissionLevel } from '../api/user'
import {
  ADMIN_PERMISSION_OPTIONS,
  type AdminPermissionKey,
} from '../constants/adminPermissions'

const props = withDefaults(
  defineProps<{
    level: AdminPermissionLevel
    permissions: string[]
    disabled?: boolean
    placeholder?: string
  }>(),
  {
    disabled: false,
    placeholder: '选择权限…',
  },
)

const emit = defineEmits<{
  'update:level': [value: AdminPermissionLevel]
  'update:permissions': [value: string[]]
}>()

const rootRef = ref<HTMLElement | null>(null)
const open = ref(false)

const selectedSet = computed(() => new Set(props.permissions))

const displayText = computed(() => {
  if (!props.permissions.length) {
    return ''
  }
  return props.permissions.join(', ')
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
  emit('update:permissions', normalizeSelection(next))
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
  const next = [...props.permissions]
  const index = next.indexOf(key)
  if (index >= 0) {
    next.splice(index, 1)
  } else {
    next.push(key)
  }
  emitSelection(next)
}

function handleLevelChange(event: Event) {
  const target = event.target
  if (!(target instanceof HTMLSelectElement)) {
    return
  }
  const value = target.value
  if (value === 'full' || value === 'limited') {
    emit('update:level', value)
  }
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
  <div class="admin-permission-picker">
    <label class="admin-permission-picker__level-field">
      <span class="admin-permission-picker__label">管理员权限级别</span>
      <select
        class="admin-permission-picker__level-select input"
        :value="level"
        :disabled="disabled"
        @change="handleLevelChange"
      >
        <option value="full">完整</option>
        <option value="limited">有限</option>
      </select>
    </label>

    <div v-if="level === 'limited'" ref="rootRef" class="permission-picker">
      <span class="admin-permission-picker__label">管理员权限键</span>
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

    <p v-else class="admin-permission-picker__hint">
      完整权限包含全部操作，无需单独勾选。
    </p>
  </div>
</template>

<style scoped>
.admin-permission-picker {
  display: grid;
  gap: 0.85rem;
}

.admin-permission-picker__level-field {
  display: grid;
  gap: 0.35rem;
}

.admin-permission-picker__label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--heading);
}

.admin-permission-picker__level-select {
  width: 100%;
}

.admin-permission-picker__hint {
  margin: 0;
  font-size: 0.82rem;
  color: var(--text-muted);
  line-height: 1.45;
}

.permission-picker {
  position: relative;
  width: 100%;
  display: grid;
  gap: 0.35rem;
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
