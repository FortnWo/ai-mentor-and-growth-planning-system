<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { useRouter } from 'vue-router'

import ThemeToggle from './components/ThemeToggle.vue'
import {
  authState,
  clearAuthSession,
  hasAdminPermission,
  isFullAdmin,
  isLimitedAdmin,
  loadStoredAuthState,
  refreshCurrentUser,
} from './stores/auth'

const router = useRouter()
const mobileMenuOpen = ref(false)
const glowX = ref(0)
const glowY = ref(0)
const glowVisible = ref(false)

const authenticated = computed(() => Boolean(authState.token))
const fullAdmin = computed(() => isFullAdmin(authState.user))
const limitedAdmin = computed(() => isLimitedAdmin(authState.user))
const userLabel = computed(() => authState.user?.full_name || authState.user?.username || 'User')

const studentNavigationItems = [
  { to: '/chat', label: '聊天' },
  { to: '/profile', label: '用户画像' },
  { to: '/plan', label: '目标计划' },
  { to: '/growth', label: '成长记录' },
  { to: '/info', label: '我的资料' },
]

const navigationItems = computed(() => {
  if (!authenticated.value) {
    return [{ to: '/login', label: '登录' }]
  }

  if (fullAdmin.value) {
    return [
      { to: '/chat', label: '管理助手' },
      { to: '/admin/users', label: '用户管理' },
      { to: '/admin/system', label: '系统维护' },
      { to: '/info', label: '我的资料' },
    ]
  }

  const items = [...studentNavigationItems]
  if (limitedAdmin.value && hasAdminPermission(authState.user, 'user.read')) {
    items.splice(1, 0, { to: '/admin/users', label: '用户管理' })
  }
  return items
})

const headerStatusLabel = computed(() => {
  if (fullAdmin.value) return '管理员权限'
  if (limitedAdmin.value) return '临时管理权限'
  return '学生工作台'
})

function closeMobileMenu() {
  mobileMenuOpen.value = false
}

function updateGlowPosition(event: PointerEvent) {
  glowX.value = event.clientX
  glowY.value = event.clientY
  glowVisible.value = true
}

function hideGlow() {
  glowVisible.value = false
}

onMounted(async () => {
  loadStoredAuthState()
  if (authState.token && !authState.user) {
    await refreshCurrentUser()
  }

  window.addEventListener('pointermove', updateGlowPosition)
  window.addEventListener('pointerdown', updateGlowPosition)
  window.addEventListener('blur', hideGlow)
})

onBeforeUnmount(() => {
  window.removeEventListener('pointermove', updateGlowPosition)
  window.removeEventListener('pointerdown', updateGlowPosition)
  window.removeEventListener('blur', hideGlow)
})

async function logout() {
  clearAuthSession()
  closeMobileMenu()
  await router.push('/login')
}
</script>

