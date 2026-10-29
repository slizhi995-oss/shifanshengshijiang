<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { trialVideosApi, type TrialVideo } from '@/api/trialVideos'
import { useAuthStore } from '@/stores/auth'
import { subjectOptions } from '@/constants/textbooks'
import TrialVideoPlayer from '@/components/TrialVideoPlayer.vue'
import TrialVideoCard from '@/components/TrialVideoCard.vue'
import TrialVideoLibrary from '@/components/TrialVideoLibrary.vue'

const route = useRoute()
const auth = useAuthStore()
const active = ref(route.query.tab === 'mine' && auth.userRole === 'student' ? 'mine' : route.query.tab === 'student' ? 'student' : 'example')
const rows = ref<TrialVideo[]>([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)
const player = ref<InstanceType<typeof TrialVideoPlayer>>()
const deletingId = ref<number | null>(null)
let requestNumber = 0
const sections = computed(() => subjectOptions.map(subject => ({ subject,
  teachers: rows.value.filter(video => video.subject === subject && video.presenter_type === 'teacher'),
  students: rows.value.filter(video => video.subject === subject && video.presenter_type === 'student'),
})).filter(section => section.teachers.length || section.students.length))

async function load(reset = false) {
  if (reset) page.value = 1
  const currentRequest = ++requestNumber
  if (active.value === 'mine') {
    rows.value = []
    total.value = 0
    loading.value = false
    return
  }
  loading.value = true
  try {
    const result = await trialVideosApi.publicList(active.value, page.value)
    if (currentRequest !== requestNumber) return
    rows.value = result.items
    total.value = result.total
  } finally {
    if (currentRequest === requestNumber) loading.value = false
  }
}

async function remove(video: TrialVideo) {
  if (deletingId.value !== null || !video.can_delete) return
  try {
    await ElMessageBox.confirm(`确定删除“${video.title}”？删除后将从同学试讲中移除，已有分析报告仍保留。`,
      '删除我的试讲视频', { type: 'warning', confirmButtonText: '删除视频', cancelButtonText: '取消' })
  } catch { return }
  deletingId.value = video.id
  try {
    await trialVideosApi.remove(video.id)
    ElMessage.success('视频已删除')
    if (rows.value.length === 1 && page.value > 1) page.value--
    await load()
  } finally { deletingId.value = null }
}

let navigationRequest = 0
watch(() => route.fullPath, async () => {
  const request = ++navigationRequest
  const videoId = Number(route.query.video)
  const commentId = Number(route.query.comment)
  if (Number.isInteger(videoId) && videoId > 0) active.value = 'student'
  try {
    await load(true)
    if (!Number.isInteger(videoId) || videoId <= 0) return
    const video = await trialVideosApi.detail(videoId)
    if (request === navigationRequest) await player.value?.open(video, Number.isInteger(commentId) && commentId > 0 ? commentId : undefined)
  } catch { /* API errors already show a message; keep the video list available. */ }
}, { immediate: true })
</script>

<template>
  <div class="trial-learning">
    <header><h2>试讲学习</h2><p>观摩优秀课堂，交流试讲实践。</p></header>
    <el-tabs v-model="active" @tab-change="load(true)">
      <el-tab-pane label="优秀试讲示例" name="example" />
      <el-tab-pane label="同学试讲" name="student" />
      <el-tab-pane v-if="auth.userRole === 'student'" label="我的上传" name="mine" />
    </el-tabs>
    <TrialVideoLibrary v-if="active === 'mine'" />
    <div v-else v-loading="loading" class="learning-content">
      <el-empty v-if="!loading && !rows.length" :description="active === 'example' ? '暂未发布优秀试讲示例' : '暂时没有同学公开试讲视频'" />
      <template v-if="active === 'example'">
        <section v-for="section in sections" :key="section.subject" class="subject-section">
          <h3>{{ section.subject }}</h3>
          <div v-for="group in [{ label: '教师示范', items: section.teachers }, { label: '学生示范', items: section.students }]" :key="group.label">
            <template v-if="group.items.length">
              <h4>{{ group.label }}</h4>
              <div class="video-grid">
                <TrialVideoCard v-for="video in group.items" :key="video.id" :video="video" @play="player?.open($event)" />
              </div>
            </template>
          </div>
        </section>
      </template>
      <div v-else class="video-grid">
        <TrialVideoCard v-for="video in rows" :key="video.id" :video="video" show-subject
          :deleting="deletingId === video.id" :delete-disabled="deletingId !== null && deletingId !== video.id"
          @play="player?.open($event)" @remove="remove" />
      </div>
    </div>
    <el-pagination v-if="total > 100" v-model:current-page="page" :page-size="100" :total="total" layout="prev, pager, next" @current-change="load()" />
    <TrialVideoPlayer ref="player" />
  </div>
</template>

<style scoped>
.trial-learning { max-width: 1250px; margin: 0 auto; }
header h2 { margin: 0 0 8px; color: #0f172a; font-size: 26px; }
header p { color: #64748b; margin-bottom: 24px; }
.learning-content { min-height: 240px; }
.subject-section { margin: 16px 0 32px; }
.subject-section h3 { font-size: 21px; padding-left: 12px; border-left: 4px solid #0891b2; color: #0f172a; }
.subject-section h4 { color: #475569; font-size: 15px; margin: 20px 0 12px; }
.video-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 280px), 1fr)); gap: 28px 20px; }
</style>
