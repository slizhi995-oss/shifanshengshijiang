<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ChatDotRound, Delete, MoreFilled, UserFilled } from '@element-plus/icons-vue'
import { trialVideosApi, videoDate, type TrialVideoComment } from '@/api/trialVideos'

const props = withDefaults(defineProps<{
  comment: TrialVideoComment
  videoId: number
  canReply: boolean
  refreshVersion: number
  deletingId: number | null
  depth?: number
  replyTo?: string
  focusThread?: TrialVideoComment[]
}>(), { depth: 1 })
const emit = defineEmits<{ remove: [comment: TrialVideoComment]; added: [] }>()
const replies = ref<TrialVideoComment[]>([])
const replyCount = ref(props.comment.reply_count || 0)
const expanded = ref(false)
const loadedPage = ref(0)
const loading = ref(false)
const replying = ref(false)
const posting = ref(false)
const draft = ref('')
const error = ref('')
const input = ref<{ focus: () => void }>()
const entry = ref<HTMLElement>()
const focused = computed(() => props.focusThread?.[props.focusThread.length - 1]?.id === props.comment.id)
const focusChild = computed(() => {
  const index = props.focusThread?.findIndex(row => row.id === props.comment.id) ?? -1
  return index >= 0 ? props.focusThread?.[index + 1] : undefined
})
const remaining = computed(() => Math.max(0, replyCount.value - replies.value.length))
let requestNumber = 0
let disposed = false

