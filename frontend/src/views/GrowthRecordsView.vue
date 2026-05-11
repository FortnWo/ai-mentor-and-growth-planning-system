<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { listGrowthRecords, createGrowthRecord, generateWeeklySummary } from '../api/growthRecords'
import { authState, refreshCurrentUser } from '../stores/auth'

const records = ref([] as any[])
const loading = ref(false)
const feedback = ref('')
const summaryFeedback = ref('')

const form = reactive({ title: '', summary: '' })

async function load() {
    loading.value = true
    try {
        const items = await listGrowthRecords({ limit: 20 })
        records.value = items
    } catch (e) {
        records.value = []
    } finally {
        loading.value = false
    }
}

async function submit() {
    try {
        const payload = { title: form.title.trim() || '记录一个小胜利', summary: form.summary.trim() || undefined, idempotency_key: `ui-${Date.now()}` }
        await createGrowthRecord(payload)
        feedback.value = '已记录今天的小胜利 🎉'
        form.title = ''
        form.summary = ''
        await load()
    } catch (e) {
        feedback.value = '记录失败，请稍后重试。'
    }
}

async function triggerWeeklySummary() {
    try {
        const end = new Date()
        const start = new Date()
        start.setDate(end.getDate() - 6)
        await generateWeeklySummary({ start_date: start.toISOString().slice(0, 10), end_date: end.toISOString().slice(0, 10) })
        summaryFeedback.value = '已触发周总结生成（后台），稍后可在「周总结」查看或刷新。'
    } catch (e) {
        summaryFeedback.value = '触发周总结失败。'
    }
}

onMounted(async () => {
    if (!authState.user) {
        await refreshCurrentUser()
    }
    await load()
})
</script>

<template>
    <div class="page page--wide">
        <section class="page-header glass-card panel hero-frame">
            <div class="title-row">
                <div>
                    <p class="page-kicker">成长记录</p>
                    <h1 class="page-title">记录你的每一次小进步</h1>
                    <p class="page-subtitle">鼓励温暖的文字，让成长的轨迹更清晰。</p>
                </div>
            </div>
        </section>

        <div class="grid-2">
            <section class="panel form-card">
                <h2 class="section-title">记录一个小胜利</h2>
                <label class="field">
                    <span class="label">标题</span>
                    <input v-model="form.title" class="input" placeholder="比如：完成复习 30 分钟" />
                </label>
                <label class="field">
                    <span class="label">简短描述</span>
                    <textarea v-model="form.summary" class="textarea" rows="3" placeholder="写下你的感受或下一步"></textarea>
                </label>
                <div class="actions">
                    <button class="button button--primary" @click="submit">记录小胜利</button>
                    <button class="button button--ghost" @click="triggerWeeklySummary">生成本周总结</button>
                </div>
                <p v-if="feedback" class="feedback feedback--success">{{ feedback }}</p>
                <p v-if="summaryFeedback" class="feedback feedback--muted">{{ summaryFeedback }}</p>
            </section>

            <section class="panel">
                <h2 class="section-title">时间线</h2>
                <div v-if="loading">加载中…</div>
                <div v-else-if="records.length === 0" class="empty-state">
                    <p>还没有成长记录。试着记录一个小胜利，或者从行动计划中自动回写。</p>
                    <button class="button button--ghost"
                        @click="form.title = '完成了练习题'; form.summary = '进步一点点，值得庆祝'; submit()">写个示例</button>
                </div>
                <ul v-else class="record-list">
                    <li v-for="r in records" :key="r.id" class="record-item">
                        <h3>{{ r.title }}</h3>
                        <p class="muted">{{ r.record_date ?? (r.occurred_at ? new Date(r.occurred_at).toLocaleString() :
                            '') }}</p>
                        <p v-if="r.summary">{{ r.summary }}</p>
                        <p v-if="r.ai_summary" class="muted">AI 摘要：{{ r.ai_summary }}</p>
                    </li>
                </ul>
            </section>
        </div>
    </div>
</template>

<style scoped>
.record-list {
    display: grid;
    gap: 0.8rem;
}

.record-item {
    padding: 0.8rem;
    border-bottom: 1px solid rgba(148, 163, 184, 0.08);
}

.empty-state {
    padding: 1rem 0;
}
</style>
