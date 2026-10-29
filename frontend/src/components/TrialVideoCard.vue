<script setup lang="ts">
import { Delete, VideoPlay } from '@element-plus/icons-vue'
import { videoDate, type TrialVideo } from '@/api/trialVideos'
import TrialVideoCover from '@/components/TrialVideoCover.vue'

defineProps<{ video: TrialVideo; showSubject?: boolean; deleting?: boolean; deleteDisabled?: boolean }>()
defineEmits<{ play: [video: TrialVideo]; remove: [video: TrialVideo] }>()

function shortDate(value: string | null) {
  const date = videoDate(value)
  return date === '—' ? date : date.split(' ')[0]
}
</script>

<template>
  <article class="video-card">
    <button class="video-cover" :aria-label="`观看${video.author}的试讲：${video.title}`" @click="$emit('play', video)">
      <TrialVideoCover :key="video.id" :video-id="video.id" :title="video.title" />
      <span class="cover-shade" aria-hidden="true"></span>
      <el-icon class="cover-play" aria-hidden="true"><VideoPlay /></el-icon>
      <span v-if="showSubject" class="cover-subject">{{ video.subject }}</span>
    </button>
    <div class="video-heading">
      <h5><button class="video-title" :title="video.title" @click="$emit('play', video)">{{ video.title }}</button></h5>
      <el-button v-if="video.can_delete" text size="small" class="video-delete" :icon="Delete"
        :aria-label="`删除我的试讲视频：${video.title}`" :loading="deleting" :disabled="deleteDisabled"
        @click="$emit('remove', video)" />
    </div>
    <div class="video-meta">
      <span class="video-author" :title="video.author"><span class="author-label">讲授</span>{{ video.author }}</span>
      <span v-if="video.source === 'student' && video.college" class="video-college" :title="video.college">{{ video.college }}</span>
      <span class="video-date" :title="videoDate(video.published_at || video.created_at)">
        · {{ shortDate(video.published_at || video.created_at) }}
      </span>
    </div>
  </article>
</template>

<style scoped>
.video-card { min-width: 0; }
.video-cover { position: relative; display: block; width: 100%; aspect-ratio: 16 / 9; padding: 0; overflow: hidden; border: 0; border-radius: 8px; background: #164e63; color: white; cursor: pointer; }
.cover-shade { position: absolute; inset: 0; background: linear-gradient(180deg, transparent 60%, #0f172a80); }
.cover-play { position: absolute; left: 12px; bottom: 10px; font-size: 23px; filter: drop-shadow(0 1px 3px #0006); transition: transform .2s; }
.video-cover:hover .cover-play { transform: scale(1.15); }
.cover-subject { position: absolute; right: 12px; bottom: 11px; font-size: 12px; line-height: 20px; text-shadow: 0 1px 3px #0008; }
.video-heading { display: flex; align-items: flex-start; gap: 8px; margin-top: 12px; }
h5 { flex: 1; min-width: 0; margin: 0; font-size: 16px; line-height: 24px; font-weight: 500; color: #1e293b; }
.video-title { display: -webkit-box; width: 100%; padding: 0; border: 0; background: transparent; color: inherit; font: inherit; text-align: left; cursor: pointer; overflow: hidden; overflow-wrap: anywhere; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.video-title:hover { color: #0891b2; }
.video-meta { display: flex; align-items: center; flex-wrap: wrap; column-gap: 7px; row-gap: 3px; margin-top: 4px; color: #8a919f; font-size: 12px; line-height: 20px; }
.video-author { display: inline-flex; align-items: center; gap: 5px; max-width: 100%; overflow-wrap: anywhere; }
.author-label { flex-shrink: 0; padding: 0 2px; border: 1px solid currentColor; border-radius: 3px; font-size: 10px; line-height: 13px; }
.video-college { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%; }
.video-date { white-space: nowrap; }
.video-delete { flex-shrink: 0; margin: 0; padding: 4px; color: #8a919f; }
.video-delete:not(:disabled):hover, .video-delete:not(:disabled):focus-visible { color: #dc2626; background: #fef2f2; }
.video-cover:focus-visible, .video-title:focus-visible { outline: 3px solid #0891b2; outline-offset: 2px; }
</style>