function commentTime(value: string) {
  const date = new Date(value.endsWith('Z') || /[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`)
  if (Number.isNaN(date.getTime())) return '—'
  const now = new Date()
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  const time = date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  if (date.toDateString() === now.toDateString()) return `今天 ${time}`
  if (date.toDateString() === yesterday.toDateString()) return `昨天 ${time}`
  const monthDay = `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
  return `${date.getFullYear() === now.getFullYear() ? '' : `${date.getFullYear()}-`}${monthDay} ${time}`
}

function errorMessage(problem: any, fallback: string) {
  const detail = problem.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

async function loadReplies(reset = false) {
  const request = ++requestNumber
  const targetPage = reset ? 1 : loadedPage.value + 1
  loading.value = true
  error.value = ''
  try {
    const result = await trialVideosApi.comments(props.videoId, targetPage, props.comment.id, 3)
    if (disposed || request !== requestNumber) return
    const existing = reset ? [] : [...replies.value]
    if (focusChild.value) existing.push(focusChild.value)
    replies.value = [...new Map([...existing, ...result.items].map(row => [row.id, row])).values()]
      .sort((a, b) => a.id - b.id)
    replyCount.value = result.total
    loadedPage.value = targetPage
  } catch (problem: any) {
    if (!disposed && request === requestNumber) error.value = errorMessage(problem, '回复加载失败，请重试')
  } finally {
    if (!disposed && request === requestNumber) loading.value = false
  }
}

async function expand() {
  expanded.value = true
  if (!loadedPage.value) await loadReplies(true)
}

async function startReply() {
  replying.value = true
  await nextTick()
  input.value?.focus()
}

async function submitReply() {
  if (!props.canReply || posting.value || !draft.value.trim()) return
  posting.value = true
  error.value = ''
  try {
    const reply = await trialVideosApi.addComment(props.videoId, draft.value.trim(), props.comment.id)
    if (disposed) return
    draft.value = ''
    replying.value = false
    replyCount.value++
    emit('added')
    ElMessage.success('回复已发表')
    expanded.value = true
    // Keep the submitted reply visible even if the refresh fails or older replies are folded.
    if (!loadedPage.value) await loadReplies(true)
    if (!replies.value.some(row => row.id === reply.id)) replies.value.push(reply)
  } catch (problem: any) {
    if (!disposed) error.value = errorMessage(problem, '回复发表失败，请重试')
  } finally {
    if (!disposed) posting.value = false
  }
}

watch(() => props.comment.reply_count, count => { replyCount.value = count || 0 })
watch(() => props.refreshVersion, () => {
  if (focusChild.value) expanded.value = true
  if (expanded.value && replyCount.value) void loadReplies(true)
  else { requestNumber++; replies.value = []; loadedPage.value = 0; loading.value = false }
}, { immediate: true })
watch(focused, async isFocused => {
  if (!isFocused) return
  await nextTick()
  if (!disposed) entry.value?.scrollIntoView({ block: 'center', behavior: 'smooth' })
}, { immediate: true })
onUnmounted(() => { disposed = true; requestNumber++ })
</script>

<template>
  <article ref="entry" class="comment-entry" :class="{ 'comment-entry-reply': depth > 1, 'comment-focused': focused }" :data-comment-id="comment.id" :data-depth="depth">
    <el-avatar class="comment-avatar" :size="depth === 1 ? 44 : 32"
      :src="comment.is_deleted ? undefined : comment.author_avatar || undefined" :alt="`${comment.author_name}的头像`">
      <el-icon v-if="comment.is_deleted"><UserFilled /></el-icon>
      <span v-else>{{ comment.author_name.slice(0, 1) }}</span>
    </el-avatar>
    <div class="comment-meta">
      <div class="comment-author">
        <strong>{{ comment.is_deleted ? '原评论' : comment.author_name }}</strong>
        <span v-if="comment.is_video_author && !comment.is_deleted" class="video-author-badge">作者</span>
        <span v-if="replyTo && !comment.is_deleted" class="reply-target">回复 {{ replyTo }}</span>
      </div>
      <el-dropdown v-if="comment.can_delete" class="comment-menu" trigger="click" @command="emit('remove', comment)">
        <el-button text size="small" class="comment-menu-button" :icon="MoreFilled" :loading="deletingId === comment.id"
          :disabled="deletingId !== null && deletingId !== comment.id" :aria-label="`${comment.author_name}的评论操作`" />
        <template #dropdown><el-dropdown-menu><el-dropdown-item command="delete" :icon="Delete">删除评论</el-dropdown-item></el-dropdown-menu></template>
      </el-dropdown>
    </div>
    <p class="comment-content" :class="{ 'comment-deleted': comment.is_deleted }">{{ comment.is_deleted ? '该评论已删除' : comment.content }}</p>
    <div class="comment-publication"><time :datetime="comment.created_at" :title="videoDate(comment.created_at)">{{ commentTime(comment.created_at) }}</time></div>
    <div class="comment-actions">
      <el-button v-if="canReply && !comment.is_deleted" text size="small" class="reply-action"
        :icon="ChatDotRound" :aria-label="`回复${comment.author_name}的评论`" @click="startReply">回复<span v-if="replyCount" class="reply-count">{{ replyCount }}</span></el-button>
    </div>
    <div v-if="replying" class="reply-composer">
      <el-input ref="input" v-model="draft" :aria-label="`回复${comment.author_name}的内容`" type="textarea"
        :autosize="{ minRows: 2, maxRows: 5 }" :maxlength="1000" show-word-limit :disabled="posting || !canReply"
        :placeholder="`回复 ${comment.author_name}…`" @keydown.ctrl.enter.prevent="submitReply" />
      <div class="reply-composer-actions">
        <el-button text size="small" :disabled="posting" @click="replying = false">取消</el-button>
        <el-button type="primary" size="small" :loading="posting" :disabled="!canReply || !draft.trim()" @click="submitReply">发表回复</el-button>
      </div>
    </div>
    <div v-if="expanded && (replies.length || loading)" class="comment-replies" :class="{ 'comment-replies-flat': depth >= 2 }">
      <TrialVideoCommentThread v-for="reply in replies" :key="reply.id" :comment="reply" :video-id="videoId"
        :depth="depth + 1" :can-reply="canReply" :refresh-version="refreshVersion" :deleting-id="deletingId"
        :focus-thread="focusThread"
        :reply-to="comment.is_deleted ? '已删除的评论' : comment.author_name"
        @remove="emit('remove', $event)" @added="emit('added')" />
    </div>
    <div v-if="replyCount || loading" class="reply-controls">
      <el-button v-if="!expanded" link type="primary" :aria-expanded="false" @click="expand">展开 {{ replyCount }} 条回复</el-button>
      <template v-else>
        <el-button v-if="remaining || loading" link type="primary" :loading="loading" @click="loadReplies()">{{ loading ? '正在加载回复' : `展开剩余 ${remaining} 条回复` }}</el-button>
        <el-button link :aria-expanded="true" @click="expanded = false">收起回复</el-button>
      </template>
    </div>
    <p v-if="error" role="alert" class="reply-error">{{ error }} <el-button v-if="!replying" link type="primary" @click="loadReplies(!loadedPage)">重试</el-button></p>
  </article>
</template>

<style scoped>
.comment-entry { position: relative; min-width: 0; padding: 18px 0 18px 58px; border-bottom: 1px solid #f1f5f9; }
.comment-focused { background: #ecfeff; border-radius: 8px; box-shadow: 0 0 0 6px #ecfeff; }
.comment-avatar { position: absolute; left: 0; top: 18px; background: #e8f3f5; color: #527a84; font-size: 16px; }
.comment-entry-reply { padding: 12px 0 12px 44px; border-bottom: 0; }
.comment-entry-reply > .comment-avatar { top: 12px; font-size: 13px; }
.comment-meta { display: flex; align-items: center; justify-content: space-between; gap: 8px 16px; min-height: 21px; }
.comment-author { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; min-width: 0; }
.comment-author strong { color: #8a8a8a; font-size: 14px; line-height: 21px; font-weight: 400; overflow-wrap: anywhere; }
.video-author-badge { font-size: 12px; color: #0891b2; }
.reply-target { color: #999; font-size: 12px; overflow-wrap: anywhere; }
.comment-menu { flex-shrink: 0; }
.comment-menu-button { height: 22px; padding: 2px 4px; color: #999; }
.comment-content { margin: 3px 0 0; color: #303133; line-height: 1.7; font-size: 15px; white-space: pre-wrap; overflow-wrap: anywhere; }
.comment-publication { margin-top: 6px; color: #999; font-size: 12px; line-height: 18px; }
.comment-deleted { color: #94a3b8; }
.comment-actions { display: flex; align-items: center; gap: 16px; margin-top: 3px; }
.comment-actions:empty { display: none; }
.comment-actions .el-button { height: 24px; margin: 0; padding: 2px 0; color: #888; font-size: 12px; }
.comment-actions :deep(.el-icon) { font-size: 16px; }
.reply-count { margin-left: 5px; }
.comment-actions .reply-action:hover { color: #0891b2; }
.reply-composer { margin: 10px 0; }
.reply-composer-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }
.comment-replies { margin-top: 8px; }
.comment-replies-flat { margin-left: -44px; }
.reply-controls { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin-top: 8px; }
.reply-controls .el-button { margin: 0; font-size: 12px; }
.reply-error { color: #b45309; font-size: 12px; }
@media (max-width: 600px) { .comment-meta { gap: 8px; } .comment-content { font-size: 14px; } }
</style>
