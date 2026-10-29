<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Delete, VideoPlay } from '@element-plus/icons-vue'
import { lessonVideosApi, resourceTypeLabels, type LessonVideo } from '@/api/lessonVideos'

const props = defineProps<{ item: LessonVideo; lessonId: number; removable?: boolean; disabled?: boolean }>()
defineEmits<{ remove: [] }>()
const metadata = ref<{ availability: string; cover_url: string; title: string }>()
const imageFailed = ref(false)
let revision = 0
const unavailable = computed(() => metadata.value?.availability === 'unavailable' || !href.value)
const cover = computed(() => metadata.value?.cover_url || props.item.cover_url || '')
const title = computed(() => (metadata.value?.title || props.item.title).replace(/(?:_哔哩哔哩_bilibili|\s*[-_]\s*哔哩哔哩(?:视频)?)\s*$/i, '').trim())
const href = computed(() => {
  if (/^BV[0-9A-Za-z]{10}$/.test(props.item.bvid || '')) return `https://www.bilibili.com/video/${props.item.bvid}/` + (props.item.page > 1 ? `?p=${props.item.page}` : '')
  try {
    const url = new URL(props.item.url)
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : ''
  } catch { return '' }
})
const siteName = computed(() => {
  if (props.item.site_name) return props.item.site_name
  if (props.item.bvid) return 'B 站'
  try { return new URL(props.item.url).hostname } catch { return '来源网站' }
})
const typeLabel = computed(() => resourceTypeLabels[props.item.resource_type || (props.item.bvid ? 'video' : 'webpage')])
watch(cover, () => { imageFailed.value = false })
watch(() => [props.lessonId, props.item.bvid], async () => {
  const current = ++revision
  metadata.value = undefined
  imageFailed.value = false
  if (!/^BV[0-9A-Za-z]{10}$/.test(props.item.bvid || '')) return
  try {
    const result = await lessonVideosApi.metadata(props.lessonId, props.item.bvid)
    if (current === revision) metadata.value = result
  } catch { /* A missing cover never prevents opening the original video page. */ }
}, { immediate: true })
onBeforeUnmount(() => { ++revision })
</script>

<template>
  <article class="video-card" :class="{ 'selected-video': removable, unavailable }">
    <a class="video-cover" :href="unavailable ? undefined : href" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer" :aria-label="`在${siteName}打开：${title}`" :aria-disabled="unavailable">
      <img v-if="cover && !imageFailed" :src="cover" :alt="`${title}的资源封面`" loading="lazy" decoding="async" referrerpolicy="no-referrer" @error="imageFailed = true" />
      <div v-else class="cover-placeholder"><el-icon :size="32"><VideoPlay /></el-icon><span>{{ unavailable ? '资源暂不可用' : `${typeLabel} · 封面暂不可用` }}</span></div>
      <span class="cover-source">{{ siteName }} · {{ typeLabel }}</span>
    </a>
    <div class="video-body">
      <div class="video-card-meta"><span class="video-label">{{ removable ? item.source === 'manual' ? '手动添加' : '已选素材' : item.ranking === 'ai' ? 'AI 初筛 · 待预览确认' : '搜索候选 · 待确认' }}</span><el-button v-if="removable" :icon="Delete" text type="danger" :disabled="disabled" aria-label="移除资源" @click="$emit('remove')" /></div>
      <h5><span v-if="unavailable" class="unavailable-title">{{ title }}</span><a v-else class="video-title" :href="href" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer">{{ title }}</a></h5>
      <p v-if="unavailable" class="unavailable-note">该资源暂不可用，可重新检索或移除此引用。</p>
      <p class="video-section">{{ removable ? '教学环节' : '适用环节' }}：{{ item.section }}</p><p>{{ item.purpose }}</p>
      <p v-if="item.reason" class="video-reason">{{ item.reason }}</p>
      <details v-if="item.evidence_quote"><summary>查看匹配依据</summary><p>标题或摘要原文：{{ item.evidence_quote }}</p></details>
      <details v-if="item.snippet"><summary>查看搜索摘要</summary><p>{{ item.snippet }}</p></details>
    </div>
  </article>
</template>

<style scoped>
.video-card { border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; min-width: 0; background: #fff; }.selected-video { border-color: #bae6e7; }
.video-cover { display: block; position: relative; aspect-ratio: 16 / 9; overflow: hidden; background: #edf4f8; }.video-cover img { display: block; width: 100%; height: 100%; object-fit: cover; transition: transform .2s; }.video-cover:hover img { transform: scale(1.025); }.cover-placeholder { width: 100%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; color: #7594a5; background: linear-gradient(135deg, #eff8fa, #e9eff8); font-size: 12px; }.cover-source { position: absolute; bottom: 10px; left: 12px; padding: 3px 8px; border-radius: 5px; color: #fff; background: #172b40b3; font-size: 11px; }
.video-body { display: flex; flex-direction: column; gap: 10px; padding: 17px 18px 19px; }.video-card-meta { display: flex; justify-content: space-between; align-items: center; min-height: 18px; }.video-card-meta .el-button { padding: 0 4px; height: 20px; }.video-label { font-size: 11px; color: #0e7490; }h5 { margin: 0; font-size: 15px; line-height: 1.65; overflow-wrap: anywhere; }.video-title { color: #1e293b; text-decoration: none; }.video-title:hover { color: #0891b2; text-decoration: underline; }.video-title:focus-visible, .video-cover:focus-visible { outline: 2px solid #0891b2; outline-offset: -2px; }p { margin: 0; color: #64748b; font-size: 12px; line-height: 1.8; overflow-wrap: anywhere; }.video-section { color: #334155; }.video-reason { background: #f0fdfa; padding: 10px; border-radius: 7px; color: #0e7490; }details { font-size: 12px; color: #64748b; }summary { cursor: pointer; }details p { margin-top: 8px; max-height: 180px; overflow: auto; }.unavailable-note { color: #b45309; }.unavailable-title { color: #64748b; }
@media (max-width: 760px) { .video-body { padding: 15px; } }
</style>
