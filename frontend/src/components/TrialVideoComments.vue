<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { trialVideosApi, type TrialVideoComment } from '@/api/trialVideos'
import TrialVideoCommentThread from '@/components/TrialVideoCommentThread.vue'

const props = defineProps<{ videoId: number; focusCommentId?: number }>()
const auth = useAuthStore()
const rows = ref<TrialVideoComment[]>([])
const total = ref(0)
const rootTotal = ref(0)
const refreshVersion = ref(0)
const focusThread = ref<TrialVideoComment[]>([])
const page = ref(1)
const loading = ref(false)
const posting = ref(false)
const deletingId = ref<number | null>(null)
const draft = ref('')
const loadError = ref('')
const available = ref(false)
const canReply = computed(() => auth.isAuthenticated && auth.userRole === 'student' && available.value)
const canPost = computed(() => canReply.value && !!draft.value.trim() && !posting.value)
function replyAdded() { total.value++ }
function refreshComments() { focusThread.value = []; return loadComments() }
let requestNumber = 0
let generation = 0

function errorMessage(error: any, fallback: string) {
  const detail = error.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

async function loadComments(targetPage = page.value) {
  const request = ++requestNumber
  loading.value = true
  loadError.value = ''
  try {
    const result = await trialVideosApi.comments(props.videoId, targetPage)
    if (request !== requestNumber) return
    if (!result.items.length && result.total > 0 && targetPage > Math.ceil(result.total / 20)) {
      await loadComments(Math.ceil(result.total / 20))
      return
    }
    rows.value = result.items
    rootTotal.value = result.total
    total.value = result.comment_count ?? result.total
    page.value = targetPage
    available.value = true
    refreshVersion.value++
  } catch (error: any) {
    if (request !== requestNumber) return
    loadError.value = errorMessage(error, '评论暂时加载失败，请重试')
    if ([401, 403, 404, 410, 422].includes(error.response?.status)) available.value = false
  } finally {
    if (request === requestNumber) loading.value = false
  }
}

async function submit() {
  if (!canPost.value) return
  const currentGeneration = generation
  const content = draft.value.trim()
  posting.value = true
  try {
    const comment = await trialVideosApi.addComment(props.videoId, content)
    if (currentGeneration !== generation) return
    draft.value = ''
    // Keep the successful comment visible even if the following refresh fails.
    rows.value = [comment, ...(page.value === 1 ? rows.value.filter(row => row.id !== comment.id) : [])].slice(0, 20)
    total.value++
    page.value = 1
    ElMessage.success('评论已发表')
    await loadComments(1)
  } catch (error: any) {
    if (currentGeneration !== generation) return
    loadError.value = errorMessage(error, '评论发表失败，请重试')
    if ([401, 403, 404, 410].includes(error.response?.status)) available.value = false
  } finally {
    if (currentGeneration === generation) posting.value = false
  }
}

async function remove(comment: TrialVideoComment) {
  if (!comment.can_delete || deletingId.value !== null) return
  const currentGeneration = generation
  try {
    await ElMessageBox.confirm('确定删除这条评论？其他同学的回复将保留。', '删除评论', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
    })
  } catch { return }
  if (currentGeneration !== generation) return
  deletingId.value = comment.id
  try {
    await trialVideosApi.removeComment(props.videoId, comment.id)
    if (currentGeneration !== generation) return
    focusThread.value = []
    if (!comment.reply_count) rows.value = rows.value.filter(row => row.id !== comment.id)
    total.value = Math.max(0, total.value - 1)
    const targetPage = !rows.value.length && page.value > 1 ? page.value - 1 : page.value
    ElMessage.success('评论已删除')
    await loadComments(targetPage)
  } catch (error: any) {
    if (currentGeneration === generation) loadError.value = errorMessage(error, '评论删除失败，请重试')
  } finally {
    if (currentGeneration === generation) deletingId.value = null
  }
}

