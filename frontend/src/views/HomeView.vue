<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'

import ModuleDashboardTree from '../components/ModuleDashboardTree.vue'
import { useHomeDashboard } from '../composables/useHomeDashboard'
import {
  STUDENT_WORKSPACE_MODULES,
  type WorkspaceModuleId,
} from '../constants/workspaceModules'
import { authState, hasAdminPermission, isFullAdmin, isLimitedAdmin } from '../stores/auth'

const { loading, slicesById, refresh } = useHomeDashboard()

const expandedId = ref<WorkspaceModuleId | null>(null)

const userLabel = computed(() => authState.user?.full_name || authState.user?.username || '同学')
const fullAdmin = computed(() => isFullAdmin(authState.user))
const limitedAdmin = computed(() => isLimitedAdmin(authState.user))
const canManageUsers = computed(() => hasAdminPermission(authState.user, 'user.read'))

const ADMIN_QUICK_LINKS = [
  { to: '/admin/users', kicker: '用户管理', title: '用户账号管理', subtitle: '查看、注册、检索和批量管理学生账号。', icon: '👥' },
  { to: '/admin/system', kicker: '系统维护', title: '系统维护中心', subtitle: '配置 AI 参数、通知服务、查看日志与流量。', icon: '⚙️' },
  { to: '/chat', kicker: '管理助手', title: '管理员聊天', subtitle: '使用 AI 助手进行自然语言数据库查询与系统管理。', icon: '🤖' },
  { to: '/info', kicker: '个人信息', title: '我的资料', subtitle: '查看并编辑管理员账号信息与联系方式。', icon: '👤' },
]

function toggleModule(id: WorkspaceModuleId) {
  expandedId.value = expandedId.value === id ? null : id
}
</script>

<template>
  <div class="page page--wide home-page">
    <section class="hero-frame glass-card panel app-hero reveal">
      <div class="app-hero__copy">
        <p class="page-kicker">{{ fullAdmin ? '系统管理工作台' : 'AI 导师工作台' }}</p>
        <h1 class="page-title">欢迎回来，{{ userLabel }}。</h1>
        <p class="page-subtitle">
          {{
            fullAdmin
              ? '管理员权限已启用。可在此快速进入用户管理、系统维护或管理员聊天。'
              : limitedAdmin
                ? '你已获临时管理权限。可继续使用学生工作区，并按需进入用户管理。'
                : '在此总览聊天、画像、计划与成长记录。工作区已就绪，按你的节奏继续推进即可。'
          }}
        </p>

        <div class="hero-actions">
          <template v-if="fullAdmin">
            <RouterLink class="button button--primary" to="/admin/users">用户管理</RouterLink>
            <RouterLink class="button button--ghost" to="/admin/system">系统维护</RouterLink>
            <RouterLink class="button button--ghost" to="/chat">管理助手</RouterLink>
          </template>
          <template v-else>
            <RouterLink class="button button--primary" to="/chat">打开聊天</RouterLink>
            <RouterLink v-if="canManageUsers" class="button button--ghost" to="/admin/users">用户管理</RouterLink>
            <RouterLink class="button button--ghost" to="/plan">查看计划</RouterLink>
            <RouterLink class="button button--ghost" to="/growth">成长记录</RouterLink>
            <button class="button button--ghost" type="button" :disabled="loading" @click="refresh">
              刷新数据
            </button>
          </template>
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
            <p class="hero-floating__value">{{ fullAdmin ? '管理员' : limitedAdmin ? '临时管理员' : '学生' }}</p>
            <p class="hero-floating__trend">{{
              fullAdmin ? '系统全权管理访问' : limitedAdmin ? '学生工作区 + 管理入口' : '与 AI 一起规划和聊天'
            }}</p>
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

    <!-- ── 管理员工作台入口 ── -->
    <section v-if="fullAdmin" class="panel home-modules reveal reveal--delay-1">
      <div class="title-row">
        <div>
          <p class="eyebrow">管理工作区</p>
          <h2 class="section-title">快速入口</h2>
        </div>
        <span class="chip chip--admin">管理员模式</span>
      </div>

      <div class="module-grid">
        <RouterLink
          v-for="link in ADMIN_QUICK_LINKS"
          :key="link.to"
          :to="link.to"
          class="admin-module-card"
        >
          <div class="admin-module-card__icon">{{ link.icon }}</div>
          <div class="admin-module-card__body">
            <p class="eyebrow">{{ link.kicker }}</p>
            <p class="admin-module-card__title">{{ link.title }}</p>
            <p class="admin-module-card__sub">{{ link.subtitle }}</p>
          </div>
          <span class="chip chip--neutral admin-module-card__cta">进入 →</span>
        </RouterLink>
      </div>
    </section>

    <!-- ── 普通用户工作台模块 ── -->
    <section v-else class="panel home-modules reveal reveal--delay-1">
      <div class="title-row">
        <div>
          <p class="eyebrow">工作区</p>
          <h2 class="section-title">模块入口</h2>
        </div>
        <span v-if="loading" class="chip chip--neutral">加载中</span>
      </div>

      <div class="module-grid">
        <article
          v-for="mod in STUDENT_WORKSPACE_MODULES"
          :key="mod.id"
          class="module-card"
          :class="{ 'module-card--expanded': expandedId === mod.id }"
        >
          <ModuleDashboardTree
            :kicker="mod.kicker"
            :title="mod.title"
            :subtitle="mod.subtitle"
            :metrics="slicesById[mod.id].metrics"
            :loading="slicesById[mod.id].loading"
            :error="slicesById[mod.id].error"
            :expanded="expandedId === mod.id"
            @toggle="toggleModule(mod.id)"
          />
          <RouterLink :to="mod.path" class="chip chip--neutral module-card__cta" @click.stop>
            进入 →
          </RouterLink>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.home-page {
  display: grid;
  gap: 1rem;
}

