<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Search, Refresh, Files, UploadFilled, Document } from '@element-plus/icons-vue'
import api from '@/utils/request'

interface Semester {
  id: number
  name: string
  status: string
}

interface Submission {
  id: number
  student_name: string
  student_code: string
  semester_name: string
  task_title: string
  status: string
  created_at: string
  lesson_plan_path?: string
  lesson_plan_name?: string
  video_path?: string
  video_name?: string
  total_score?: number
}

const semesters = ref<Semester[]>([])
const submissions = ref<Submission[]>([])
const loading = ref(false)
const uploadVisible = ref(false)
const uploadLoading = ref(false)

const filters = ref({
  semester_id: '',
  keyword: '',
  status: '',
})

const pagination = ref({
  page: 1,
  pageSize: 20,
  total: 0,
})

const statusOptions = [
  { label: '全部', value: '' },
  { label: '待审核', value: 'pending' },
  { label: '已通过', value: 'approved' },
  { label: '已退回', value: 'rejected' },
]

const statusMap: Record<string, { label: string; type: string }> = {
  pending: { label: '待审核', type: 'warning' },
  approved: { label: '已通过', type: 'success' },
  rejected: { label: '已退回', type: 'danger' },
}

const fetchSemesters = async () => {
  try {
    const res: any = await api.get('/semesters')
    semesters.value = res
  } catch {
    semesters.value = []
  }
}

