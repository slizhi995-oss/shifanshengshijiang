<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { trialVideosApi } from '@/api/trialVideos'

const props = defineProps<{ videoId: number; title: string }>()
const root = ref<HTMLImageElement>()
const fallback = '/images/trial-video-cover.svg'
const source = ref(fallback)
let observer: IntersectionObserver | null = null
let objectUrl = ''
let disposed = false

async function load() {
  observer?.disconnect()
  try {
    const blob = await trialVideosApi.cover(props.videoId)
    if (disposed) return
    objectUrl = URL.createObjectURL(blob)
    source.value = objectUrl
  } catch { /* 封面不可用时继续显示默认课堂图片。 */ }
}

onMounted(() => {
  if (!root.value) return
  observer = new IntersectionObserver(entries => {
    if (entries.some(entry => entry.isIntersecting)) void load()
  }, { rootMargin: '200px' })
  observer.observe(root.value)
})

onUnmounted(() => {
  disposed = true
  observer?.disconnect()
  if (objectUrl) URL.revokeObjectURL(objectUrl)
})
</script>

<template>
  <img ref="root" :src="source" :alt="`${title}的视频封面`" @error="source = fallback" />
</template>

<style scoped>
img { display: block; width: 100%; height: 100%; object-fit: cover; }
</style>