<template>
  <div class="app-shell">
    <div class="pointer-glow" :class="{ 'is-visible': glowVisible }"
      :style="{ '--glow-x': `${glowX}px`, '--glow-y': `${glowY}px` }"></div>

    <div class="ambient-orb"></div>

    <header class="app-header glass-card">
      <RouterLink class="brand" to="/home" @click="closeMobileMenu">
        <span class="brand-mark">
          AI
        </span>
        <span class="brand-copy">
          <strong>AI Mentor</strong>
          <small>{{ authenticated ? userLabel : '成长规划工作台' }}</small>
        </span>
      </RouterLink>

      <div v-if="authenticated" class="header-status">
        <span class="status-dot"></span>
        <span>{{ headerStatusLabel }}</span>
      </div>

      <nav class="desktop-nav" :class="{ 'desktop-nav--guest': !authenticated }">
        <RouterLink v-for="item in navigationItems" :key="item.to" :to="item.to" class="nav-link"
          @click="closeMobileMenu">
          {{ item.label }}
        </RouterLink>

        <ThemeToggle />

        <button v-if="authenticated" class="button button--ghost nav-button" type="button" @click="logout">
          退出登录
        </button>
      </nav>

      <div class="header-actions">
        <ThemeToggle />

        <RouterLink v-if="!authenticated" class="button button--primary login-button" to="/login"
          @click="closeMobileMenu">
          登录
        </RouterLink>

        <button class="menu-toggle button button--ghost" type="button" @click="mobileMenuOpen = !mobileMenuOpen">
          <span aria-hidden="true">☰</span>
          <span>菜单</span>
        </button>
      </div>
    </header>

    <transition name="fade-slide">
      <div v-if="mobileMenuOpen" class="mobile-menu glass-card">
        <div class="mobile-menu__top">
          <span class="eyebrow">导航</span>
          <div class="mobile-menu__top-actions">
            <ThemeToggle />
            <button class="button button--ghost mobile-close" type="button" @click="closeMobileMenu">
              ×
            </button>
          </div>
        </div>

        <RouterLink v-for="item in navigationItems" :key="item.to" :to="item.to" class="mobile-link"
          @click="closeMobileMenu">
          {{ item.label }}
        </RouterLink>

        <button v-if="authenticated" class="button button--primary mobile-logout" type="button" @click="logout">
          退出登录
        </button>
      </div>
    </transition>

    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  position: sticky;
  top: 1rem;
  z-index: 30;
  padding: 0.9rem 1rem;
  border-radius: 24px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  min-width: 0;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 2.8rem;
  height: 2.8rem;
  border-radius: 18px;
  color: var(--button-text);
  background: linear-gradient(135deg, var(--primary), var(--accent));
  box-shadow: 0 18px 28px rgba(var(--accent-1-rgb), 0.18);
}

.brand-copy {
  display: grid;
  gap: 0.12rem;
  text-align: left;
}

.brand-copy strong {
  color: var(--heading);
  font-family: var(--font-display);
  letter-spacing: -0.03em;
}

.brand-copy small,
.header-status {
  color: var(--text-muted);
}

.header-status {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.55rem 0.8rem;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
}

.status-dot {
  width: 0.55rem;
  height: 0.55rem;
  border-radius: 999px;
  background: linear-gradient(135deg, var(--primary), #34d399);
  box-shadow: 0 0 0 6px rgba(6, 182, 212, 0.14);
}

.desktop-nav {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.7rem;
}

.nav-link {
  padding: 0.68rem 0.95rem;
  border: 1px solid transparent;
  border-radius: 999px;
  color: var(--text-muted);
  transition:
    color 0.2s ease,
    border-color 0.2s ease,
    background 0.2s ease,
    transform 0.2s ease;
}

.nav-link:hover,
.nav-link.router-link-active {
  color: var(--nav-active-text);
  border-color: rgba(var(--accent-1-rgb), 0.24);
  background: rgba(var(--accent-1-rgb), 0.08);
  transform: translateY(-1px);
}

.nav-button {
  min-height: 40px;
}

.header-actions {
  display: none;
  align-items: center;
  gap: 0.7rem;
}

.menu-toggle {
  display: none;
  min-height: 42px;
}

.login-button {
  min-height: 42px;
}

.mobile-menu {
  display: none;
}

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

@media (max-width: 1024px) {
  .app-header {
    position: relative;
    top: 0;
    padding: 0.9rem;
  }

  .header-status,
  .desktop-nav {
    display: none;
  }

  .header-actions {
    display: flex;
  }

  .menu-toggle {
    display: inline-flex;
  }

  .mobile-menu {
    display: grid;
    gap: 0.7rem;
    margin-top: 0.9rem;
    padding: 1rem;
    border-radius: 24px;
  }

  .mobile-menu__top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .mobile-menu__top-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .mobile-close {
    min-height: 38px;
    padding-inline: 0.85rem;
  }

  .mobile-link {
    display: block;
    padding: 0.85rem 1rem;
    border-radius: 16px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text);
  }

  .mobile-link.router-link-active {
    border-color: rgba(var(--accent-1-rgb), 0.24);
    background: rgba(var(--accent-1-rgb), 0.08);
    color: var(--nav-active-text);
  }

  .mobile-logout {
    width: 100%;
  }
}
</style>
