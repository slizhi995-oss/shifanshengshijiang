<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { trialVideosApi, videoSize, type TrialVideo } from '@/api/trialVideos'
import { subjectOptions } from '@/constants/textbooks'
import TrialVideoUploader from '@/components/TrialVideoUploader.vue'
import TrialVideoPlayer from '@/components/TrialVideoPlayer.vue'

const source = ref('example')
const rows = ref<TrialVideo[]>([])
const total = ref(0)
const page = ref(1)
const used = ref(0)
const capacity = ref(0)
const loading = ref(false)
const saving = ref(false)
const uploadVisible = ref(false)
const editor = ref(false)
const selected = ref<TrialVideo | null>(null)
const player = ref<InstanceType<typeof TrialVideoPlayer>>()
const form = reactive({ title: '', subject: '', presenter_name: '', presenter_type: 'student', is_public: true })
let requestNumber = 0

async function load(reset = false) {
  if (reset) page.value = 1
  const currentRequest = ++requestNumber
  loading.value = true
  try {
    const result = await trialVideosApi.admin(source.value, page.value)
    if (currentRequest !== requestNumber) return
    rows.value = result.items
    total.value = result.total
    used.value = result.used_bytes || 0
    capacity.value = result.total_bytes || 0
  } finally { if (currentRequest === requestNumber) loading.value = false }
}

function edit(video: TrialVideo) {
  selected.value = video
  Object.assign(form, { title: video.title, subject: video.subject,
    presenter_name: video.author, presenter_type: video.presenter_type, is_public: video.is_public })
  editor.value = true
}

async function save() {
  if (!selected.value) return
  saving.value = true
  try {
    await trialVideosApi.update(selected.value.id, form)
    editor.value = false
    await load()
    ElMessage.success('示例已更新')
  } finally { saving.value = false }
}

async function takedown(video: TrialVideo) {
  let reason: string
  try {
    const result = await ElMessageBox.prompt('填写下架原因，学生将无法自行重新公开该视频。', '下架同学试讲', {
      inputValidator: value => Boolean(value?.trim()) || '请填写下架原因', inputType: 'textarea',
    })
    reason = result.value
  } catch { return }
  await trialVideosApi.takedown(video.id, reason)
  await load()
}

async function remove(video: TrialVideo) {
  try { await ElMessageBox.confirm('确定删除原视频？此操作不可恢复，已有分析报告保留。', '删除视频', { type: 'warning' }) }
  catch { return }
  await trialVideosApi.remove(video.id)
  await load()
}

function uploaded() {
  uploadVisible.value = false
  source.value = 'example'
  load(true)
}

onMounted(() => { load().catch(() => {}) })
</script>

<template>
  <div>
    <div class="management-header"><div><h2>试讲视频管理</h2><p>视频库已用 {{ videoSize(used) }} / {{ videoSize(capacity) }}</p></div><el-button type="primary" @click="uploadVisible = true">上传优秀示例</el-button></div>
    <el-tabs v-model="source" @tab-change="load(true)"><el-tab-pane label="优秀试讲示例" name="example" /><el-tab-pane label="同学试讲" name="student" /></el-tabs>
    <el-table v-loading="loading" :data="rows" empty-text="暂无视频">
      <el-table-column prop="title" label="标题" min-width="180" />
      <el-table-column prop="subject" label="学科" width="100" />
      <el-table-column prop="author" label="讲授者" width="110" />
      <el-table-column v-if="source === 'example'" label="类型" width="110"><template #default="{ row }">{{ row.presenter_type === 'teacher' ? '教师示范' : '学生示范' }}</template></el-table-column>
      <el-table-column label="状态" min-width="120"><template #default="{ row }"><el-tag :type="row.blocked ? 'danger' : row.is_public ? 'success' : 'info'">{{ row.file_status === 'deleted' ? '已删除' : !row.available ? '已到期' : row.blocked ? '已下架' : row.is_public ? '已公开' : '未公开' }}</el-tag><p v-if="row.moderation_reason" class="moderation-reason">{{ row.moderation_reason }}</p></template></el-table-column>
      <el-table-column label="大小" width="110"><template #default="{ row }">{{ videoSize(row.file_size) }}</template></el-table-column>
      <el-table-column label="操作" min-width="220"><template #default="{ row }">
        <el-button link type="primary" :disabled="!row.available" @click="player?.open(row)">观看</el-button>
        <el-button v-if="source === 'example'" link :disabled="!row.available" @click="edit(row)">编辑 / 上下架</el-button>
        <el-button v-else link type="warning" :disabled="row.blocked || !row.available" @click="takedown(row)">下架</el-button>
        <el-button link type="danger" :disabled="!row.available" @click="remove(row)">删除</el-button>
      </template></el-table-column>
    </el-table>
    <el-pagination v-if="total > 20" v-model:current-page="page" :page-size="20" :total="total" layout="prev, pager, next" @current-change="load()" />
    <el-dialog v-model="uploadVisible" title="上传优秀试讲示例" width="min(650px, 94vw)" :close-on-click-modal="false" destroy-on-close><TrialVideoUploader source="example" @uploaded="uploaded" /></el-dialog>
    <el-dialog v-model="editor" title="编辑优秀示例" width="min(550px, 94vw)">
      <el-form label-position="top">
        <el-form-item label="标题"><el-input v-model="form.title" maxlength="200" /></el-form-item>
        <el-form-item label="学科"><el-select v-model="form.subject"><el-option v-for="subject in subjectOptions" :key="subject" :value="subject" :label="subject" /></el-select></el-form-item>
        <el-form-item label="讲授者姓名"><el-input v-model="form.presenter_name" maxlength="64" /></el-form-item>
        <el-form-item label="示范类型"><el-radio-group v-model="form.presenter_type"><el-radio label="student">学生示范</el-radio><el-radio label="teacher">教师示范</el-radio></el-radio-group></el-form-item>
        <el-form-item label="前端展示"><el-switch v-model="form.is_public" active-text="上架" inactive-text="下架" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="editor = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>
    <TrialVideoPlayer ref="player" />
  </div>
</template>

<style scoped>
.management-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.management-header h2 { margin: 0 0 8px; }
.management-header p, .moderation-reason { color: #64748b; font-size: 12px; }
.el-pagination { margin-top: 20px; }
</style>
