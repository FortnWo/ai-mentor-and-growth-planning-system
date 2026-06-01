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
      <path
        fill="currentColor"
        d="M12 18a6 6 0 1 0 0-12 6 6 0 0 0 0 12Zm0 4a1 1 0 0 1-1-1v-1.05a1 1 0 1 1 2 0V21a1 1 0 0 1-1 1Zm0-17a1 1 0 0 1-1-1V2.9a1 1 0 1 1 2 0V4a1 1 0 0 1-1 1ZM4.22 19.78a1 1 0 0 1-1.41-1.41l.74-.74a1 1 0 0 1 1.41 1.41l-.74.74ZM19.78 19.78l-.74-.74a1 1 0 0 1 1.41-1.41l.74.74a1 1 0 0 1-1.41 1.41ZM2.9 13a1 1 0 1 1 0-2H4a1 1 0 1 1 0 2H2.9Zm17.1 0a1 1 0 1 1 0-2h1.1a1 1 0 1 1 0 2H20ZM6.34 17.66a1 1 0 0 1-1.41 0l-.74-.74a1 1 0 0 1 1.41-1.41l.74.74a1 1 0 0 1 0 1.41Zm12.02-12.02a1 1 0 0 1-1.41 0l-.74-.74a1 1 0 1 1 1.41-1.41l.74.74a1 1 0 0 1 0 1.41ZM6.34 6.34a1 1 0 0 1 0-1.41l.74-.74a1 1 0 0 1 1.41 1.41l-.74.74a1 1 0 0 1-1.41 0Z"
      />
    </svg>
    <svg v-else class="theme-toggle__icon" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M21 14.5A7.5 7.5 0 0 1 9.5 3 6.5 6.5 0 1 0 21 14.5Z"
      />
    </svg>
    <span class="theme-toggle__label">{{ isDark ? '浅色' : '深色' }}</span>
  </button>
</template>

<style scoped>
.theme-toggle {
  min-height: 40px;
  padding-inline: 0.85rem;
}

.theme-toggle__icon {
  width: 1.1rem;
  height: 1.1rem;
  flex-shrink: 0;
}

.theme-toggle__label {
  font-size: 0.88rem;
}

@media (max-width: 1024px) {
  .theme-toggle__label {
    display: none;
  }
}
</style>
