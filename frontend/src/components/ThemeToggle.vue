<script setup lang="ts">
import { computed } from 'vue'

import { useTheme } from '../composables/useTheme'

const { isDark, toggleTheme } = useTheme()

const label = computed(() => (isDark.value ? '切换到浅色模式' : '切换到深色模式'))
</script>

<template>
  <button
    class="button button--ghost theme-toggle"
    type="button"
    :aria-label="label"
    :title="label"
    @click="toggleTheme"
  >
    <svg v-if="isDark" class="theme-toggle__icon" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="2" />
      <path
        fill="none"
        stroke="currentColor"
        stroke-linecap="round"
        stroke-width="2"
        d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"
      />
    </svg>
    <svg v-else class="theme-toggle__icon" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="none"
        stroke="currentColor"
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"
      />
    </svg>
  </button>
</template>

<style scoped>
.theme-toggle {
  color: var(--heading);
  min-height: 40px;
  padding-inline: 0.75rem;
}

.theme-toggle:hover {
  border-color: rgba(var(--accent-1-rgb), 0.24);
  background: rgba(var(--accent-1-rgb), 0.08);
}

.theme-toggle__icon {
  width: 1.25rem;
  height: 1.25rem;
  flex-shrink: 0;
}
</style>
