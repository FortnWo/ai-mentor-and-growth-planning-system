<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { useRoute, useRouter } from 'vue-router'

import { authState, clearAuthSession, isAdmin, loadStoredAuthState, refreshCurrentUser } from './stores/auth'

const router = useRouter()
const route = useRoute()
const mobileMenuOpen = ref(false)
const glowX = ref(0)
const glowY = ref(0)
const glowVisible = ref(false)

const authenticated = computed(() => Boolean(authState.token))
const admin = computed(() => isAdmin(authState.user))
const userLabel = computed(() => authState.user?.full_name || authState.user?.username || 'User')
const workspaceTitle = computed(() => {
  if (route.path === '/chat') {
    return '对话工作台'
  }

  if (route.path === '/growth') {
    return '成长记录工作台'
  }

  if (route.path === '/profile/extended') {
    return '扩展画像实验室'
  }

  if (route.path === '/profile') {
    return '身份信息工作台'
  }

  if (route.path === '/plan') {
    return '成长路线图'
  }

  if (route.path.startsWith('/admin')) {
    return '管理控制台'
  }

  return 'AI 导师工作台'
})
const workspaceSubtitle = computed(() => {
  if (route.path === '/chat') {
    return '整理会话、对照上下文，让对话流保持安静而清晰。'
  }

  if (route.path === '/growth') {
    return '记录每一个小进步，回看成长轨迹，让成长痕迹始终可见。'
  }

  if (route.path === '/profile/extended') {
    return '通过手动编辑与聊天抽取，持续整理兴趣、技能、习惯和目标。'
  }

  if (route.path === '/profile') {
    return '查看你的身份概览，让资料保持干净、聚焦、及时更新。'
  }

  if (route.path === '/plan') {
    return '面向未来的规划入口，带着更清晰的目标感与成长信号。'
  }

  if (route.path.startsWith('/admin')) {
    return '高密度管理界面，让审核与控制更快、更稳。'
  }

  return '一个具有层次感与动效氛围的玻璃风工作台。'
})
const navigationItems = computed(() => {
  if (!authenticated.value) {
    return [{ to: '/login', label: '登录' }]
  }

  return [
    { to: '/chat', label: '聊天' },
    { to: '/profile', label: '我的资料' },
    { to: '/profile/extended', label: '扩展画像' },
    { to: '/plan', label: '成长计划' },
    { to: '/growth', label: '成长记录' },
    ...(admin.value ? [{ to: '/admin/users', label: '用户管理' }] : []),
  ]
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
      <RouterLink class="brand" to="/chat" @click="closeMobileMenu">
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
        <span>{{ admin ? '管理员权限' : '学生工作台' }}</span>
      </div>

      <nav class="desktop-nav" :class="{ 'desktop-nav--guest': !authenticated }">
        <RouterLink v-for="item in navigationItems" :key="item.to" :to="item.to" class="nav-link"
          @click="closeMobileMenu">
          {{ item.label }}
        </RouterLink>

        <button v-if="authenticated" class="button button--ghost nav-button" type="button" @click="logout">
          退出登录
        </button>
      </nav>

      <div class="header-actions">
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
          <button class="button button--ghost mobile-close" type="button" @click="closeMobileMenu">
            ×
          </button>
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
      <section v-if="authenticated" class="hero-frame glass-card panel app-hero reveal">
        <div class="app-hero__copy">
          <p class="page-kicker">{{ workspaceTitle }}</p>
          <h1 class="page-title">{{ workspaceSubtitle }}</h1>
          <p class="page-subtitle">
            {{
              admin
                ? 'Administrative access enabled. The control surface is tuned for speed and clarity.'
                : 'Your workspace is ready. Move between mentoring, profile, and planning with a stronger visual rhythm.'
            }}
          </p>

          <div class="hero-actions">
            <RouterLink class="button button--primary" to="/chat">打开聊天</RouterLink>
            <RouterLink class="button button--ghost" to="/plan">查看计划</RouterLink>
            <RouterLink class="button button--ghost" to="/growth">Growth Records</RouterLink>
          </div>
        </div>

        <div class="hero-visual">
          <div class="hero-visual__stage">
            <div class="hero-visual__ring">
              <div class="hero-visual__core"></div>
            </div>
          </div>

          <div class="hero-floating">
            <article class="hero-floating__card">
              <p class="hero-floating__label">工作区</p>
              <p class="hero-floating__value">在线</p>
              <p class="hero-floating__trend">带有动效层次的动态布局</p>
            </article>

            <article class="hero-floating__card">
              <p class="hero-floating__label">角色</p>
              <p class="hero-floating__value">{{ admin ? '管理员' : '学生' }}</p>
              <p class="hero-floating__trend">{{ admin ? '管理权限与用户' : '与 AI 一起规划和聊天' }}</p>
            </article>

            <article class="hero-floating__card">
              <p class="hero-floating__label">状态</p>
              <p class="hero-floating__value">已同步</p>
              <p class="hero-floating__trend">CORS 与接口路由已连接</p>
            </article>

            <article class="hero-floating__card">
              <p class="hero-floating__label">动效</p>
              <p class="hero-floating__value">开启</p>
              <p class="hero-floating__trend">光晕、漂移与渐显动画</p>
            </article>
          </div>
        </div>
      </section>

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
