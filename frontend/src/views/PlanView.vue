<script setup lang="ts">
// Growth plan view — business logic will be added in a future iteration.
</script>

<template>
  <div class="page page--wide plan-page">
    <section class="page-header glass-card panel">
      <p class="page-kicker">Roadmap preview</p>
      <h1 class="page-title">Growth Plan</h1>
      <p class="page-subtitle">
        This workspace will turn into a personalised roadmap once the AI Mentor has gathered enough context about your goals and progress.
      </p>

      <div class="hero-actions">
        <span class="chip chip--neutral">Future-ready layout</span>
        <span class="chip chip--active">AI-assisted planning</span>
      </div>
    </section>

    <section class="grid-3">
      <article class="stat-card">
        <p class="stat-label">Stage 1</p>
        <p class="stat-value">Discover</p>
        <p class="stat-note">Capture goals, constraints, and habits.</p>
      </article>

      <article class="stat-card">
        <p class="stat-label">Stage 2</p>
        <p class="stat-value">Plan</p>
        <p class="stat-note">Translate intent into weekly actions.</p>
      </article>

      <article class="stat-card">
        <p class="stat-label">Stage 3</p>
        <p class="stat-value">Review</p>
        <p class="stat-note">Measure progress and adjust the route.</p>
      </article>
    </section>

    <section class="panel roadmap-panel">
      <div class="title-row">
        <div>
          <p class="eyebrow">Coming soon</p>
          <h2 class="section-title">Structured planning canvas</h2>
        </div>
      </div>

      <p class="placeholder">
        Your personalised growth plan will appear here once the AI Mentor has gathered enough information about your goals and progress.
      </p>
    </section>
  </div>
</template>

<style scoped>
.plan-page {
  width: min(1180px, 100%);
  margin: 0 auto;
}

.roadmap-panel {
  display: grid;
  gap: 1rem;
}

.section-title {
  margin: 0;
  font-family: var(--font-display);
  color: var(--heading);
  font-size: clamp(1.25rem, 2vw, 1.6rem);
}
</style>
