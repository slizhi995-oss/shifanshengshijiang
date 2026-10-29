<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Refresh, VideoPlay } from '@element-plus/icons-vue'
import { lessonVideosApi, isBilibiliVideo, type LessonVideo, type VideoSearchState } from '@/api/lessonVideos'
import LessonVideoCard from '@/components/LessonVideoCard.vue'

const props = defineProps<{ lessonId: number; resultsOnly?: boolean }>()
const emit = defineEmits<{
  (event: 'fallback', visible: boolean): void
  (event: 'results', visible: boolean): void
}>()
const state = ref<VideoSearchState>()
const loading = ref(false)
const failed = ref(false)
const working = ref(false)
const query = ref('')
const showManual = ref(false)
const form = ref({ url: '', title: '', section: '', purpose: '' })
const formError = ref('')
const clock = ref(Date.now())
let revision = 0
let pollTimer: ReturnType<typeof setTimeout> | undefined
const tick = setInterval(() => { clock.value = Date.now() }, 1000)
const busy = computed(() => ['queued', 'searching'].includes(state.value?.status || ''))
const hasResults = computed(() => !!(state.value?.items.length || state.value?.selected.length))
watch(hasResults, visible => emit('results', visible), { immediate: true })
watch(() => !loading.value && !working.value && !busy.value &&
  (failed.value || (!!state.value && !state.value.items.length && !state.value.selected.length)),
  visible => emit('fallback', visible), { immediate: true })
const textbook = computed(() => state.value?.needs.find(need => need.textbook)?.textbook)
const remaining = computed(() => Math.max(0, Math.ceil(((state.value?.next_search_at ? Date.parse(state.value.next_search_at) : 0) - clock.value) / 1000)))
const canSearch = computed(() => !!state.value?.configured && !busy.value && !working.value && !loading.value && remaining.value === 0)
const statusText = computed(() => {
  switch (state.value?.status) {
    case 'queued': return '正在准备素材检索…'
    case 'searching': return '正在根据教案检索和筛选 B 站视频，可继续使用其他资源。'
    case 'not_configured': return '视频联网搜索尚未配置，可先查看下方试讲技巧视频，也可手动添加 B 站视频。'
    case 'no_need': return '当前教案未提取到明确的素材需求，可输入关键词查找。'
    case 'no_results': return '暂未找到适合当前教案的素材，可以先查看下方试讲技巧，也可调整关键词或手动添加。'
    case 'error': return '本次素材检索未完成，请重试或手动添加。'
    default: return state.value?.items.length ? '' : '可根据教案自动检索，也可输入具体的素材需求。'
  }
})

