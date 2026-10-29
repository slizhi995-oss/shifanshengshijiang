<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { VideoPlay } from '@element-plus/icons-vue'
import { teachingTipsApi, type TeachingTip } from '@/api/teachingTips'

defineProps<{ reason?: string }>()
const items = ref<TeachingTip[]>([])
const loading = ref(false)
const failed = ref(false)
const category = ref('')
const page = ref(1)
const pageSize = 9
const brokenCovers = ref(new Set<number>())
const resolvedCovers = ref<Record<number, string>>({})
const requestedCovers = new Set<number>()
const categories = computed(() => [...new Set(items.value.map(item => item.category))])
const filtered = computed(() => items.value.filter(item => !category.value || item.category === category.value))
const visible = computed(() => filtered.value.slice((page.value - 1) * pageSize, page.value * pageSize))
watch(category, () => { page.value = 1 })
watch(visible, rows => {
  for (const item of rows) if (!item.cover_url) void resolveCover(item)
})
async function resolveCover(item: TeachingTip) {
  if (requestedCovers.has(item.id)) return
  requestedCovers.add(item.id)
  try {
    const result = await teachingTipsApi.coverMetadata(item.id)
    if (result.cover_url && result.cover_url !== item.cover_url) {
      resolvedCovers.value[item.id] = result.cover_url
      brokenCovers.value.delete(item.id)
    }
  } catch { /* Keep the classroom illustration when metadata is unavailable. */ }
}
function coverFailed(item: TeachingTip) {
  brokenCovers.value.add(item.id)
  void resolveCover(item)
}
async function load() {
  loading.value = true
  failed.value = false
  try { items.value = (await teachingTipsApi.list()).items }
  catch { failed.value = true }
  finally { loading.value = false }
}
onMounted(load)
</script>

<template>
  <section class="teaching-tips" aria-label="试讲技巧视频" v-loading="loading">
    <header><div><span class="eyebrow">备课与试讲 · 精选学习</span><h3><el-icon><VideoPlay /></el-icon> 试讲技巧视频</h3></div><span class="curated">管理员精选</span></header>
    <p class="intro">{{ reason || '暂未找到对应的课堂资源，可以先看看这些试讲技巧。' }}</p>
    <p v-if="failed" class="tip-status" role="alert">精选视频加载失败 <el-button link type="primary" @click="load">重试</el-button></p>
    <template v-else-if="!loading">
      <div v-if="categories.length > 1" class="filters" aria-label="试讲技巧分类">
        <el-button round size="small" :type="!category ? 'primary' : 'default'" @click="category = ''">全部</el-button>
        <el-button v-for="label in categories" :key="label" round size="small" :type="category === label ? 'primary' : 'default'" @click="category = label">{{ label }}</el-button>
      </div>
      <div v-if="visible.length" class="tips-grid">
        <a v-for="item in visible" :key="item.id" class="tip-card" :href="item.url" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer" :aria-label="`${item.title}（在 B 站观看）`">
          <div class="tip-cover">
            <img v-if="(resolvedCovers[item.id] || item.cover_url) && !brokenCovers.has(item.id)" :src="resolvedCovers[item.id] || item.cover_url" :alt="item.title" loading="lazy" referrerpolicy="no-referrer" @error="coverFailed(item)" />
            <img v-else class="cover-placeholder" src="/images/trial-video-cover.svg" alt="课堂插图占位封面" />
          </div>
          <h4 :title="item.title">{{ item.title }}</h4>
        </a>
      </div>
      <div v-else class="tip-status">精选试讲技巧视频正在整理中，管理员添加并上架后将在这里展示。</div>
      <nav v-if="filtered.length > pageSize" class="tips-pagination" aria-label="试讲技巧视频分页">
        <el-pagination v-model:current-page="page" :page-size="pageSize" :total="filtered.length" layout="prev, pager, next" background />
      </nav>
    </template>
  </section>
</template>

<style scoped>
.teaching-tips { margin-top: 24px; border-top: 1px solid #e2e8f0; padding-top: 24px; min-height: 150px; color: #1e293b; }
header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }.eyebrow { font-size: 11px; color: #0891b2; letter-spacing: 1px; }h3 { display: flex; align-items: center; gap: 8px; margin: 8px 0 0; font-size: 19px; }h3 .el-icon { color: #0891b2; }.curated { flex-shrink: 0; font-size: 11px; color: #0e7490; background: #ecfeff; border: 1px solid #cffafe; border-radius: 20px; padding: 6px 10px; }
.intro, .tip-status { font-size: 13px; line-height: 1.8; color: #64748b; }.intro { margin: 12px 0 18px; }.tip-status { background: #f8fafc; padding: 18px; border-radius: 10px; }.filters { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 18px; }.filters .el-button { margin: 0; }
.tips-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 24px 18px; }.tip-card { display: flex; flex-direction: column; min-width: 0; text-decoration: none; color: inherit; border-radius: 8px; }.tip-card:focus-visible { outline: 2px solid #0891b2; outline-offset: 4px; }.tip-card:hover h4 { color: #0891b2; }
.tip-cover { position: relative; aspect-ratio: 16 / 9; border-radius: 8px; background: #e0f2fe; overflow: hidden; }.tip-cover img { width: 100%; height: 100%; object-fit: cover; display: block; transition: transform .2s; }.tip-card:hover .tip-cover img { transform: scale(1.03); }
h4 { font-size: 15px; font-weight: 500; margin: 9px 0 0; line-height: 1.5; overflow-wrap: anywhere; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; transition: color .2s; }
.tips-pagination { display: flex; justify-content: center; margin-top: 24px; }
@media(max-width: 1100px) { .tips-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media(max-width: 640px) { .tips-grid { grid-template-columns: 1fr; } }
</style>
