import { computed, ref } from 'vue'

export type Theme = 'light' | 'dark'

export const STORAGE_KEY = 'ai-mentor-theme'

const theme = ref<Theme>('light')

function readStoredTheme(): Theme | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'light' || stored === 'dark') {
      return stored
    }
  } catch {
    /* ignore */
  }
  return null
}

export function applyTheme(next: Theme) {
  theme.value = next
  document.documentElement.setAttribute('data-theme', next)
}

export function initTheme() {
  const stored = readStoredTheme()
  applyTheme(stored ?? 'light')
}

export function setTheme(next: Theme) {
  applyTheme(next)
  try {
    localStorage.setItem(STORAGE_KEY, next)
  } catch {
    /* ignore */
  }
}

export function toggleTheme() {
  setTheme(theme.value === 'light' ? 'dark' : 'light')
}

export function useTheme() {
  const isDark = computed(() => theme.value === 'dark')

  return {
    theme,
    isDark,
    setTheme,
    toggleTheme,
  }
}