watch(() => [props.videoId, props.focusCommentId], async () => {
  generation++
  const currentGeneration = generation
  requestNumber++
  focusThread.value = []
  rows.value = []
  total.value = 0
  rootTotal.value = 0
  page.value = 1
  draft.value = ''
  posting.value = false
  deletingId.value = null
  available.value = false
  let targetPage = 1
  if (props.focusCommentId) {
    try {
      const context = await trialVideosApi.commentContext(props.videoId, props.focusCommentId)
      if (currentGeneration !== generation) return
      focusThread.value = context.thread
      targetPage = context.root_page
    } catch (error: any) {
      if (currentGeneration !== generation) return
      ElMessage.info(errorMessage(error, '这条评论暂时无法查看'))
    }
  }
  await loadComments(targetPage)
}, { immediate: true })

onUnmounted(() => { generation++; requestNumber++ })
</script>

<template>
  <section class="video-comments" aria-label="试讲视频评论区">
    <div class="comments-heading">
      <h3>评论交流 <span>{{ total }}</span></h3>
      <el-button text size="small" :disabled="loading" @click="refreshComments">刷新</el-button>
    </div>
    <div v-if="auth.isAuthenticated && auth.userRole === 'student'" class="comment-composer">
      <el-input v-model="draft" aria-label="评论内容" type="textarea" :autosize="{ minRows: 3, maxRows: 6 }"
        :maxlength="1000" show-word-limit :disabled="posting || !available"
        placeholder="分享你的观察、建议或教学思路…" @keydown.ctrl.enter.prevent="submit" />
      <div class="composer-footer">
        <span>Ctrl + Enter 发表</span>
        <el-button type="primary" :loading="posting" :disabled="!canPost" @click="submit">发表评论</el-button>
      </div>
    </div>
    <p v-else-if="!auth.isAuthenticated" class="comment-signin">登录后即可参与评论。</p>
    <el-alert v-if="loadError" class="comment-error" :title="loadError" type="warning" :closable="false">
      <el-button link type="primary" @click="loadComments()">重新加载</el-button>
    </el-alert>
    <div v-loading="loading" class="comments-list">
      <p v-if="!loading && !loadError && !rows.length" class="comments-empty">还没有评论，来分享你的看法吧。</p>
      <TrialVideoCommentThread v-for="comment in rows" :key="comment.id" :comment="comment" :video-id="videoId"
        :can-reply="canReply" :refresh-version="refreshVersion" :deleting-id="deletingId"
        :focus-thread="focusThread"
        @remove="remove" @added="replyAdded" />
    </div>
    <el-pagination v-if="rootTotal > 20" :current-page="page" :page-size="20" :total="rootTotal"
      :disabled="loading || posting || deletingId !== null" layout="prev, pager, next" @current-change="loadComments" />
  </section>
</template>

<style scoped>
.video-comments { margin-top: 24px; padding-top: 22px; border-top: 1px solid #e2e8f0; color: #334155; font-family: "Microsoft YaHei", "PingFang SC", Arial, sans-serif; }
.comments-heading { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.comments-heading h3 { display: flex; align-items: center; gap: 10px; margin: 0; font-size: 17px; font-weight: 600; color: #0f172a; }
.comments-heading h3 span { padding: 2px 8px; border-radius: 6px; background: #f1f5f9; color: #64748b; font-size: 12px; font-weight: 400; }
.comment-composer :deep(.el-textarea__inner) { padding: 12px; line-height: 1.7; border-radius: 8px; }
.composer-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 10px; }
.composer-footer > span { color: #94a3b8; font-size: 12px; }
.comment-error { margin-top: 18px; }
.comments-list { min-height: 72px; margin-top: 12px; }
.comments-empty, .comment-signin { padding: 18px 0; color: #94a3b8; font-size: 14px; text-align: center; }
.el-pagination { justify-content: center; margin-top: 20px; }
</style>
