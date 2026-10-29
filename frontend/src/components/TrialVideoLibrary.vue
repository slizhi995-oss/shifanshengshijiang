<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { trialVideosApi, videoDate, videoSize, type TrialVideo, type VideoAnalysis } from '@/api/trialVideos'
import { subjectOptions } from '@/constants/textbooks'
import TrialVideoPlayer from '@/components/TrialVideoPlayer.vue'

const props = withDefaults(defineProps<{ instructor?: boolean }>(), { instructor: false })
const rows = ref<TrialVideo[]>([])
const page = ref(1)
const total = ref(0)
const loading = ref(false)
const saving = ref(false)
const player = ref<InstanceType<typeof TrialVideoPlayer>>()
const editor = ref(false)
const selected = ref<TrialVideo | null>(null)
const form = reactive({ title: '', subject: '', is_public: false })
const report = ref<VideoAnalysis | null>(null)
const reportVisible = ref(false)
const deletingId = ref<number | null>(null)

async function refresh() {
  loading.value = true
  try {
    const result = await (props.instructor ? trialVideosApi.instructor(page.value) : trialVideosApi.mine(page.value))
    rows.value = result.items
    total.value = result.total
  } finally { loading.value = false }
}

function edit(video: TrialVideo) {
  selected.value = video
  Object.assign(form, { title: video.title, subject: video.subject, is_public: video.is_public })
  editor.value = true
}

async function save() {
  if (!selected.value) return
  if (form.is_public && (!form.title.trim() || !form.subject)) {
    ElMessage.warning('公开前请填写标题并选择学科')
    return
  }
  saving.value = true
  try {
    await trialVideosApi.update(selected.value.id, form)
    editor.value = false
    ElMessage.success('视频信息已更新')
    await refresh()
  } finally { saving.value = false }
}

async function remove(video: TrialVideo) {
  if (deletingId.value !== null) return
  try {
    await ElMessageBox.confirm('删除后无法继续播放，已有分析报告仍保留。确定删除？', '删除视频', { type: 'warning' })
  } catch { return }
  deletingId.value = video.id
  try {
    await trialVideosApi.remove(video.id)
    ElMessage.success('视频已删除，同学试讲中将不再展示，已有分析报告保留')
    await refresh()
  } finally { deletingId.value = null }
}

async function viewReport(video: TrialVideo) {
  report.value = await trialVideosApi.analysis(video.id)
  reportVisible.value = true
}

onMounted(() => { refresh().catch(() => {}) })
defineExpose({ refresh })
</script>

<template>
  <section class="trial-library">
    <div class="library-heading"><h3>{{ instructor ? '学生自主试讲视频' : '我的上传' }}</h3><el-button @click="refresh">刷新</el-button></div>
    <p v-if="!instructor" class="library-note">在这里观看、编辑或删除你上传的视频。新上传的视频默认公开，删除后将从同学试讲中移除，已有分析报告保留。</p>
    <p v-else class="library-note">仅展示由你在对应批次指导的学生视频，包括私密视频。</p>
    <el-table v-loading="loading" :data="rows" empty-text="暂无视频">
      <el-table-column label="视频" min-width="190">
        <template #default="{ row }"><strong>{{ row.title }}</strong><div class="library-note">{{ row.subject || '未填写学科' }} · {{ videoSize(row.file_size) }}</div></template>
      </el-table-column>
      <el-table-column v-if="instructor" prop="author" label="学生" width="100" />
      <el-table-column label="状态" min-width="150">
        <template #default="{ row }">
          <el-tag :type="row.blocked ? 'danger' : row.is_public ? 'success' : 'info'">
            {{ row.file_status === 'expired' || !row.available && row.file_status !== 'deleted' ? '已到期' : row.file_status === 'deleted' ? '已删除' : row.blocked ? '已下架' : row.is_public ? '公开' : '私密' }}
          </el-tag>
          <div v-if="row.expires_at && row.available" class="library-note">保留至 {{ videoDate(row.expires_at) }}</div>
          <div v-if="row.blocked" class="library-note">{{ row.moderation_reason }}</div>
        </template>
      </el-table-column>
      <el-table-column label="操作" min-width="240">
        <template #default="{ row }">
          <el-button link type="primary" :disabled="!row.available" @click="player?.open(row)">观看</el-button>
          <el-button v-if="!instructor" link :disabled="!row.available" @click="edit(row)">编辑 / 可见范围</el-button>
          <el-button link @click="viewReport(row)">分析报告</el-button>
          <el-button v-if="!instructor" type="danger" plain size="small" :loading="deletingId === row.id"
            :disabled="!row.available || deletingId !== null && deletingId !== row.id" @click="remove(row)">删除视频</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination v-if="total > 20" v-model:current-page="page" :page-size="20" :total="total" layout="prev, pager, next" @current-change="refresh" />
    <TrialVideoPlayer ref="player" />
    <el-dialog v-model="editor" title="编辑视频" width="min(520px, 94vw)">
      <el-form label-position="top">
        <el-form-item label="标题"><el-input v-model="form.title" maxlength="200" /></el-form-item>
        <el-form-item label="学科"><el-select v-model="form.subject" clearable><el-option v-for="subject in subjectOptions" :key="subject" :label="subject" :value="subject" /></el-select></el-form-item>
        <el-form-item label="可见范围">
          <el-radio-group v-model="form.is_public" :disabled="selected?.blocked">
            <el-radio :label="false">私密</el-radio><el-radio :label="true">公开</el-radio>
          </el-radio-group>
        </el-form-item>
        <p class="library-note">{{ selected?.blocked ? '管理员已下架此视频，不能自行重新公开。' : '公开后展示真实姓名；改为私密后，原视频再保留 15 天。' }}</p>
      </el-form>
      <template #footer><el-button @click="editor = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>
    <el-dialog v-model="reportVisible" title="试讲分析报告" width="min(700px, 94vw)">
      <template v-if="report?.status === 'completed' && report.analysis">
        <p v-if="report.analysis.overall_score !== undefined">综合得分：{{ report.analysis.overall_score }}</p>
        <p v-if="report.analysis.transcript" class="report-transcript">{{ report.analysis.transcript }}</p>
        <ul><li v-for="(suggestion, index) in report.analysis.suggestions || []" :key="index">{{ suggestion }}</li></ul>
      </template>
      <el-empty v-else :description="report?.status === 'processing' ? '正在分析，请稍后刷新查看' : report?.error || '暂无分析报告'" />
    </el-dialog>
  </section>
</template>

<style scoped>
.trial-library { margin-top: 24px; padding: 24px; border-radius: 14px; background: white; color: #334155; border: 1px solid #e2e8f0; }
.library-heading { display: flex; align-items: center; justify-content: space-between; }
.library-heading h3 { margin: 0; font-size: 18px; }
.library-note { font-size: 12px; color: #64748b; line-height: 1.7; margin: 6px 0; }
.report-transcript { white-space: pre-wrap; line-height: 1.8; }
.el-pagination { margin-top: 18px; }
</style>