function setState(result: VideoSearchState) {
  state.value = { ...result, items: result.items.filter(isBilibiliVideo), selected: result.selected.filter(isBilibiliVideo) }
}
function stopPolling() { clearTimeout(pollTimer); pollTimer = undefined }
function excerptText(value: string) {
  return value.replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1').replace(/\*\*|^\s*[#>]+\s*/gm, '').trim()
}
function schedulePoll() {
  stopPolling()
  if (busy.value) pollTimer = setTimeout(() => { void load(false) }, 2000)
}
async function load(initial = false) {
  const current = ++revision
  loading.value = true
  failed.value = false
  try {
    const result = await lessonVideosApi.get(props.lessonId, props.resultsOnly)
    if (current !== revision) return
    setState(result)
    if (initial) query.value = result.query
    if (initial && result.configured && (result.status === 'idle' || (result.stale && ['ready', 'no_need', 'no_results'].includes(result.status)))) {
      const started = await lessonVideosApi.search(props.lessonId, result.query, false, props.resultsOnly)
      if (current !== revision) return
      setState(started)
    }
  } catch { if (current === revision) failed.value = true }
  finally {
    if (current === revision) { loading.value = false; schedulePoll() }
  }
}
async function search(reset = false) {
  if (!canSearch.value) return
  if (reset) query.value = ''
  const current = ++revision
  working.value = true
  stopPolling()
  try {
    const result = await lessonVideosApi.search(props.lessonId, query.value.trim(), true)
    if (current === revision) { setState(result); failed.value = false }
  } catch { /* The shared request handler displays the service error. */ }
  finally { if (current === revision) { working.value = false; schedulePoll() } }
}
async function addManual() {
  if (working.value) return
  formError.value = ''
  const values = Object.fromEntries(Object.entries(form.value).map(([key, value]) => [key, value.trim()]))
  if (Object.values(values).some(value => !value)) { formError.value = '请填写资源链接、标题、教学环节和用途'; return }
  try {
    const url = new URL(values.url)
    const match = url.pathname.match(/^\/video\/(BV[0-9A-Za-z]{10})\/?$/)
    if (!match || !isBilibiliVideo({ url: values.url, bvid: match[1] } as LessonVideo)) throw new Error()
  } catch { formError.value = '请使用包含 BV 号的 B 站完整视频链接'; return }
  const current = ++revision
  working.value = true
  stopPolling()
  try {
    const result = await lessonVideosApi.add(props.lessonId, values)
    if (current !== revision) return
    setState(result)
    loading.value = false
    showManual.value = false
    form.value = { url: '', title: '', section: '', purpose: '' }
    ElMessage.success('已加入本教案，请打开原网页确认素材适用性')
  } catch { /* Shared error handling. */ }
  finally { if (current === revision) { working.value = false; schedulePoll() } }
}
async function remove(item: LessonVideo) {
  if (working.value) return
  const current = ++revision
  working.value = true
  stopPolling()
  try {
    const result = await lessonVideosApi.remove(props.lessonId, item.id)
    if (current === revision) { setState(result); loading.value = false }
  } catch { /* Shared error handling. */ }
  finally { if (current === revision) { working.value = false; schedulePoll() } }
}
watch(() => props.lessonId, () => {
  ++revision
  stopPolling()
  state.value = undefined
  query.value = ''
  showManual.value = false
  form.value = { url: '', title: '', section: '', purpose: '' }
  formError.value = ''
  working.value = false
  void load(true)
}, { immediate: true })
onBeforeUnmount(() => { ++revision; stopPolling(); clearInterval(tick) })
</script>

<template>
  <section v-show="!resultsOnly || hasResults" class="lesson-videos" aria-label="教学视频">
    <div class="video-heading">
      <div><h3><el-icon><VideoPlay /></el-icon> 教学视频</h3><p>根据当前教案查找 B 站视频，点击视频标题前往 B 站观看。</p></div>
      <el-button v-if="!resultsOnly" :icon="Plus" :disabled="!state || working" @click="showManual = true">手动添加</el-button>
    </div>
    <div v-if="!resultsOnly && failed" class="video-message error" role="alert">教学素材加载失败 <el-button link @click="load(true)">重试</el-button></div>
    <p v-else-if="!resultsOnly && !state && loading" class="video-message" role="status">正在加载教学素材…</p>
    <template v-if="state">
      <template v-if="!resultsOnly">
      <form class="video-search" @submit.prevent="search()">
        <el-input v-model="query" aria-label="素材检索关键词" placeholder="可输入具体需求，如：真空中羽毛与铁球下落实验" maxlength="160" clearable :disabled="busy || working" />
        <el-button native-type="submit" type="primary" :icon="Refresh" :disabled="!canSearch" :loading="busy || working">{{ busy ? '检索中' : remaining ? `${remaining}秒后可检索` : '检索素材' }}</el-button>
        <el-button :disabled="!canSearch" @click="search(true)">按教案推荐</el-button>
      </form>
      <div v-if="statusText || state.message" class="video-message" :class="{ error: state.status === 'error' }" role="status">
        <p v-if="statusText">{{ statusText }}</p><p v-if="state.message && state.message !== statusText">{{ state.message }}</p>
      </div>
      <div class="video-meta"><span>推荐依据为搜索标题与摘要，视频内容与可播放性需预览确认。</span><a :href="state.fallback_url" target="_blank" rel="noopener noreferrer">去 B 站搜索 ↗</a></div>
      <details v-if="state.needs.length" class="video-needs"><summary>查看本次视频需求（{{ state.needs.length }}）</summary><div v-for="need in state.needs" :key="need.id"><strong>{{ need.section }}</strong><p>{{ need.purpose }}</p><span>关键词：{{ need.keywords.join(' / ') }}</span></div></details>
      <p v-if="textbook" class="preview-note">本次结合教材《{{ textbook.book_title }}》· {{ textbook.chapter_title }}补充检索词，视频用途依据当前教案。</p>
      </template>
      <div v-if="state.items.length" class="video-group">
        <h4>推荐候选 <span>{{ state.items.length }}</span></h4>
        <div class="video-grid"><LessonVideoCard v-for="item in state.items" :key="item.id" :item="item" :lesson-id="lessonId" /></div>
      </div>
      <div v-if="!resultsOnly || state.selected.length" class="video-group">
        <h4>已保存素材 <span>{{ state.selected.length }}</span></h4>
        <div v-if="state.selected.length" class="video-grid">
          <LessonVideoCard v-for="item in state.selected" :key="item.id" :item="item" :lesson-id="lessonId" removable :disabled="working" @remove="remove(item)" />
        </div>
        <p v-else class="selected-empty">可粘贴 B 站链接手动添加教学视频；推荐视频点击标题即可观看。</p>
      </div>
    </template>

    <el-dialog v-model="showManual" title="添加 B 站教学视频" width="min(540px, 94vw)" :close-on-click-modal="!working">
      <el-form label-position="top" @submit.prevent="addManual">
        <el-form-item label="资源完整链接"><el-input v-model="form.url" placeholder="https://www.bilibili.com/video/BV…/" maxlength="2048" /></el-form-item>
        <el-form-item label="资源标题"><el-input v-model="form.title" maxlength="256" /></el-form-item>
        <el-form-item label="教学环节"><el-input v-model="form.section" placeholder="如：情境导入、实验探究" maxlength="100" /></el-form-item>
        <el-form-item label="素材用途"><el-input v-model="form.purpose" type="textarea" :rows="3" placeholder="说明素材如何配合当前教案" maxlength="400" show-word-limit /></el-form-item>
        <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
        <p class="preview-note">请先在 B 站预览确认。这里只保存视频引用，后续可随时移除。</p>
        <el-button native-type="submit" type="primary" :loading="working">保存到本教案</el-button>
      </el-form>
    </el-dialog>
  </section>
