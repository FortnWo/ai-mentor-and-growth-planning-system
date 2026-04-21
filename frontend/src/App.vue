<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { useRouter } from 'vue-router'

import { authState, clearAuthSession, isAdmin, loadStoredAuthState, refreshCurrentUser } from './stores/auth'

const router = useRouter()

const authenticated = computed(() => Boolean(authState.token))
const admin = computed(() => isAdmin(authState.user))
const userLabel = computed(() => authState.user?.full_name || authState.user?.username || 'User')

onMounted(async () => {
  loadStoredAuthState()
  if (authState.token && !authState.user) {
    await refreshCurrentUser()
  }
})

async function logout() {
  clearAuthSession()
  await router.push('/login')
}
</script>

<template>
  <header class="app-header">
    <div class="brand-group">
      <span class="brand">AI Mentor</span>
      <small v-if="authenticated" class="identity">
        {{ userLabel }}
      </small>
    </div>

    <nav v-if="authenticated">
      <RouterLink to="/chat">Chat</RouterLink>
      <RouterLink to="/profile">My Profile</RouterLink>
      <RouterLink to="/plan">Growth Plan</RouterLink>
      <RouterLink v-if="admin" to="/admin/users">Admin Users</RouterLink>
      <button class="logout" type="button" @click="logout">Logout</button>
    </nav>

    <nav v-else>
      <RouterLink to="/login">Login</RouterLink>
    </nav>
  </header>

  <main>
    <RouterView />
  </main>
</template>

<style scoped>
.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1.5rem;
  background: #0f172a;
  color: #f8fafc;
}

.brand-group {
  display: flex;
  flex-direction: column;
}

.brand {
  font-weight: 700;
  font-size: 1.1rem;
}

.identity {
  opacity: 0.8;
}

nav {
  display: flex;
  align-items: center;
  gap: 1rem;
}

nav a {
  color: rgba(255, 255, 255, 0.85);
  text-decoration: none;
  font-weight: 500;
}

nav a:hover,
nav a.router-link-active {
  color: white;
  text-decoration: underline;
}

.logout {
  border: 1px solid rgba(255, 255, 255, 0.35);
  background: transparent;
  color: #f8fafc;
  border-radius: 6px;
  padding: 0.4rem 0.65rem;
  cursor: pointer;
}

main {
  padding: 0.5rem;
}

@media (max-width: 900px) {
  .app-header {
    flex-direction: column;
    align-items: flex-start;
  }

  nav {
    flex-wrap: wrap;
  }
}
</style>
