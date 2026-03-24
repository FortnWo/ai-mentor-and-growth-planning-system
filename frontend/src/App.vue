<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <header class="app-header">
    <span class="brand">🎓 AI Mentor</span>
    <nav>
      <RouterLink to="/chat">Chat</RouterLink>
      <RouterLink to="/profile">Profile</RouterLink>
      <RouterLink to="/plan">Growth Plan</RouterLink>
    </nav>
  </header>

  <main>
    <RouterView />
  </main>
</template>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  gap: 2rem;
  padding: 0.75rem 1.5rem;
  background: #1a56db;
  color: white;
}
.brand { font-weight: 700; font-size: 1.1rem; }
nav { display: flex; gap: 1rem; }
nav a { color: rgba(255,255,255,0.85); text-decoration: none; font-weight: 500; }
nav a:hover, nav a.router-link-active { color: white; text-decoration: underline; }
main { padding: 0.5rem; }
</style>
