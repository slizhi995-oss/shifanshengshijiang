<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Collection, Download, Headset, Refresh, VideoPlay } from '@element-plus/icons-vue'
import { resourceCenterApi, type AudioLessonDetail, type LessonAudio } from '@/api/resourceCenter'
import LessonVideos from '@/components/LessonVideos.vue'

const props = defineProps<{ resourceLessonId?: number; lessonId?: number }>()
const emit = defineEmits<{ (event: 'results', visible: boolean): void }>()
const selectedId = ref<number>()
const detail = ref<AudioLessonDetail>()
const hasVideos = ref(false)
const hasResults = computed(() => !!detail.value?.audios.length || hasVideos.value)
const kind = ref('')
const playing = ref<LessonAudio>()
const audioUrl = ref('')
const audioLoading = ref(false)
const audioFailed = ref(false)
const audioElement = ref<HTMLAudioElement>()
const downloading = ref('')
const rematching = ref(false)
let detailRevision = 0
let audioRevision = 0
const audioKinds = computed(() => [...new Set(detail.value?.audios.map(item => item.audio_kind).filter(Boolean) || [])])
const visibleAudios = computed(() => detail.value?.audios.filter(item => !kind.value || item.audio_kind === kind.value) || [])
const sourceLabel = computed(() => detail.value ? [detail.value.source.book_title, detail.value.source.parent_title, detail.value.source.chapter_title].filter(Boolean).join(' · ') : '')
watch(hasResults, visible => emit('results', visible), { immediate: true })

function stopAudio() {
  ++audioRevision
  audioElement.value?.pause()
  if (audioUrl.value) URL.revokeObjectURL(audioUrl.value)
  audioUrl.value = ''
  playing.value = undefined
  audioLoading.value = false
  audioFailed.value = false
}

async function play(item: LessonAudio) {
  if (!selectedId.value) return
  const id = selectedId.value
  stopAudio()
  const revision = audioRevision
  playing.value = item
  audioLoading.value = true
  try {
    const blob = await resourceCenterApi.file(id, item.resource_id)
    if (revision !== audioRevision) return
    audioUrl.value = URL.createObjectURL(blob)
    await nextTick()
    if (revision === audioRevision) {
      try { await audioElement.value?.play() }
      catch { /* Native controls remain available if the browser blocks autoplay. */ }
    }
  } catch {
    if (revision === audioRevision) audioFailed.value = true
  } finally {
    if (revision === audioRevision) audioLoading.value = false
  }
}

