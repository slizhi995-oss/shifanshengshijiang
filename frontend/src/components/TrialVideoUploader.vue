<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { trialVideosApi, videoSize, type TrialVideo, type VideoOptions } from '@/api/trialVideos'

const props = withDefaults(defineProps<{
  source?: 'student' | 'example'
  evaluatedFile?: File
  analysisTaskId?: string
}>(), { source: 'student' })
const emit = defineEmits<{ uploaded: [file: File, video: TrialVideo]; busyChange: [busy: boolean] }>()
const options = ref<VideoOptions | null>(null)
const busy = ref(false)
const progress = ref(0)
const file = ref<File | null>(props.evaluatedFile || null)
const uploadRef = ref()
const form = reactive({ title: '', subject: '',
  presenter_name: '', presenter_type: 'student' })
const isExample = computed(() => props.source === 'example')

async function loadOptions() {
  options.value = await trialVideosApi.options()
}

function selectFile(upload: { raw?: File }) {
  file.value = upload.raw || null
}

async function submit() {
  if (!file.value || !options.value) return
  if (file.value.size > options.value.max_bytes) {
    ElMessage.warning(`单个视频不能超过 ${videoSize(options.value.max_bytes)}`)
    return
  }
  if (!form.title.trim() || !form.subject) {
    ElMessage.warning('请填写试讲课题并选择学科')
    return
  }
  if (isExample.value && !form.presenter_name.trim()) {
    ElMessage.warning('请填写讲授者姓名')
    return
  }
  const selected = file.value
  const data = new FormData()
  data.append('video', selected)
  data.append('source', props.source)
  data.append('is_public', 'true')
  if (props.analysisTaskId) data.append('analysis_task_id', props.analysisTaskId)
  for (const [key, value] of Object.entries(form)) {
    if (value !== null) data.append(key, String(value))
  }
  busy.value = true
  emit('busyChange', true)
  progress.value = 0
  try {
    const result = await trialVideosApi.upload(data, percent => { progress.value = percent })
    ElMessage.success(isExample.value ? '优秀示例已发布' : '视频已公开到同学试讲，可在“我的上传”中管理或删除')
    file.value = null
    uploadRef.value?.clearFiles()
    form.title = ''
    emit('uploaded', selected, result)
    if (!props.evaluatedFile) await loadOptions()
  } finally {
    busy.value = false
    emit('busyChange', false)
  }
}

onMounted(() => { loadOptions().catch(() => {}) })
</script>

<template>
  <el-form label-position="top" class="trial-upload-form" :disabled="busy">
    <el-alert v-if="!options" title="正在读取上传设置；若加载失败，请重试" type="info" :closable="false">
      <el-button link @click="loadOptions">重新加载</el-button>
    </el-alert>
    <template v-else>
      <div class="upload-fields">
        <el-form-item label="试讲课题">
          <el-input v-model="form.title" maxlength="200" placeholder="例如：牛顿第一定律试讲" />
        </el-form-item>
        <el-form-item label="学科">
          <el-select v-model="form.subject" placeholder="选择学科" clearable style="width:100%">
            <el-option v-for="subject in options.subjects" :key="subject" :label="subject" :value="subject" />
          </el-select>
        </el-form-item>
      </div>
      <template v-if="isExample">
        <div class="upload-fields">
          <el-form-item label="讲授者姓名"><el-input v-model="form.presenter_name" maxlength="64" /></el-form-item>
          <el-form-item label="示范类型">
            <el-radio-group v-model="form.presenter_type">
              <el-radio label="student">学生示范</el-radio><el-radio label="teacher">教师示范</el-radio>
            </el-radio-group>
          </el-form-item>
        </div>
      </template>
      <template v-else>
        <p class="upload-note">上传后将公开展示在“同学试讲”，姓名、学院使用账号资料，可在“我的上传”中管理或删除。</p>
      </template>
      <p v-if="evaluatedFile" class="upload-note">已评估视频：{{ evaluatedFile.name }}</p>
      <el-upload v-else ref="uploadRef" :auto-upload="false" :limit="1" :on-change="selectFile"
        :on-remove="() => { file = null }" :disabled="busy"
        accept=".mp4,.mov,.webm,.avi,.mkv,.flv,.wmv">
        <el-button :disabled="busy">选择视频文件</el-button>
        <template #tip>
          <div class="upload-note">单个视频最多 {{ videoSize(options.max_bytes) }}，建议使用 MP4 或 WebM。
            <template v-if="!isExample">个人已用 {{ videoSize(options.used_bytes) }} / {{ videoSize(options.user_max_bytes) }}。</template>
          </div>
        </template>
      </el-upload>
      <el-progress v-if="busy" :percentage="progress" :status="progress === 100 ? 'success' : undefined" />
      <p v-if="busy" class="upload-note">{{ progress === 100 ? '文件已发送，正在保存，请勿重复上传。' : '正在上传，请保持页面打开。' }}</p>
      <el-button type="primary" :loading="busy" :disabled="!file" class="upload-submit" @click="submit">
        {{ isExample ? '上传并发布示例' : '确认上传' }}
      </el-button>
    </template>
  </el-form>
</template>

<style scoped>
.trial-upload-form { width: 100%; text-align: left; }
.upload-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.upload-note { font-size: 12px; line-height: 1.7; color: #64748b; margin: 5px 0 14px; }
.upload-submit { margin-top: 18px; }
@media (max-width: 600px) { .upload-fields { grid-template-columns: 1fr; gap: 0; } }
</style>