</template>

<style scoped>
.lesson-videos { margin-top: 30px; padding-top: 27px; border-top: 1px solid #e2e8f0; }
.video-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; margin-bottom: 17px; }.video-heading h3 { display: flex; align-items: center; gap: 8px; margin: 0; font-size: 16px; }.video-heading h3 .el-icon { color: #0891b2; }.video-heading p { margin: 9px 0 0; color: #64748b; font-size: 12px; line-height: 1.7; }
.video-search { display: flex; flex-wrap: wrap; gap: 8px; }.video-search .el-input { flex: 1 1 240px; min-width: 0; }.video-search .el-button { margin: 0; }.video-message { padding: 12px 14px; background: #f8fafc; border-radius: 8px; color: #64748b; font-size: 13px; line-height: 1.8; margin: 14px 0; }.video-message p { margin: 0; }.video-message.error, .form-error { color: #b45309; }.video-meta { display: flex; flex-wrap: wrap; gap: 10px; justify-content: space-between; color: #64748b; font-size: 12px; line-height: 1.7; margin: 13px 0; }a { color: #0e7490; text-decoration: none; }a:hover { text-decoration: underline; }
.video-needs { background: #f0fdfa; border-radius: 8px; padding: 12px 14px; font-size: 12px; color: #0e7490; margin-bottom: 14px; overflow-wrap: anywhere; }.video-needs p { margin: 5px 0; line-height: 1.7; }.video-needs blockquote { margin: 0 0 10px; padding-left: 10px; border-left: 2px solid #99d5d2; color: #475569; }.video-needs details { color: #64748b; margin-top: 8px; }summary { cursor: pointer; }
.video-group { margin-top: 22px; }.video-group > h4 { margin: 0 0 13px; font-size: 14px; }.video-group > h4 span { color: #64748b; font-size: 12px; padding-left: 7px; }.video-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 15px; }.selected-empty { color: #64748b; font-size: 12px; line-height: 1.8; padding: 14px; background: #f8fafc; border-radius: 8px; }
.supplement-group { margin-top: 18px; padding-top: 14px; border-top: 1px dashed #cbd5e1; }.supplement-group h5 { font-size: 13px; margin: 0 0 6px; }.supplement-group > p { font-size: 12px; color: #64748b; margin: 0 0 12px; }
.preview-note { color: #64748b; font-size: 12px; line-height: 1.8; }.form-error { font-size: 13px; }
@media (max-width: 1100px) { .video-grid { grid-template-columns: 1fr; } }
@media (max-width: 760px) { .video-heading { flex-wrap: wrap; }.video-search .el-input { flex-basis: 100%; } }
</style>
