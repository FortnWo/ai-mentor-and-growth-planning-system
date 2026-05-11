<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

export type CompactActionTone = 'default' | 'danger'

export interface CompactActionMenuItem {
  key: string
  label: string
  tone?: CompactActionTone
  disabled?: boolean
}

const props = withDefaults(
  defineProps<{
    items: CompactActionMenuItem[]
    ariaLabel?: string
  }>(),
  {
    ariaLabel: '打开操作菜单',
  },
)

const emit = defineEmits<{
  select: [key: string]
}>()

const menuRef = ref<HTMLDetailsElement | null>(null)

function closeMenu() {
  if (menuRef.value) {
    menuRef.value.open = false
  }
}

function selectItem(key: string) {
  emit('select', key)
  closeMenu()
}

function handleDocumentClick(event: MouseEvent) {
  const root = menuRef.value
  const target = event.target

  if (!root?.open || !(target instanceof Node)) {
    return
  }

  if (!root.contains(target)) {
    closeMenu()
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
  <details ref="menuRef" class="compact-action-menu">
    <summary class="button button--ghost compact-action-menu__trigger" :aria-label="props.ariaLabel">
      <span aria-hidden="true">⋯</span>
    </summary>

    <div class="compact-action-menu__panel">
      <button
        v-for="item in props.items"
        :key="item.key"
        :class="['compact-action-menu__item', item.tone === 'danger' && 'compact-action-menu__item--danger']"
        :disabled="item.disabled"
        type="button"
        @click="selectItem(item.key)"
      >
        {{ item.label }}
      </button>
    </div>
  </details>
</template>

<style scoped>
.compact-action-menu {
  position: relative;
  display: inline-flex;
  justify-content: flex-end;
}

.compact-action-menu__trigger {
  min-width: 2.4rem;
  min-height: 2.4rem;
  padding: 0;
  justify-content: center;
}

.compact-action-menu__trigger {
  list-style: none;
}

.compact-action-menu__trigger::-webkit-details-marker {
  display: none;
}

.compact-action-menu__panel {
  position: absolute;
  top: calc(100% + 0.45rem);
  right: 0;
  z-index: 20;
  display: grid;
  gap: 0.25rem;
  min-width: 9.5rem;
  padding: 0.45rem;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 16px;
  background: rgba(15, 23, 42, 0.95);
  box-shadow: 0 20px 40px rgba(2, 6, 23, 0.4);
  backdrop-filter: blur(20px);
}

.compact-action-menu__item {
  display: block;
  width: 100%;
  padding: 0.72rem 0.85rem;
  border: 0;
  border-radius: 12px;
  text-align: left;
  color: #d8e7f7;
  background: transparent;
  transition: background 0.2s ease, color 0.2s ease;
}

.compact-action-menu__item:hover:not(:disabled) {
  background: rgba(6, 182, 212, 0.08);
  color: #f8fbff;
}

.compact-action-menu__item--danger {
  color: #fecaca;
}

.compact-action-menu__item--danger:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.12);
  color: #fff1f2;
}

.compact-action-menu__item:disabled {
  cursor: not-allowed;
  opacity: 0.48;
}
</style>