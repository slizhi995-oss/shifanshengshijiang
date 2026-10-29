<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, Clock, Collection, MagicStick, Search } from '@element-plus/icons-vue'
import { resourceCenterApi, type ResourceLesson } from '@/api/resourceCenter'
import TeachingTipVideos from '@/components/TeachingTipVideos.vue'

const route = useRoute()
const router = useRouter()
const keyword = ref('')
const page = ref(1)
const total = ref(0)
const lessons = ref<ResourceLesson[]>([])
const listLoading = ref(false)
const listFailed = ref(false)
const historyVisible = ref(false)
let listRevision = 0
const dateLabel = (value: string) => value ? value.slice(0, 16).replace('T', ' ') : ''

async function loadLessons() {
  const revision = ++listRevision
  listLoading.value = true
  listFailed.value = false
  try {
    const result = await resourceCenterApi.list({ keyword: keyword.value.trim(), page: page.value })
    if (revision !== listRevision) return
    lessons.value = result.items
    total.value = result.total
  } catch { if (revision === listRevision) listFailed.value = true }
  finally { if (revision === listRevision) listLoading.value = false }
}
function search() { page.value = 1; void loadLessons() }
function changePage(value: number) { page.value = value; void loadLessons() }
function openHistory() { historyVisible.value = true; void loadLessons() }
function restoreLesson(id: number) {
  historyVisible.value = false
  void router.push({ path: '/student/ai-generator', query: { resourceLesson: String(id) } })
}
// Preserve existing resource links while opening their lesson in its new home.
watch(() => [route.query.resourceLesson, route.query.lesson], () => {
  if (route.query.resourceLesson || route.query.lesson) {
    void router.replace({ path: '/student/ai-generator', query: { ...route.query } })
  }
}, { immediate: true })
onBeforeUnmount(() => { ++listRevision })
</script>

<template>
  <section class="resource-center">
    <header class="page-heading">
      <div>
        <span class="eyebrow"><el-icon><Collection /></el-icon> 备课与试讲 · 精选学习</span>
        <h1>AI 资源中心</h1>
        <p>学习精选试讲技巧；教案配套音频与教学视频可在「AI 教案生成」中直接查看。</p>
      </div>
      <div class="heading-actions">
        <el-button :icon="Clock" @click="openHistory">历史记录</el-button>
        <el-button type="primary" :icon="MagicStick" @click="router.push('/student/ai-generator')">生成新教案</el-button>
      </div>
    </header>

    <main class="lesson-content" aria-label="精选学习资源">
      <TeachingTipVideos class="standalone-tips" reason="学习导入设计、板书与课堂表达等试讲技巧，为课堂呈现积累方法。" />
    </main>

    <el-dialog v-model="historyVisible" title="历史记录" width="min(680px, 94vw)" class="resource-history-dialog">
      <p class="history-help">打开曾生成的教案，在教案下方查看对应的配套资源。</p>
      <form class="history-search" @submit.prevent="search">
        <el-input v-model="keyword" placeholder="搜索课题、学科或年级" aria-label="搜索历史记录" clearable :prefix-icon="Search" @clear="search" />
        <el-button native-type="submit" :icon="Search" aria-label="搜索历史记录">搜索</el-button>
      </form>
      <div v-loading="listLoading" class="history-list">
        <div v-if="listFailed" class="error-box" role="alert">历史记录加载失败 <el-button link @click="loadLessons()">重试</el-button></div>
        <template v-else>
          <button v-for="lesson in lessons" :key="lesson.id" type="button" class="history-item"
            :aria-label="`查看教案：${lesson.title}`" @click="restoreLesson(lesson.id)">
            <span class="history-item-body">
              <span class="history-title">{{ lesson.title }}</span>
              <span class="history-meta">{{ lesson.subject }} · {{ lesson.grade }}<template v-if="lesson.created_at"> · {{ dateLabel(lesson.created_at) }}</template></span>
              <span v-if="lesson.source.parent_title" class="history-meta">{{ lesson.source.book_title }} · {{ lesson.source.parent_title }}</span>
            </span>
            <span class="history-open">查看教案<el-icon><ArrowRight /></el-icon></span>
          </button>
          <el-empty v-if="!listLoading && !lessons.length" :image-size="75" :description="keyword ? '没有找到相关历史记录' : '暂无历史记录，生成教案后可在这里查看'" />
        </template>
      </div>
      <div v-if="!listFailed && total" class="history-footer">
        <span>共 {{ total }} 条记录</span>
        <el-pagination v-if="total > 20" small layout="prev, pager, next" :total="total" :page-size="20" :current-page="page" @current-change="changePage" />
      </div>
    </el-dialog>
  </section>
</template>

<style scoped>
.resource-center { max-width: 1480px; margin: 0 auto; padding: 28px; color: #1e293b; }
.standalone-tips { margin-top: 0; border-top: 0; padding-top: 0; }
.page-heading { display: flex; align-items: center; justify-content: space-between; gap: 18px; }
.heading-actions { display: flex; flex-wrap: wrap; gap: 10px; flex-shrink: 0; }.heading-actions .el-button { margin: 0; }
.page-heading { margin-bottom: 25px; }.eyebrow { display: inline-flex; align-items: center; gap: 7px; color: #0891b2; font-size: 12px; font-weight: 600; }h1 { margin: 9px 0 10px; font-size: 28px; letter-spacing: -.5px; }.page-heading p { margin: 0; font-size: 14px; color: #64748b; line-height: 1.7; }
.lesson-content { padding: 26px; border: 1px solid #e2e8f0; border-radius: 14px; background: #fff; min-width: 0; }
.history-help { margin: 0 0 16px; color: #64748b; font-size: 13px; line-height: 1.7; }.history-search { display: flex; gap: 8px; margin-bottom: 18px; }.history-search .el-input { min-width: 0; }.history-search .el-button { margin: 0; }.history-list { min-height: 150px; max-height: 52vh; overflow-y: auto; padding: 3px; }.history-item { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 16px; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px; margin-bottom: 10px; text-align: left; background: #fff; font: inherit; color: #1e293b; cursor: pointer; }.history-item:hover { background: #f8fafc; border-color: #a5f3fc; }.history-item:focus-visible { outline: 2px solid #0891b2; outline-offset: 1px; }.history-item-body { min-width: 0; }.history-title { display: block; font-size: 14px; font-weight: 600; line-height: 1.6; overflow-wrap: anywhere; }.history-meta { display: block; font-size: 12px; color: #64748b; line-height: 1.7; margin-top: 7px; }.history-open { display: flex; align-items: center; gap: 6px; flex-shrink: 0; color: #0e7490; font-size: 12px; }.history-footer { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-top: 16px; font-size: 12px; color: #64748b; }
.error-box { padding: 25px 10px; text-align: center; font-size: 13px; color: #b45309; }
@media (max-width: 760px) { .resource-center { padding: 16px; }.page-heading { align-items: flex-start; flex-direction: column; }h1 { font-size: 24px; }.lesson-content { padding: 19px; }.history-item { gap: 10px; padding: 12px; }.history-open { font-size: 11px; } }
</style>