const fetchSubmissions = async () => {
  loading.value = true
  try {
    const params: any = {
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
    }
    if (filters.value.semester_id) params.semester_id = filters.value.semester_id
    if (filters.value.keyword) params.keyword = filters.value.keyword
    if (filters.value.status) params.status = filters.value.status

    const res: any = await api.get('/admin/submissions', { params })
    if (res?.items) {
      submissions.value = res.items
      pagination.value.total = res.total || res.items.length
    } else if (Array.isArray(res)) {
      submissions.value = res
      pagination.value.total = res.length
    } else {
      submissions.value = []
    }
  } catch {
    submissions.value = []
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.value.page = 1
  fetchSubmissions()
}

const handleReset = () => {
  filters.value = { semester_id: '', keyword: '', status: '' }
  pagination.value.page = 1
  fetchSubmissions()
}

const handlePageChange = (page: number) => {
  pagination.value.page = page
  fetchSubmissions()
}

const downloadFile = (filePath: string, fileName: string) => {
  const url = filePath.startsWith('http') ? filePath : `/uploads/${filePath}`
  const a = document.createElement('a')
  a.href = url
  a.download = fileName
  a.target = '_blank'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

const hasFiles = (row: Submission) => !!(row.lesson_plan_path || row.video_path)

const uploadForm = ref({
  title: '',
  description: '',
  semester_id: '',
  file: null as File | null,
})

const uploadFileList = ref<any[]>([])

const handleFileChange = (file: any) => {
  uploadForm.value.file = file.raw
  uploadFileList.value = [file]
}

const handleUpload = async () => {
  if (!uploadForm.value.title) {
    ElMessage.warning('请填写材料标题')
    return
  }
  if (!uploadForm.value.file) {
    ElMessage.warning('请选择要上传的文件')
    return
  }
  uploadLoading.value = true
  try {
    const formData = new FormData()
    formData.append('title', uploadForm.value.title)
    formData.append('description', uploadForm.value.description)
    if (uploadForm.value.semester_id) formData.append('semester_id', uploadForm.value.semester_id)
    formData.append('file', uploadForm.value.file)
    await api.post('/admin/materials/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    ElMessage.success('上传成功')
    uploadVisible.value = false
    uploadForm.value = { title: '', description: '', semester_id: '', file: null }
    uploadFileList.value = []
    fetchSubmissions()
  } catch {
    ElMessage.error('上传失败，请重试')
  } finally {
    uploadLoading.value = false
  }
}

const totalFiles = computed(() =>
  submissions.value.filter(s => s.lesson_plan_path || s.video_path).length
)

onMounted(() => {
  fetchSemesters()
  fetchSubmissions()
})
</script>

<template>
  <div class="materials-page">
    <!-- 页面标题 -->
    <div class="page-header mb-6">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-xl font-bold text-gray-800 flex items-center gap-2">
            <el-icon color="#ef4444"><Files /></el-icon>
            试讲材料
          </h2>
          <p class="text-sm text-gray-500 mt-1">查看、收集、上传及下载试讲相关材料</p>
        </div>
        <el-button type="primary" :icon="UploadFilled" @click="uploadVisible = true">
          上传材料
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div class="stat-mini-card">
        <div class="stat-mini-value text-blue-600">{{ pagination.total }}</div>
        <div class="stat-mini-label">提交总数</div>
      </div>
      <div class="stat-mini-card">
        <div class="stat-mini-value text-emerald-600">{{ totalFiles }}</div>
        <div class="stat-mini-label">含文件提交</div>
      </div>
      <div class="stat-mini-card">
        <div class="stat-mini-value text-amber-600">
          {{ submissions.filter(s => s.status === 'pending').length }}
        </div>
        <div class="stat-mini-label">待审核</div>
      </div>
      <div class="stat-mini-card">
        <div class="stat-mini-value text-emerald-600">
          {{ submissions.filter(s => s.status === 'approved').length }}
        </div>
        <div class="stat-mini-label">已通过</div>
      </div>
    </div>

    <!-- 筛选栏 -->
    <el-card shadow="never" class="filter-card mb-4">
      <div class="flex flex-wrap gap-3 items-end">
        <div>
          <div class="filter-label">试讲时段</div>
          <el-select
            v-model="filters.semester_id"
            placeholder="全部时段"
            clearable
            style="width: 200px"
          >
            <el-option
              v-for="s in semesters"
              :key="s.id"
              :label="s.name"
              :value="s.id"
            />
          </el-select>
        </div>
        <div>
          <div class="filter-label">状态</div>
          <el-select v-model="filters.status" style="width: 120px">
            <el-option
              v-for="opt in statusOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </div>
        <div>
          <div class="filter-label">关键词</div>
          <el-input
            v-model="filters.keyword"
            placeholder="学生姓名 / 学号"
            :prefix-icon="Search"
            style="width: 200px"
            @keyup.enter="handleSearch"
          />
        </div>
        <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
        <el-button :icon="Refresh" @click="handleReset">重置</el-button>
      </div>
    </el-card>

    <!-- 材料列表 -->
    <el-card shadow="never" class="table-card">
      <el-table
        :data="submissions"
        v-loading="loading"
        stripe
        style="width: 100%"
        empty-text="暂无试讲材料提交记录"
      >
        <el-table-column label="学生" min-width="120">
          <template #default="{ row }">
            <div class="font-medium text-gray-800">{{ row.student_name }}</div>
            <div class="text-xs text-gray-400">{{ row.student_code }}</div>
          </template>
        </el-table-column>
        <el-table-column label="试讲时段" prop="semester_name" min-width="160" show-overflow-tooltip />
        <el-table-column label="任务" prop="task_title" min-width="120" show-overflow-tooltip />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag
              :type="(statusMap[row.status]?.type || 'info') as any"
              size="small"
            >
              {{ statusMap[row.status]?.label || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="附件" width="220">
          <template #default="{ row }">
            <div class="flex flex-wrap gap-1">
              <el-tag v-if="row.lesson_plan_path" size="small" type="primary">教案</el-tag>
              <el-tag v-if="row.video_path" size="small" type="success">视频</el-tag>
              <span v-if="!row.lesson_plan_path && !row.video_path" class="text-gray-300 text-sm">无附件</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="提交时间" prop="created_at" width="160">
          <template #default="{ row }">
            <span class="text-sm text-gray-500">
              {{ row.created_at ? new Date(row.created_at).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" align="center" fixed="right">
          <template #default="{ row }">
            <template v-if="hasFiles(row)">
              <el-button
                v-if="row.lesson_plan_path"
                size="small"
                type="primary"
                :icon="Download"
                link
                @click="downloadFile(row.lesson_plan_path!, row.lesson_plan_name || '教案.pdf')"
              >教案</el-button>
              <el-button
                v-if="row.video_path"
                size="small"
                type="success"
                :icon="Download"
                link
                @click="downloadFile(row.video_path!, row.video_name || '视频.mp4')"
              >视频</el-button>
            </template>
            <span v-else class="text-gray-300 text-xs">—</span>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="flex justify-end mt-4" v-if="pagination.total > pagination.pageSize">
        <el-pagination
          v-model:current-page="pagination.page"
          :page-size="pagination.pageSize"
          :total="pagination.total"
          layout="prev, pager, next, total"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- 上传材料对话框 -->
    <el-dialog v-model="uploadVisible" title="上传试讲材料" width="500px" :close-on-click-modal="false">
      <el-form label-width="80px" class="space-y-1">
        <el-form-item label="标题" required>
          <el-input v-model="uploadForm.title" placeholder="材料标题（如：评分标准模板）" />
        </el-form-item>
        <el-form-item label="试讲时段">
          <el-select v-model="uploadForm.semester_id" placeholder="选择关联时段（可选）" clearable style="width: 100%">
            <el-option v-for="s in semesters" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明">
          <el-input
            v-model="uploadForm.description"
            type="textarea"
            :rows="3"
            placeholder="材料用途说明（可选）"
          />
        </el-form-item>
        <el-form-item label="文件" required>
          <el-upload
            v-model:file-list="uploadFileList"
            :auto-upload="false"
            :limit="1"
            :on-change="handleFileChange"
            drag
            accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.zip,.mp4"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽文件到此处，或 <em>点击上传</em></div>
            <template #tip>
              <div class="el-upload__tip text-gray-400 text-xs">支持 PDF / Word / PPT / Excel / ZIP / MP4，单文件不超过 100MB</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploadLoading" @click="handleUpload">上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.materials-page { max-width: 1400px; }

.stat-mini-card {
  background: white;
  border-radius: 10px;
  padding: 14px 16px;
  border: 1px solid #f0f0f0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.stat-mini-value { font-size: 24px; font-weight: 700; }
.stat-mini-label { font-size: 12px; color: #9ca3af; margin-top: 2px; }

.filter-card :deep(.el-card__body) { padding: 16px; }
.filter-label { font-size: 12px; color: #6b7280; margin-bottom: 4px; }
.table-card :deep(.el-card__body) { padding: 16px; }
</style>
