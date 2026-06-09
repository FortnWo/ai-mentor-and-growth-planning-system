<script lang="ts">
export default {
  name: 'AdminPermissionCheckboxes',
}
</script>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  ADMIN_PERMISSION_OPTIONS,
  type AdminPermissionKey,
} from '../constants/adminPermissions'

const props = withDefaults(
  defineProps<{
    modelValue: AdminPermissionKey[]
    disabled?: boolean
    excludeKeys?: AdminPermissionKey[]
    compact?: boolean
    popover?: boolean
    triggerLabel?: string
  }>(),
  {
    disabled: false,
    excludeKeys: () => [],
    compact: true,
    popover: false,
    triggerLabel: '权限',
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: AdminPermissionKey[]]
}>()

const rootRef = ref<HTMLElement | null>(null)
const open = ref(false)

const visibleOptions = computed(() =>
  ADMIN_PERMISSION_OPTIONS.filter((option) => !props.excludeKeys.includes(option.key)),
)

const selectedSet = computed(() => new Set(props.modelValue))

const triggerSummary = computed(() => {
  if (!props.modelValue.length) {
    return '未选择'
  }
  const labels = props.modelValue
    .map((key) => visibleOptions.value.find((option) => option.key === key)?.label ?? key)
    .join('、')
  return labels.length > 18 ? `${labels.slice(0, 18)}…` : labels
})

function normalizeSelection(keys: string[]): AdminPermissionKey[] {
  const allowed = new Set(ADMIN_PERMISSION_OPTIONS.map((option) => option.key))
  const ordered: AdminPermissionKey[] = []
  for (const option of ADMIN_PERMISSION_OPTIONS) {
    if (keys.includes(option.key) && allowed.has(option.key)) {
      ordered.push(option.key)
    }
  }
  return ordered
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
  emit('update:modelValue', normalizeSelection(next))
}

function togglePopover() {
  if (props.disabled) {
    return
  }
  open.value = !open.value
}

function handleDocumentClick(event: MouseEvent) {
  if (!props.popover || !open.value) {
    return
  }
  const root = rootRef.value
  const target = event.target
  if (!root || !(target instanceof Node) || root.contains(target)) {
    return
  }
  open.value = false
}

onMounted(() => {
  document.addEventListener('click', handleDocumentClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick)
})
</script>

<template>
  <div
    ref="rootRef"
    class="perm-checkboxes"
    :class="{
      'perm-checkboxes--compact': compact,
      'perm-checkboxes--popover': popover,
    }"
  >
    <button
      v-if="popover"
      type="button"
      class="perm-checkboxes__trigger"
      :disabled="disabled"
      :aria-expanded="open"
      aria-haspopup="listbox"
      @click.stop="togglePopover"
    >
      <span class="perm-checkboxes__trigger-label">{{ triggerLabel }}</span>
      <span class="perm-checkboxes__trigger-summary">{{ triggerSummary }}</span>
      <span class="perm-checkboxes__trigger-caret" aria-hidden="true">{{ open ? '▴' : '▾' }}</span>
    </button>

    <div
      v-show="!popover || open"
      class="perm-checkboxes__panel"
      :class="{ 'perm-checkboxes__panel--floating': popover }"
      role="listbox"
      aria-multiselectable="true"
      @click.stop
    >
      <label
        v-for="option in visibleOptions"
        :key="option.key"
        class="perm-checkboxes__item"
        :class="{ 'perm-checkboxes__item--selected': selectedSet.has(option.key) }"
      >
        <input
          type="checkbox"
          class="perm-checkboxes__input"
          :checked="selectedSet.has(option.key)"
          :disabled="disabled"
          @change="togglePermission(option.key)"
        />
        <span class="perm-checkboxes__copy">
          <span class="perm-checkboxes__label">{{ option.label }}</span>
          <span v-if="!compact" class="perm-checkboxes__desc">{{ option.description }}</span>
        </span>
      </label>
    </div>
  </div>
</template>

<style scoped>
.perm-checkboxes {
  display: grid;
  gap: 0.35rem;
  min-width: 8.5rem;
}

.perm-checkboxes--popover {
  position: relative;
  min-width: 0;
}

.perm-checkboxes--compact .perm-checkboxes__item {
  padding: 0.2rem 0;
}

.perm-checkboxes__trigger {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  width: 100%;
  padding: 0.35rem 0.5rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 10px);
  background: var(--surface);
  color: var(--text);
  font-size: 0.78rem;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.perm-checkboxes__trigger:hover:not(:disabled) {
  border-color: rgba(var(--accent-1-rgb), 0.35);
  background: rgba(var(--accent-1-rgb), 0.05);
}

.perm-checkboxes__trigger:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.perm-checkboxes__trigger-label {
  flex-shrink: 0;
  font-weight: 600;
  color: var(--heading);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-size: 0.72rem;
}

.perm-checkboxes__trigger-summary {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-muted);
}

.perm-checkboxes__trigger-caret {
  flex-shrink: 0;
  font-size: 0.65rem;
  color: var(--text-muted);
}

.perm-checkboxes__panel--floating {
  position: absolute;
  z-index: 40;
  top: calc(100% + 0.35rem);
  left: 0;
  right: 0;
  min-width: 12rem;
  max-height: min(16rem, 50vh);
  overflow-y: auto;
  padding: 0.35rem;
  border: 1px solid var(--popover-border, var(--border));
  border-radius: var(--radius-md, 14px);
  background: var(--popover-bg, var(--bg-strong));
  box-shadow: var(--popover-shadow, var(--shadow-soft));
}

.perm-checkboxes__item {
  display: flex;
  align-items: flex-start;
  gap: 0.4rem;
  padding: 0.45rem 0.5rem;
  border-radius: var(--radius-sm, 10px);
  cursor: pointer;
  font-size: 0.78rem;
  color: var(--text-muted);
  transition: background 0.15s ease;
}

.perm-checkboxes__item:hover {
  background: rgba(var(--accent-1-rgb), 0.06);
}

.perm-checkboxes__item--selected {
  color: var(--heading);
  background: rgba(var(--accent-1-rgb), 0.08);
}

.perm-checkboxes__input {
  margin-top: 0.15rem;
  width: 0.85rem;
  height: 0.85rem;
  flex-shrink: 0;
  accent-color: var(--primary);
  cursor: pointer;
}

.perm-checkboxes__copy {
  display: grid;
  gap: 0.1rem;
  min-width: 0;
}

.perm-checkboxes__label {
  line-height: 1.2;
  font-weight: 600;
}

.perm-checkboxes__desc {
  font-size: 0.72rem;
  line-height: 1.35;
  color: var(--text-muted);
}
</style>
