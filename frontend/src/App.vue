<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { useRouter } from 'vue-router'

import { authState, clearAuthSession, isAdmin, loadStoredAuthState, refreshCurrentUser } from './stores/auth'

const router = useRouter()
const mobileMenuOpen = ref(false)

const authenticated = computed(() => Boolean(authState.token))
const admin = computed(() => isAdmin(authState.user))
const userLabel = computed(() => authState.user?.full_name || authState.user?.username || 'User')
const navigationItems = computed(() => {
  if (!authenticated.value) {
    return [{ to: '/login', label: 'Login' }]
  }

  return [
    { to: '/chat', label: 'Chat' },
    { to: '/profile', label: 'Profile' },
    { to: '/plan', label: 'Growth Plan' },
    ...(admin.value ? [{ to: '/admin/users', label: 'Admin Users' }] : []),
  ]
})

function closeMobileMenu() {
  mobileMenuOpen.value = false
}

onMounted(async () => {
  loadStoredAuthState()
  if (authState.token && !authState.user) {
    await refreshCurrentUser()
  }
})

async function logout() {
  clearAuthSession()
  closeMobileMenu()
  await router.push('/login')
}
</script>

<template>
  <div class="app-shell">
    <header class="app-header glass-card">
      <RouterLink class="brand" to="/chat" @click="closeMobileMenu">
        <span class="brand-mark">
          AI
        </span>
        <span class="brand-copy">
          <strong>AI Mentor</strong>
          <small>{{ authenticated ? userLabel : 'Growth planning studio' }}</small>
        </span>
      </RouterLink>

      <div v-if="authenticated" class="header-status">
        <span class="status-dot"></span>
        <span>{{ admin ? 'Admin access' : 'Student workspace' }}</span>
      </div>

      <nav class="desktop-nav" :class="{ 'desktop-nav--guest': !authenticated }">
        <RouterLink
          v-for="item in navigationItems"
          :key="item.to"
          :to="item.to"
          class="nav-link"
          @click="closeMobileMenu"
        >
          {{ item.label }}
        </RouterLink>

        <button v-if="authenticated" class="button button--ghost nav-button" type="button" @click="logout">
          Logout
        </button>
      </nav>

      <div class="header-actions">
        <RouterLink v-if="!authenticated" class="button button--primary login-button" to="/login" @click="closeMobileMenu">
          Login
        </RouterLink>

        <button class="menu-toggle button button--ghost" type="button" @click="mobileMenuOpen = !mobileMenuOpen">
          <span aria-hidden="true">☰</span>
          <span>Menu</span>
        </button>
      </div>
    </header>

    <transition name="fade-slide">
      <div v-if="mobileMenuOpen" class="mobile-menu glass-card">
        <div class="mobile-menu__top">
          <span class="eyebrow">Navigation</span>
          <button class="button button--ghost mobile-close" type="button" @click="closeMobileMenu">
            ×
          </button>
        </div>

        <RouterLink
          v-for="item in navigationItems"
          :key="item.to"
          :to="item.to"
          class="mobile-link"
          @click="closeMobileMenu"
        >
          {{ item.label }}
        </RouterLink>

        <button v-if="authenticated" class="button button--primary mobile-logout" type="button" @click="logout">
          Logout
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
  color: #eff6ff;
  background: linear-gradient(135deg, rgba(6, 182, 212, 0.95), rgba(37, 99, 235, 0.95));
  box-shadow: 0 18px 28px rgba(6, 182, 212, 0.18);
}

.brand-copy {
  display: grid;
  gap: 0.12rem;
  text-align: left;
}

.brand-copy strong {
  color: #f8fbff;
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
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.56);
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
  color: #f8fbff;
  border-color: rgba(6, 182, 212, 0.24);
  background: rgba(6, 182, 212, 0.08);
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

  .mobile-close {
    min-height: 38px;
    padding-inline: 0.85rem;
  }

  .mobile-link {
    display: block;
    padding: 0.85rem 1rem;
    border-radius: 16px;
    border: 1px solid rgba(148, 163, 184, 0.14);
    background: rgba(15, 23, 42, 0.55);
    color: #d8e7f7;
  }

  .mobile-link.router-link-active {
    border-color: rgba(6, 182, 212, 0.24);
    background: rgba(6, 182, 212, 0.08);
  }

  .mobile-logout {
    width: 100%;
  }
}
</style>
