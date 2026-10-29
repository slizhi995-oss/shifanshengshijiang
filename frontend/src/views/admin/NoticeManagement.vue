<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount, shallowRef } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, View, Link, Paperclip, Cpu } from '@element-plus/icons-vue'
// @ts-ignore
import { Editor, Toolbar } from '@wangeditor/editor-for-vue'
import type { IEditorConfig, IToolbarConfig } from '@wangeditor/editor'
import '@wangeditor/editor/dist/css/style.css'
import api from '@/utils/request'
import { useAuthStore } from '@/stores/auth'

// AI 撰写助手
const aiDraftVisible = ref(false)
const aiDraftLoading = ref(false)
const aiDraftKeyPoints = ref('')
const aiDraftTone = ref('formal')
const aiDraftResult = ref('')

const authStore = useAuthStore()

interface Notice {
  id: number
  title: string
  content: string
  display_type: 'dialog' | 'marquee' | 'both'
  is_pinned: boolean
  is_published: boolean
  show_on_login: boolean // 新增：在登录页展示
  attachment_path?: string
  created_at: string
  updated_at: string
}

// 附件列表
interface Attachment {
  name: string
  url: string
  size?: number
}

const notices = ref<Notice[]>([])
const total = ref(0)
const loading = ref(false)
const readStats = ref<Record<number, number>>({})  // 公告已读统计

const query = reactive({
  page: 1,
  page_size: 10
})

// Dialog state
const dialogVisible = ref(false)
const dialogTitle = ref('发布公告')
const isEditing = ref(false)

const form = reactive({
  id: null as number | null,
  title: '',
  content: '',
  display_type: 'dialog' as 'dialog' | 'marquee' | 'both',
  is_pinned: false,
  is_published: true,
  show_on_login: false, // 新增：在登录页展示
  attachments: [] as Attachment[]
})

// 富文本编辑器相关
const editorRef = shallowRef()
const mode = 'default'

// 编辑器配置
const toolbarConfig: Partial<IToolbarConfig> = {
  excludeKeys: ['fullScreen']
}

const editorConfig: Partial<IEditorConfig> = {
  placeholder: '请输入公告内容...',
  MENU_CONF: {
    uploadImage: {
      async customUpload(file: File, insertFn: Function) {
        const formData = new FormData()
        formData.append('file', file)
        try {
          const res: any = await api.post('/notices/upload/image', formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
          })
          insertFn(res.url, res.alt, res.url)
        } catch (e) {
          ElMessage.error('图片上传失败')
        }
      }
    }
  }
}

// 编辑器创建后的回调
const handleCreated = (editor: any) => {
  editorRef.value = editor
}

// 组件销毁时销毁编辑器
onBeforeUnmount(() => {
  const editor = editorRef.value
  if (editor) editor.destroy()
})

