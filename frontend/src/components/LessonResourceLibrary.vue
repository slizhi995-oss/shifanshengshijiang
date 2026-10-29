<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Document, Download, Picture, Reading, Refresh, Search } from '@element-plus/icons-vue'
import { lessonResourcesApi, type LessonMaterial, type LessonResources, type LessonResourceSummary } from '@/api/lessonResources'
import { textbookApi } from '@/api/textbooks'
import TextbookImage from '@/components/TextbookImage.vue'
import LessonWordPreview from '@/components/LessonWordPreview.vue'

const route = useRoute()
const router = useRouter()
const keyword = ref('')
const page = ref(1)
const total = ref(0)
const lessons = ref<LessonResourceSummary[]>([])
const listLoading = ref(false)
const listFailed = ref(false)
const selectedId = ref<number>()
const detail = ref<LessonResources>()
const detailLoading = ref(false)
const detailFailed = ref(false)
const imagePreview = ref<LessonMaterial>()
const showImage = ref(false)
const showWord = ref(false)
const wordReady = ref(false)
const wordPreview = ref<InstanceType<typeof LessonWordPreview>>()
const documentIds = ref<Record<number, string>>({})
const bundleLoading = ref(false)
const pdfLoading = ref(false)
const showPdf = ref(false)
const pdfUrl = ref('')
const pdfPage = ref(1)
let listRevision = 0
let detailRevision = 0
let pdfRevision = 0
const availableCount = computed(() => detail.value?.materials.filter(image => image.available).length || 0)
const dateLabel = (value: string) => value ? value.slice(0, 16).replace('T', ' ') : ''

async function loadLessons(initial = false) {
  const revision = ++listRevision
  listLoading.value = true
  listFailed.value = false
  try {
    const result = await lessonResourcesApi.list({ keyword: keyword.value.trim(), page: page.value })
    if (revision !== listRevision) return
    lessons.value = result.items
    total.value = result.total
    const requested = initial ? Number(route.query.lesson) : 0
    if (requested > 0 && Number.isInteger(requested)) await selectLesson(requested)
    else if (!result.items.some(item => item.id === selectedId.value)) {
      if (result.items.length) await selectLesson(result.items[0].id)
      else { ++detailRevision; detail.value = undefined; selectedId.value = undefined; detailLoading.value = false }
    }
  } catch {
    if (revision === listRevision) listFailed.value = true
  } finally {
    if (revision === listRevision) listLoading.value = false
  }
}

async function selectLesson(id: number) {
  const revision = ++detailRevision
  selectedId.value = id
  detail.value = undefined
  detailLoading.value = true
  detailFailed.value = false
  showWord.value = false
  showImage.value = false
  closePdf()
  try {
    const result = await lessonResourcesApi.detail(id)
    if (revision === detailRevision) detail.value = result
  } catch {
    if (revision === detailRevision) detailFailed.value = true
  } finally {
    if (revision === detailRevision) detailLoading.value = false
  }
}