async function download(item: LessonAudio) {
  if (!selectedId.value || downloading.value) return
  downloading.value = item.resource_id
  try {
    const blob = await resourceCenterApi.file(selectedId.value, item.resource_id)
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${item.unit_title}_${item.title}.mp3`.replace(/[\\/:*?"<>|]/g, '_')
    anchor.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch { ElMessage.error('音频下载失败，请重试') }
  finally { downloading.value = '' }
}

async function rematch() {
  if (!selectedId.value || rematching.value) return
  const revision = detailRevision
  rematching.value = true
  stopAudio()
  try {
    const result = await resourceCenterApi.rematch(selectedId.value)
    if (revision === detailRevision) { detail.value = result; kind.value = '' }
  } catch { /* Shared request handling reports explicit rematch failures. */ }
  finally { if (revision === detailRevision) rematching.value = false }
}

watch(() => [props.resourceLessonId, props.lessonId], async () => {
  const revision = ++detailRevision
  selectedId.value = undefined
  detail.value = undefined
  hasVideos.value = false
  kind.value = ''
  rematching.value = false
  stopAudio()
  try {
    const id = props.resourceLessonId || (props.lessonId ? (await resourceCenterApi.resolve(props.lessonId, true)).id : undefined)
    if (revision !== detailRevision || !id) return
    // Mount video retrieval independently so an audio failure cannot hide video results.
    selectedId.value = id
    const result = await resourceCenterApi.detail(id, true)
    if (revision === detailRevision) detail.value = result
  } catch { /* Optional background resources leave the lesson readable without an empty panel. */ }
}, { immediate: true })
onBeforeUnmount(() => { ++detailRevision; stopAudio() })
</script>

<template>
  <section v-show="hasResults" class="lesson-matched-resources" aria-label="教案配套资源">
    <header class="resources-heading"><div><span class="eyebrow">为本教案匹配</span><h2>配套资源</h2></div></header>
    <template v-if="detail?.audios.length">
      <div v-if="sourceLabel" class="source-note"><el-icon><Collection /></el-icon><span>{{ sourceLabel }}<template v-if="detail.source.printed_pages"> · 教材第 {{ detail.source.printed_pages }} 页</template></span></div>
          <div class="section-heading"><h3><el-icon><Headset /></el-icon> 配套音频 <span>{{ detail.audios.length }}</span></h3><el-button :icon="Refresh" :loading="rematching" @click="rematch">重新匹配音频</el-button></div>
          <div v-if="audioKinds.length > 1" class="kind-filters" aria-label="音频类型筛选">
            <el-button :type="kind === '' ? 'primary' : 'default'" round size="small" @click="kind = ''">全部</el-button>
            <el-button v-for="label in audioKinds" :key="label" :type="kind === label ? 'primary' : 'default'" round size="small" @click="kind = label">{{ label }}</el-button>
          </div>

          <section v-if="playing" v-loading="audioLoading" class="audio-player" aria-label="音频播放器">
            <div class="player-label"><el-icon><Headset /></el-icon><div><strong>{{ playing.title }}</strong><span>{{ playing.unit_title }}</span></div><el-button text @click="stopAudio">关闭</el-button></div>
            <audio v-if="audioUrl" ref="audioElement" :src="audioUrl" controls preload="metadata" @error="audioFailed = true" />
            <p v-if="audioFailed" class="error-text" role="alert">音频加载失败，可重新试听或下载后播放。</p>
            <p v-else-if="audioLoading" class="muted">正在加载音频…</p>
          </section>

          <div v-if="visibleAudios.length" class="audio-grid">
            <article v-for="item in visibleAudios" :key="item.resource_id" class="audio-card" :class="{ playing: playing?.resource_id === item.resource_id }">
              <div class="audio-card-top"><div class="audio-icon"><el-icon :size="23"><Headset /></el-icon></div><span class="audio-kind">{{ item.audio_kind || '教材音频' }}</span><span v-if="item.printed_page" class="page-tag">P{{ item.printed_page }}</span></div>
              <p class="unit-title">{{ item.unit_title }}</p><h4>{{ item.title }}</h4>
              <p class="audio-source">{{ item.stage }} · {{ item.series }} · {{ item.volume }}</p>
              <p class="match-reason">{{ item.reason }}</p>
              <details v-if="item.textbook_excerpt" class="textbook-excerpt"><summary>查看教材活动参考</summary><p>{{ item.textbook_excerpt }}</p></details>
              <p v-if="!item.available" class="error-text">音频文件暂不可用</p>
              <div class="card-actions"><el-button type="primary" plain :icon="VideoPlay" :disabled="!item.available" :loading="audioLoading && playing?.resource_id === item.resource_id" @click="play(item)">试听音频</el-button><el-button :icon="Download" :disabled="!item.available || !!downloading" :loading="downloading === item.resource_id" @click="download(item)">下载</el-button></div>
            </article>
          </div>
    </template>
    <LessonVideos v-if="selectedId" :key="selectedId" :lesson-id="selectedId" results-only @results="hasVideos = $event" />
  </section>
</template>

<style scoped>
.lesson-matched-resources { margin: 0 auto 24px; padding: 24px; max-width: 1100px; min-width: 0; border: 1px solid #e2e8f0; border-radius: 14px; background: #fff; color: #1e293b; }
.resources-heading { margin-bottom: 20px; }.eyebrow { color: #059669; font-size: 12px; font-weight: 600; }.resources-heading h2 { margin: 7px 0 0; font-size: 20px; }
.source-note { display: flex; gap: 8px; padding: 12px; border-radius: 8px; background: #f8fafc; color: #64748b; font-size: 12px; line-height: 1.7; margin-bottom: 16px; }.source-note .el-icon { flex-shrink: 0; margin-top: 3px; }
.section-heading { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; margin-bottom: 18px; }.section-heading h3 { display: flex; align-items: center; gap: 8px; font-size: 16px; margin: 0; }.section-heading h3 .el-icon { color: #0891b2; }.section-heading h3 span { font-size: 12px; background: #f1f5f9; color: #64748b; border-radius: 5px; padding: 2px 7px; }.muted { color: #94a3b8; font-size: 12px; }.kind-filters { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 18px; }.kind-filters .el-button { margin: 0; }
.lesson-matched-resources > :deep(.lesson-videos) { margin-top: 0; padding-top: 0; border-top: 0; }.audio-grid ~ :deep(.lesson-videos) { margin-top: 24px; padding-top: 24px; border-top: 1px solid #e2e8f0; }
.audio-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 17px; }.audio-card { display: flex; flex-direction: column; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px; min-width: 0; transition: border-color .2s; }.audio-card.playing { border-color: #22d3ee; }.audio-card-top { display: flex; align-items: center; gap: 10px; margin-bottom: 18px; }.audio-icon { width: 43px; height: 43px; display: grid; place-items: center; color: #0891b2; background: #ecfeff; border-radius: 12px; }.audio-kind { color: #0e7490; font-size: 12px; }.page-tag { margin-left: auto; color: #94a3b8; font-size: 12px; }.unit-title { margin: 0 0 6px; color: #64748b; font-size: 12px; line-height: 1.6; }.audio-card h4 { font-size: 15px; line-height: 1.65; margin: 0; overflow-wrap: anywhere; }.audio-source { color: #94a3b8; font-size: 12px; line-height: 1.7; margin: 9px 0 0; }.match-reason { font-size: 12px; line-height: 1.7; color: #0e7490; background: #f0fdfa; border-radius: 6px; padding: 8px 10px; margin: 14px 0; }.textbook-excerpt { margin-bottom: 18px; font-size: 12px; color: #64748b; }.textbook-excerpt summary { cursor: pointer; }.textbook-excerpt p { max-height: 180px; overflow: auto; white-space: pre-wrap; line-height: 1.7; overflow-wrap: anywhere; }.card-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: auto; padding-top: 3px; }.card-actions .el-button { margin: 0; }
.audio-player { border: 1px solid #a5f3fc; border-radius: 10px; background: #f0fdff; padding: 16px; margin-bottom: 20px; }.player-label { display: flex; gap: 11px; align-items: center; margin-bottom: 10px; color: #0891b2; }.player-label > div { flex: 1; min-width: 0; }.player-label strong { display: block; font-size: 13px; color: #334155; line-height: 1.5; overflow-wrap: anywhere; }.player-label span { display: block; font-size: 12px; color: #64748b; margin-top: 4px; }audio { display: block; width: 100%; height: 40px; }.error-text { color: #b45309; font-size: 12px; line-height: 1.6; }
@media (max-width: 760px) { .lesson-matched-resources { margin: 0 12px 16px; padding: 16px; }.audio-grid { grid-template-columns: 1fr; }.audio-card { padding: 16px; } }
</style>