.section-title {
  margin: 0;
  font-family: var(--font-display);
  color: var(--heading);
  font-size: clamp(1.2rem, 2vw, 1.55rem);
}

.module-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.module-card {
  display: grid;
  gap: 0.35rem;
  padding: 0.85rem 1rem 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  background: linear-gradient(180deg, var(--card-top), var(--card-bottom));
  color: inherit;
  transition:
    border-color 0.2s ease,
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.module-card:hover {
  border-color: rgba(var(--accent-1-rgb), 0.28);
  box-shadow: var(--shadow-soft);
}

.module-card--expanded {
  border-color: rgba(var(--accent-1-rgb), 0.45);
  box-shadow: 0 8px 22px rgba(var(--accent-1-rgb), 0.12);
}

.module-card__cta {
  justify-self: start;
  margin-top: 0.15rem;
  text-decoration: none;
  transition: border-color 0.2s ease;
}

.module-card__cta:hover {
  border-color: rgba(var(--accent-1-rgb), 0.35);
}

/* ── Admin quick-link cards ── */
.admin-module-card {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  padding: 1.1rem 1.2rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  background: linear-gradient(180deg, var(--card-top), var(--card-bottom));
  text-decoration: none;
  color: inherit;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.admin-module-card:hover {
  border-color: rgba(var(--accent-1-rgb), 0.35);
  box-shadow: var(--shadow-soft);
  transform: translateY(-2px);
}

.admin-module-card__icon {
  font-size: 1.6rem;
  line-height: 1;
  flex-shrink: 0;
  margin-top: 0.1rem;
}

.admin-module-card__body {
  flex: 1;
  min-width: 0;
}

.admin-module-card__title {
  margin: 0.15rem 0 0.25rem;
  font-weight: 600;
  color: var(--heading);
  font-size: 1rem;
}

.admin-module-card__sub {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.85rem;
  line-height: 1.4;
}

.admin-module-card__cta {
  flex-shrink: 0;
  align-self: center;
  text-decoration: none;
}

.chip--admin {
  background: rgba(var(--accent-1-rgb), 0.15);
  color: var(--primary);
  border: 1px solid rgba(var(--accent-1-rgb), 0.3);
}
</style>
