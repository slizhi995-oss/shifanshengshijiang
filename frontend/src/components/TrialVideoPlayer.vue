<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { trialVideosApi, type TrialVideo } from '@/api/trialVideos'
import TrialVideoComments from '@/components/TrialVideoComments.vue'

const auth = useAuthStore()
const visible = ref(false)
const loading = ref(false)
const title = ref('')
const url = ref('')
const failed = ref(false)
const selected = ref<TrialVideo | null>(null)
const focusCommentId = ref<number>()
let requestNumber = 0

async function open(video: TrialVideo, commentId?: number) {
  const currentRequest = ++requestNumber
  visible.value = true
  title.value = video.title
  selected.value = video
  focusCommentId.value = commentId
  url.value = ''
  failed.value = false
  loading.value = true
  try {
    const result = await trialVideosApi.playback(video.id)
    if (currentRequest === requestNumber && visible.value) url.value = result.url
  } catch {
    if (currentRequest === requestNumber) failed.value = true
  } finally {
    if (currentRequest === requestNumber) loading.value = false
  }
}

function close() {
  requestNumber++
  url.value = ''
  loading.value = false
  selected.value = null
}

defineExpose({ open })
</script>

<template>
  <el-dialog v-model="visible" :title="title" width="min(900px, 94vw)" top="5vh" destroy-on-close @close="close">
    <div v-loading="loading" class="trial-player">
      <video v-if="url" :src="url" controls playsinline preload="metadata"
        controlslist="nodownload noremoteplayback" disablepictureinpicture
        @contextmenu.prevent @error="failed = true" />
      <el-empty v-if="failed" description="视频暂时无法播放，请重新打开；若格式不兼容，请上传 MP4 或 WebM" />
    </div>
    <TrialVideoComments v-if="visible && selected?.source === 'student' && url && (auth.userRole === 'student' || auth.userRole === 'admin')" :key="selected.id" :video-id="selected.id" :focus-comment-id="focusCommentId" />
  </el-dialog>
</template>

<style scoped>
.trial-player { min-height: 220px; }
video { display: block; width: 100%; max-height: 55vh; background: #0f172a; border-radius: 8px; }
</style>