function search() { page.value = 1; loadLessons() }
function changePage(value: number) { page.value = value; loadLessons() }
function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename.replace(/[\\/:*?"<>|]/g, '_')
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
async function downloadImage(material: LessonMaterial) {
  try { saveBlob(await textbookApi.image(material.asset_id), `${material.figure_number} ${material.title}.png`) }
  catch { ElMessage.error('图片下载失败，请重试') }
}
async function downloadBundle() {
  if (!detail.value || bundleLoading.value) return
  const lesson = detail.value
  bundleLoading.value = true
  try { saveBlob(await textbookApi.bundle(lesson.id), `${lesson.title}_教案与配图.zip`) }
  catch { ElMessage.error('资源包下载失败，请检查图片是否仍可用') }
  finally { bundleLoading.value = false }
}
function closePdf() {
  ++pdfRevision
  if (pdfUrl.value) URL.revokeObjectURL(pdfUrl.value)
  pdfUrl.value = ''
  pdfLoading.value = false
  showPdf.value = false
}
async function openPdf(pageNumber?: number | null) {
  const source = detail.value?.source
  if (!source?.book_id || !source.available) return
  closePdf()
  const revision = ++pdfRevision
  pdfPage.value = pageNumber || source.start_page || 1
  pdfLoading.value = true
  showPdf.value = true
  try {
    const blob = await textbookApi.pdf(source.book_id)
    if (revision === pdfRevision) pdfUrl.value = URL.createObjectURL(blob)
  } catch {
    if (revision === pdfRevision) { ElMessage.error('教材原页加载失败，请重试'); showPdf.value = false }
  } finally {
    if (revision === pdfRevision) pdfLoading.value = false
  }
}
function rememberDocument(id: string) { if (detail.value) documentIds.value[detail.value.id] = id }
watch(() => route.query.lesson, value => {
  const id = Number(value)
  if (Number.isInteger(id) && id > 0 && id !== selectedId.value) selectLesson(id)
})
onMounted(() => loadLessons(true))
onBeforeUnmount(() => { ++listRevision; ++detailRevision; closePdf() })
</script>

<template>
  <section class="lesson-library">
    <header class="library-heading">
      <div>
        <h1><el-icon><Reading /></el-icon> 我的教案资源</h1>
        <p>按教案整理教材来源、已用配图和待补充素材，备课时随时查阅与下载。</p>
      </div>
      <el-button type="primary" @click="router.push('/student/ai-generator')">新建教案</el-button>
    </header>
    <div class="library-workspace">
      <aside class="lesson-list" aria-label="教案列表">
        <div class="list-tools">
          <el-input v-model="keyword" placeholder="搜索课题、学科或教材" clearable :prefix-icon="Search" @keyup.enter="search" @clear="search" />
          <el-button :icon="Search" aria-label="搜索教案" @click="search" />
          <el-button :icon="Refresh" aria-label="刷新教案列表" @click="loadLessons()" />
        </div>
        <p class="list-count">已保存的教材教案 · {{ total }} 份</p>
        <div v-loading="listLoading" class="lesson-list-body">
          <div v-if="listFailed" class="load-error" role="alert">
            教案列表加载失败 <el-button link type="primary" @click="loadLessons()">重试</el-button>
          </div>
          <template v-else>
            <button v-for="lesson in lessons" :key="lesson.id" type="button" class="lesson-choice"
              :class="{ selected: selectedId === lesson.id }" :aria-pressed="selectedId === lesson.id" @click="selectLesson(lesson.id)">
              <span class="lesson-choice-title">{{ lesson.title }}</span>
              <span class="lesson-choice-meta">{{ lesson.subject }} · {{ lesson.grade }} · {{ dateLabel(lesson.created_at) }}</span>
              <span class="lesson-choice-count">{{ lesson.image_count }} 张引用配图<span v-if="lesson.pending_count"> · {{ lesson.pending_count }} 项待补充</span></span>
            </button>
            <el-empty v-if="!listLoading && !lessons.length" :description="keyword ? '没有找到匹配的教案' : '生成教材教案后，资源会自动归集到这里'" :image-size="80" />
          </template>
        </div>
        <el-pagination v-if="total > 20" small layout="prev, pager, next" :total="total" :page-size="20" :current-page="page" @current-change="changePage" />
      </aside>

      <main v-loading="detailLoading" class="lesson-resource-detail" aria-label="教案资源清单">
        <div v-if="detailFailed" class="load-error" role="alert">
          这份教案暂时无法读取 <el-button link type="primary" @click="selectedId && selectLesson(selectedId)">重试</el-button>
        </div>
        <template v-else-if="detail">
          <div class="detail-heading">
            <div><span class="eyebrow">教案资源清单</span><h2>{{ detail.title }}</h2><p>{{ detail.subject }} · {{ detail.grade }} · {{ dateLabel(detail.created_at) }}</p></div>
            <div class="detail-actions">
              <el-button :icon="Document" @click="showWord = true">查看教案</el-button>
              <el-button :icon="Download" :loading="bundleLoading" @click="downloadBundle">下载教案与配图</el-button>
            </div>
          </div>

          <section class="source-card" aria-label="教材来源">
            <div class="section-heading"><h3><el-icon><Reading /></el-icon> 教材来源</h3>
              <el-button type="primary" link :disabled="!detail.source.available" @click="openPdf()">查看教材原页</el-button></div>
            <strong>{{ detail.source.book_title || '历史教案未保存教材名称' }}</strong>
            <p>{{ [detail.source.edition, detail.source.volume, detail.source.chapter_title].filter(Boolean).join(' · ') }}</p>
            <p class="source-pages"><span v-if="detail.source.printed_pages">教材印刷页码：{{ detail.source.printed_pages }} · </span>PDF 文件第 {{ detail.source.start_page }}–{{ detail.source.end_page }} 页</p>
            <p v-if="!detail.source.available" class="unavailable">教材或章节当前未发布，暂时无法打开原页和配图。</p>
          </section>

          <section aria-label="已用配图" class="materials-section">
            <div class="section-heading"><h3><el-icon><Picture /></el-icon> 已用配图 <span>{{ detail.materials.length }}</span></h3><span class="muted">{{ availableCount }} 张可用</span></div>
            <p class="section-help">每张图片保留教材出处和在教案中的使用位置。</p>
            <div v-if="detail.materials.length" class="material-grid">
              <article v-for="material in detail.materials" :key="material.asset_id" class="material-card">
                <button v-if="material.available" type="button" class="material-thumb" :aria-label="`查看配图：${material.title}`" @click="imagePreview = material; showImage = true">
                  <TextbookImage :asset-id="material.asset_id" :alt="material.title" />
                </button>
                <div v-else class="missing-image">图片暂不可用</div>
                <div class="material-body">
                  <h4>{{ [material.figure_number, material.title].filter(Boolean).join(' ') }}</h4>
                  <p v-if="material.pdf_page" class="muted">{{ detail.source.book_title }} · PDF 第 {{ material.pdf_page }} 页</p>
                  <p v-if="material.description" class="material-description">{{ material.description }}</p>
                  <div v-for="(usage, index) in material.usages" :key="index" class="usage">
                    <span class="usage-label">{{ usage.section }}</span><p v-if="usage.excerpt">{{ usage.excerpt }}</p>
                  </div>
                  <div v-if="material.available" class="material-actions">
                    <el-button link type="primary" @click="downloadImage(material)">下载图片</el-button>
                    <el-button link type="primary" @click="openPdf(material.pdf_page)">查看原页</el-button>
                  </div>
                </div>
              </article>
            </div>
            <el-empty v-else description="这份教案未引用教材配图，可先查阅教材原页" :image-size="70" />
          </section>

          <section class="pending-section" aria-label="待补充素材">
            <div class="section-heading"><h3>待补充素材 <span>{{ detail.pending.length }}</span></h3></div>
            <p class="section-help">这里列出教案中明确标注待插入的图片或视频，备课时需要继续补充。</p>
            <div v-for="(item, index) in detail.pending" :key="index" class="pending-item">
              <el-tag :type="item.kind === 'video' ? 'warning' : 'info'" size="small">{{ item.kind === 'video' ? '视频' : '图片' }}</el-tag>
              <div><strong>{{ item.section }}</strong><p>{{ item.description }}</p></div>
            </div>
            <p v-if="!detail.pending.length" class="no-pending">教案中没有明确标注待补充的图片或视频。</p>
          </section>
        </template>
        <el-empty v-else-if="!detailLoading && !listFailed" description="选择一份教案，查看与它对应的资源" :image-size="110" />
      </main>
    </div>

    <el-dialog v-model="showImage" :title="imagePreview?.title || '教材配图'" width="min(900px, 94vw)" destroy-on-close>
      <template v-if="imagePreview">
        <div class="large-image"><TextbookImage :asset-id="imagePreview.asset_id" :alt="imagePreview.title" /></div>
        <p>{{ imagePreview.description }}</p><p v-if="imagePreview.conditions" class="muted">适用条件：{{ imagePreview.conditions }}</p>
        <el-button type="primary" :icon="Download" @click="downloadImage(imagePreview)">下载图片</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="showPdf" title="教材原页" width="min(1100px, 96vw)" top="3vh" destroy-on-close @close="closePdf">
      <div v-loading="pdfLoading" class="pdf-preview"><iframe v-if="pdfUrl" :src="`${pdfUrl}#page=${pdfPage}`" title="教材 PDF 原页" /></div>
      <p class="muted">定位到 PDF 文件第 {{ pdfPage }} 页，教材印刷页码可能与 PDF 页序不同。</p>
    </el-dialog>
    <el-dialog v-model="showWord" title="教案预览" width="min(1100px, 96vw)" top="3vh" destroy-on-close>
      <template v-if="detail && showWord">
        <div class="word-toolbar"><el-button :disabled="!wordReady" :icon="Download" @click="wordPreview?.download()">下载 Word</el-button></div>
        <div class="word-preview"><LessonWordPreview ref="wordPreview" :key="detail.id" :lesson-id="detail.id" :content="detail.content"
          :title="detail.title" :document-id="documentIds[detail.id]" @ready="value => wordReady = value" @document-created="rememberDocument" /></div>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.lesson-library { max-width: 1480px; margin: 0 auto; padding: 26px; color: #1e293b; }
.library-heading, .detail-heading, .section-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.library-heading { margin-bottom: 24px; }
h1 { display: flex; align-items: center; gap: 10px; margin: 0; font-size: 24px; }
h1 .el-icon, h3 .el-icon { color: #0891b2; }
.library-heading p, .detail-heading p { color: #64748b; font-size: 14px; margin: 10px 0 0; }
.library-workspace { display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: 22px; align-items: start; }
.lesson-list, .lesson-resource-detail { border: 1px solid #e2e8f0; border-radius: 14px; background: white; min-width: 0; }
.lesson-list { padding: 16px; }
.list-tools { display: flex; gap: 5px; }.list-tools .el-input { flex: 1; min-width: 0; }.list-tools .el-button { margin-left: 0; padding: 8px; }
.list-count, .muted, .source-pages, .section-help { color: #64748b; font-size: 13px; line-height: 1.65; }
.lesson-list-body { min-height: 120px; }.lesson-choice { display: block; width: 100%; text-align: left; padding: 15px 12px; border: 1px solid transparent; border-radius: 10px; background: transparent; cursor: pointer; color: inherit; font: inherit; }
.lesson-choice + .lesson-choice { margin-top: 7px; }.lesson-choice:hover { background: #f8fafc; }.lesson-choice.selected { background: #ecfeff; border-color: #a5f3fc; }
.lesson-choice:focus-visible, .material-thumb:focus-visible { outline: 2px solid #0891b2; outline-offset: 2px; }
.lesson-choice-title { display: block; font-weight: 600; font-size: 14px; line-height: 1.6; }.lesson-choice-meta, .lesson-choice-count { display: block; color: #64748b; font-size: 12px; margin-top: 7px; }.lesson-choice-count { color: #0e7490; }
.lesson-resource-detail { padding: 24px; min-height: 420px; }.detail-heading { align-items: flex-start; margin-bottom: 22px; }.eyebrow { font-size: 12px; color: #0891b2; }h2 { margin: 7px 0 0; font-size: 22px; line-height: 1.4; }.detail-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }.detail-actions .el-button { margin-left: 0; }
.source-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px; }.source-card p { font-size: 13px; line-height: 1.6; margin: 9px 0 0; }.source-card strong { display: block; margin-top: 12px; font-size: 15px; }
h3 { display: flex; align-items: center; gap: 7px; font-size: 16px; margin: 0; }h3 span { font-size: 12px; background: #e2e8f0; border-radius: 6px; padding: 2px 7px; color: #475569; }
.materials-section, .pending-section { margin-top: 27px; }.section-help { margin: 10px 0 16px; }.material-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }.material-card { border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; }.material-thumb { display: block; padding: 0; width: 100%; border: 0; cursor: zoom-in; background: #f8fafc; }.material-thumb :deep(img) { display: block; }.missing-image { height: 150px; display: grid; place-items: center; color: #64748b; background: #f1f5f9; }.material-body { padding: 16px; }h4 { margin: 0; font-size: 15px; line-height: 1.6; }.material-description { font-size: 13px; line-height: 1.7; }.usage { border-left: 2px solid #a5f3fc; margin-top: 12px; padding-left: 10px; }.usage-label { font-size: 12px; color: #0e7490; }.usage p { font-size: 12px; color: #64748b; line-height: 1.6; overflow-wrap: anywhere; margin: 7px 0; }.material-actions { display: flex; gap: 14px; margin-top: 14px; }.material-actions .el-button { margin: 0; }
.pending-item { display: flex; gap: 12px; align-items: flex-start; background: #fffbeb; border-radius: 10px; padding: 14px; margin-bottom: 10px; }.pending-item strong { font-size: 13px; }.pending-item p { font-size: 13px; line-height: 1.7; margin: 6px 0 0; }.no-pending { color: #64748b; background: #f8fafc; border-radius: 10px; padding: 16px; font-size: 13px; }.unavailable { color: #b45309; }.load-error { padding: 28px 12px; font-size: 14px; text-align: center; color: #b45309; }
.large-image :deep(img) { height: auto; max-height: 65vh; }.pdf-preview { height: 72vh; }.pdf-preview iframe { border: 0; width: 100%; height: 100%; }.word-preview { height: 72vh; display: flex; }.word-toolbar { text-align: right; margin-bottom: 12px; }
@media(max-width: 1100px) { .library-workspace { grid-template-columns: 250px minmax(0, 1fr); }.detail-heading { flex-direction: column; }.detail-actions { justify-content: flex-start; }.material-grid { grid-template-columns: 1fr; } }
@media(max-width: 760px) { .lesson-library { padding: 16px; }.library-heading { align-items: flex-start; }h1 { font-size: 20px; }.library-workspace { grid-template-columns: 1fr; }.lesson-list-body { max-height: 280px; overflow: auto; }.lesson-resource-detail { padding: 16px; }.section-heading { flex-wrap: wrap; } }
</style>