// 附件上传
const uploadingAttachment = ref(false)
const handleUploadAttachment = async (options: any) => {
  const { file } = options
  const formData = new FormData()
  formData.append('file', file)
  
  uploadingAttachment.value = true
  try {
    const res: any = await api.post('/notices/upload/attachment', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    form.attachments.push({
      name: res.name,
      url: res.url,
      size: res.size
    })
    ElMessage.success('附件上传成功')
  } catch (e) {
    ElMessage.error('附件上传失败')
  } finally {
    uploadingAttachment.value = false
  }
  return false
}

const removeAttachment = (index: number) => {
  form.attachments.splice(index, 1)
}

const formatFileSize = (bytes: number) => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

const getAttachments = (notice: Notice): Attachment[] => {
  if (!notice.attachment_path) return []
  try {
    return JSON.parse(notice.attachment_path)
  } catch {
    return []
  }
}

const displayTypeOptions = [
  { value: 'dialog', label: '弹窗通知', desc: '用户登录后弹出通知窗口' },
  { value: 'marquee', label: '跑马灯', desc: '在页面顶部滚动显示' },
  { value: 'both', label: '弹窗+跑马灯', desc: '同时使用两种形式' }
]

const getDisplayTypeLabel = (type: string) => {
  const option = displayTypeOptions.find(o => o.value === type)
  return option?.label || type
}

const getDisplayTypeTag = (type: string) => {
  switch (type) {
    case 'dialog': return 'primary'
    case 'marquee': return 'success'
    case 'both': return 'warning'
    default: return 'info'
  }
}

const fetchNotices = async () => {
  loading.value = true
  try {
    const params = {
      page: query.page,
      page_size: query.page_size
    }
    const [noticesRes, statsRes]: any[] = await Promise.all([
      api.get('/notices', { params }),
      api.get('/notices/admin/read-stats')
    ])
    notices.value = noticesRes.items
    total.value = noticesRes.total
    readStats.value = statsRes.read_stats || {}
  } finally {
    loading.value = false
  }
}

const handlePageChange = (page: number) => {
  query.page = page
  fetchNotices()
}

const openCreateDialog = () => {
  dialogTitle.value = '发布公告'
  isEditing.value = false
  form.id = null
  form.title = ''
  form.content = ''
  form.display_type = 'dialog'
  form.is_pinned = false
  form.is_published = true
  form.show_on_login = false
  form.attachments = []
  dialogVisible.value = true
}

const openEditDialog = (row: Notice) => {
  dialogTitle.value = '编辑公告'
  isEditing.value = true
  form.id = row.id
  form.title = row.title
  form.content = row.content
  form.display_type = row.display_type
  form.is_pinned = row.is_pinned
  form.is_published = row.is_published
  form.show_on_login = row.show_on_login || false
  // 解析附件
  form.attachments = row.attachment_path ? JSON.parse(row.attachment_path) : []
  dialogVisible.value = true
}

const handleSubmit = async () => {
  if (!form.title.trim()) {
    ElMessage.warning('请输入公告标题')
    return
  }
  
  // 获取编辑器内容
  const editor = editorRef.value
  const htmlContent = editor?.getHtml() || ''
  
  if (!htmlContent || htmlContent === '<p><br></p>') {
    ElMessage.warning('请输入公告内容')
    return
  }

  try {
    const payload = {
      title: form.title,
      content: htmlContent,
      display_type: form.display_type,
      is_pinned: form.is_pinned,
      is_published: form.is_published,
      show_on_login: form.show_on_login,
      attachment_path: form.attachments.length > 0 ? JSON.stringify(form.attachments) : null
    }

    if (isEditing.value && form.id) {
      await api.put(`/notices/${form.id}`, payload)
      ElMessage.success('公告已更新')
    } else {
      await api.post('/notices', payload)
      ElMessage.success('公告已发布')
    }

    dialogVisible.value = false
    fetchNotices()
  } catch (error) {
    // Error handled by interceptor
  }
}

const handleDelete = async (row: Notice) => {
  try {
    await ElMessageBox.confirm('确定删除该公告吗？删除后无法恢复。', '删除确认', {
      type: 'warning'
    })
    await api.delete(`/notices/${row.id}`)
    ElMessage.success('公告已删除')
    fetchNotices()
  } catch (error) {
    // Cancelled or error
  }
}

const handleTogglePublish = async (row: Notice) => {
  try {
    await api.put(`/notices/${row.id}`, {
      is_published: !row.is_published
    })
    ElMessage.success(row.is_published ? '公告已取消发布' : '公告已发布')
    fetchNotices()
  } catch (error) {
    // Error handled by interceptor
  }
}

const handleTogglePin = async (row: Notice) => {
  try {
    await api.put(`/notices/${row.id}`, {
      is_pinned: !row.is_pinned
    })
    ElMessage.success(row.is_pinned ? '已取消置顶' : '已置顶')
    fetchNotices()
  } catch (error) {
    // Error handled by interceptor
  }
}

// Preview dialog
const previewVisible = ref(false)
const previewNotice = ref<Notice | null>(null)

const openPreview = (row: Notice) => {
  previewNotice.value = row
  previewVisible.value = true
}

// AI 撰写公告
const openAIDraft = () => {
  aiDraftKeyPoints.value = ''
  aiDraftTone.value = 'formal'
  aiDraftResult.value = ''
  aiDraftVisible.value = true
}

const generateAIDraft = async () => {
  if (!aiDraftKeyPoints.value.trim()) {
    ElMessage.warning('请输入公告要点')
    return
  }
  aiDraftLoading.value = true
  aiDraftResult.value = ''
  try {
    const res: any = await api.post('/admin/ai-notice-draft', {
      key_points: aiDraftKeyPoints.value,
      tone: aiDraftTone.value,
    })
    if (res.success && res.data?.content) {
      aiDraftResult.value = res.data.content
    } else {
      ElMessage.error(res.message || 'AI 生成失败')
    }
  } catch {
    ElMessage.error('AI 生成失败')
  } finally {
    aiDraftLoading.value = false
  }
}

const applyAIDraft = () => {
  if (!aiDraftResult.value) return
  const editor = editorRef.value
  if (editor) {
    editor.setHtml(`<p>${aiDraftResult.value.replace(/\n/g, '</p><p>')}</p>`)
  }
  aiDraftVisible.value = false
  ElMessage.success('AI 生成内容已填入编辑器')
}

onMounted(fetchNotices)
</script>

<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-2xl font-bold">公告管理</h2>
      <el-button type="primary" :icon="Plus" @click="openCreateDialog">发布公告</el-button>
    </div>

    <el-card>
      <el-empty v-if="notices.length === 0 && !loading" description="暂无公告，点击上方按钮发布" />
      <el-table v-else :data="notices" v-loading="loading" stripe>
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column label="显示方式" width="130">
          <template #default="scope">
            <el-tag :type="getDisplayTypeTag(scope.row.display_type)" size="small">
              {{ getDisplayTypeLabel(scope.row.display_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.is_published ? 'success' : 'info'" size="small">
              {{ scope.row.is_published ? '已发布' : '草稿' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="置顶" width="80" align="center">
          <template #default="scope">
            <el-switch
              :model-value="scope.row.is_pinned"
              @change="handleTogglePin(scope.row)"
              size="small"
            />
          </template>
        </el-table-column>
        <el-table-column label="登录页" width="80" align="center">
          <template #default="scope">
            <el-tag :type="scope.row.show_on_login ? 'success' : 'info'" size="small">
              {{ scope.row.show_on_login ? '显示' : '隐藏' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="已读人数" width="100" align="center">
          <template #default="scope">
            <el-tag type="info" size="small">
              {{ readStats[scope.row.id] || 0 }} 人
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="scope">
            {{ new Date(scope.row.created_at).toLocaleString() }}
          </template>
        </el-table-column>
        <el-table-column label="操作" fixed="right" width="240">
          <template #default="scope">
            <el-button size="small" :icon="View" @click="openPreview(scope.row)">预览</el-button>
            <el-button size="small" :icon="Edit" type="primary" @click="openEditDialog(scope.row)">编辑</el-button>
            <el-button size="small" :icon="Delete" type="danger" @click="handleDelete(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="flex justify-end mt-4">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- Create/Edit Dialog -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="900px" top="5vh">
      <el-form :model="form" label-width="100px">
        <el-form-item label="公告标题" required>
          <el-input v-model="form.title" placeholder="请输入公告标题" maxlength="256" show-word-limit />
        </el-form-item>
        <el-form-item label="显示方式" required>
          <el-radio-group v-model="form.display_type">
            <el-radio-button
              v-for="opt in displayTypeOptions"
              :key="opt.value"
              :value="opt.value"
            >
              {{ opt.label }}
            </el-radio-button>
          </el-radio-group>
          <div class="text-xs text-gray-500 mt-1">
            {{ displayTypeOptions.find(o => o.value === form.display_type)?.desc }}
          </div>
        </el-form-item>
        <el-form-item label="公告内容" required>
          <div class="mb-2">
            <el-button type="primary" plain size="small" @click="openAIDraft">
              <el-icon class="mr-1"><Cpu /></el-icon>AI 智能撰写
            </el-button>
          </div>
          <div class="editor-container">
            <Toolbar
              :editor="editorRef"
              :defaultConfig="toolbarConfig"
              :mode="mode"
              class="editor-toolbar"
            />
            <Editor
              v-model="form.content"
              :defaultConfig="editorConfig"
              :mode="mode"
              class="editor-content"
              @onCreated="handleCreated"
            />
          </div>
        </el-form-item>
        <el-form-item label="附件">
          <div class="w-full">
            <el-upload
              :http-request="handleUploadAttachment"
              :show-file-list="false"
              accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.zip,.rar"
            >
              <el-button type="primary" plain :loading="uploadingAttachment" :icon="Paperclip">
                上传附件
              </el-button>
            </el-upload>
            <div class="text-xs text-gray-400 mt-1">支持 PDF、Word、Excel、PPT、ZIP 等格式</div>
            <!-- 附件列表 -->
            <div v-if="form.attachments.length > 0" class="mt-3 space-y-2">
              <div
                v-for="(att, index) in form.attachments"
                :key="index"
                class="flex items-center justify-between bg-gray-50 px-3 py-2 rounded"
              >
                <div class="flex items-center gap-2">
                  <el-icon><Paperclip /></el-icon>
                  <span class="text-sm">{{ att.name }}</span>
                  <span v-if="att.size" class="text-xs text-gray-400">{{ formatFileSize(att.size) }}</span>
                </div>
                <el-button type="danger" size="small" text @click="removeAttachment(index)">删除</el-button>
              </div>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="选项">
          <div class="flex items-center gap-6">
            <el-checkbox v-model="form.is_pinned">置顶显示</el-checkbox>
            <el-checkbox v-model="form.is_published">立即发布</el-checkbox>
            <el-checkbox v-model="form.show_on_login">在登录页展示</el-checkbox>
          </div>
          <div class="text-xs text-gray-500 mt-1">
            勾选“在登录页展示”后，该公告将在登录页面以跑马灯形式展示
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">
          {{ isEditing ? '保存' : '发布' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- AI 撰写助手对话框 -->
    <el-dialog v-model="aiDraftVisible" title="AI 智能撰写助手" width="600px">
      <el-form label-width="80px">
        <el-form-item label="公告要点">
          <el-input v-model="aiDraftKeyPoints" type="textarea" :rows="3" placeholder="输入公告的核心要点，如：提醒学生本周五前提交教案，附上格式要求" />
        </el-form-item>
        <el-form-item label="语气风格">
          <el-radio-group v-model="aiDraftTone">
            <el-radio-button value="formal">正式</el-radio-button>
            <el-radio-button value="friendly">亲切</el-radio-button>
            <el-radio-button value="urgent">紧急</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <div v-if="aiDraftResult" class="mt-4 p-4 bg-gray-50 rounded-lg border">
        <div class="flex items-center gap-2 mb-2">
          <el-icon class="text-cyan-600"><Cpu /></el-icon>
          <span class="font-semibold text-sm text-gray-700">AI 生成结果</span>
        </div>
        <div class="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">{{ aiDraftResult }}</div>
      </div>
      <template #footer>
        <el-button @click="aiDraftVisible = false">取消</el-button>
        <el-button type="primary" @click="generateAIDraft" :loading="aiDraftLoading">
          <el-icon class="mr-1"><Cpu /></el-icon>{{ aiDraftLoading ? 'AI 生成中...' : 'AI 生成' }}
        </el-button>
        <el-button v-if="aiDraftResult" type="success" @click="applyAIDraft">填入编辑器</el-button>
      </template>
    </el-dialog>

    <!-- Preview Dialog -->
    <el-dialog v-model="previewVisible" title="公告预览" width="700px">
      <template v-if="previewNotice">
        <div class="mb-4">
          <el-tag :type="getDisplayTypeTag(previewNotice.display_type)" class="mb-2">
            {{ getDisplayTypeLabel(previewNotice.display_type) }}
          </el-tag>
          <el-tag v-if="previewNotice.is_pinned" type="warning" class="ml-2">置顶</el-tag>
        </div>
        <h3 class="text-lg font-bold mb-3">{{ previewNotice.title }}</h3>
        <div class="notice-content prose max-w-none" v-html="previewNotice.content"></div>
        <!-- 附件列表 -->
        <div v-if="getAttachments(previewNotice).length > 0" class="mt-4 pt-4 border-t">
          <div class="text-sm font-medium mb-2">附件：</div>
          <div class="space-y-2">
            <a
              v-for="(att, index) in getAttachments(previewNotice)"
              :key="index"
              :href="att.url"
              target="_blank"
              class="flex items-center gap-2 text-blue-600 hover:text-blue-800"
            >
              <el-icon><Paperclip /></el-icon>
              <span>{{ att.name }}</span>
            </a>
          </div>
        </div>
        <div class="text-xs text-gray-400 mt-4">
          发布时间: {{ new Date(previewNotice.created_at).toLocaleString() }}
        </div>
      </template>
      <template #footer>
        <el-button @click="previewVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.editor-container {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  width: 100%;
}

.editor-toolbar {
  border-bottom: 1px solid #dcdfe6;
}

.editor-content {
  height: 300px;
  overflow-y: auto;
}

.notice-content :deep(img) {
  max-width: 100%;
  height: auto;
}

.notice-content :deep(p) {
  margin: 0.5em 0;
}

.notice-content :deep(ul),
.notice-content :deep(ol) {
  padding-left: 1.5em;
}
</style>
