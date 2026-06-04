<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'

import ModuleDashboardTree from '../components/ModuleDashboardTree.vue'
import { useHomeDashboard } from '../composables/useHomeDashboard'
import {
  STUDENT_WORKSPACE_MODULES,
  type WorkspaceModuleId,
} from '../constants/workspaceModules'
import { authState, isAdmin } from '../stores/auth'

const { loading, slicesById, refresh } = useHomeDashboard()

const expandedId = ref<WorkspaceModuleId | null>(null)

const userLabel = computed(() => authState.user?.full_name || authState.user?.username || '同学')
const admin = computed(() => isAdmin(authState.user))

function toggleModule(id: WorkspaceModuleId) {
  expandedId.value = expandedId.value === id ? null : id
}
</script>

<template>
  <div class="page page--wide home-page">
    <section class="hero-frame glass-card panel app-hero reveal">
      <div class="app-hero__copy">
        <p class="page-kicker">AI 导师工作台</p>
        <h1 class="page-title">欢迎回来，{{ userLabel }}。</h1>
        <p class="page-subtitle">
          {{
            admin
              ? '你的管理权限已启用。在此总览学习进度，并快速进入各工作区。'
              : '在此总览聊天、画像、计划与成长记录。工作区已就绪，按你的节奏继续推进即可。'
          }}
        </p>

        <div class="hero-actions">
          <RouterLink class="button button--primary" to="/chat">打开聊天</RouterLink>
          <RouterLink class="button button--ghost" to="/plan">查看计划</RouterLink>
          <RouterLink class="button button--ghost" to="/growth">成长记录</RouterLink>
          <button class="button button--ghost" type="button" :disabled="loading" @click="refresh">
            刷新数据
          </button>
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
            <p class="hero-floating__trend">{{ admin ? '可进入用户管理' : '与 AI 一起规划和聊天' }}</p>
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

    <section class="panel home-modules reveal reveal--delay-1">
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
</style>
