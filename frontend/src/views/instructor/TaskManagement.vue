<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, Promotion, Cpu, InfoFilled } from '@element-plus/icons-vue'
import api from '@/utils/request'

const tasks = ref<any[]>([])
const semesters = ref<any[]>([])
const selectedSemesterId = ref<number | null>(null)
const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)

const form = reactive({
  id: 0,
  semester_id: 0,
  title: '',
  content: '',
  deadline: '',
  require_lesson_plan: true,
  require_video: true
})

const fetchSemesters = async () => {
  try {
    const res: any = await api.get('/semesters')
    semesters.value = res
    
    // 默认选择第一个活跃批次
    const activeSemester = res.find((s: any) => s.status === 'active')
    if (activeSemester) {
      selectedSemesterId.value = activeSemester.id
    } else if (res.length > 0) {
      selectedSemesterId.value = res[0].id
    }
    
    if (selectedSemesterId.value) {
      await fetchTasks()
    }
  } catch (error) {}
}

const fetchTasks = async () => {
  if (!selectedSemesterId.value) return
  
  loading.value = true
  try {
    const res: any = await api.get('/tasks', { 
      params: { semester_id: selectedSemesterId.value } 
    })
    tasks.value = res
  } finally {
    loading.value = false
  }
}

const handleSemesterChange = () => {
  fetchTasks()
}

const openCreateDialog = () => {
  if (!selectedSemesterId.value) {
    ElMessage.warning('请先选择批次')
    return
  }
  
  isEdit.value = false
  Object.assign(form, {
    id: 0,
    semester_id: selectedSemesterId.value,
    title: '',
    content: '',
    deadline: '',
    require_lesson_plan: true,
    require_video: true
  })
  dialogVisible.value = true
}

const openEditDialog = (row: any) => {
  isEdit.value = true
  Object.assign(form, row)
  dialogVisible.value = true
}

const handleSubmit = async () => {
  try {
    if (isEdit.value) {
      await api.put(`/tasks/${form.id}`, form)
      ElMessage.success('更新成功')
    } else {
      await api.post('/tasks', form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchTasks()
  } catch (error) {}
}

const handlePublish = async (row: any) => {
  try {
    await api.post(`/tasks/${row.id}/publish`)
    ElMessage.success('作业已发布')
    fetchTasks()
  } catch (error) {}
}

const handleDelete = async (row: any) => {
  await ElMessageBox.confirm('确定删除该作业吗？', '警告', { type: 'warning' })
  try {
    await api.delete(`/tasks/${row.id}`)
    ElMessage.success('删除成功')
    fetchTasks()
  } catch (error) {}
}

onMounted(fetchSemesters)
</script>

<template>
  <div v-loading="loading">
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-2xl font-bold">作业管理</h2>
      <div class="flex items-center gap-3">
        <el-select
          v-model="selectedSemesterId"
          placeholder="选择批次"
          @change="handleSemesterChange"
          style="width: 200px"
        >
          <el-option
            v-for="s in semesters"
            :key="s.id"
            :label="s.name"
            :value="s.id"
          >
            <span>{{ s.name }}</span>
            <el-tag v-if="s.status === 'active'" size="small" type="success" class="ml-2">进行中</el-tag>
          </el-option>
        </el-select>
        <el-button type="primary" :icon="Plus" @click="openCreateDialog" :disabled="!selectedSemesterId">
          新建作业
        </el-button>
      </div>
    </div>

    <el-alert v-if="semesters.length === 0" type="info" :closable="false" class="mb-6">
      当前没有试讲批次，请联系管理员创建批次
    </el-alert>

    <el-card v-else-if="selectedSemesterId">
      <el-empty v-if="tasks.length === 0" description="暂无作业，点击上方按钮新建" />
      <el-table v-else :data="tasks" stripe>
        <el-table-column prop="title" label="作业标题" />
        <el-table-column label="要求" width="150">
          <template #default="{ row }">
            <el-tag v-if="row.require_lesson_plan" size="small" class="mr-1">教案</el-tag>
            <el-tag v-if="row.require_video" size="small" type="warning">视频</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="deadline" label="截止日期" width="120" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_published ? 'success' : 'info'">
              {{ row.is_published ? '已发布' : '草稿' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="AI 分析" width="130">
          <template #default="{ row }">
            <el-tag 
              v-if="row.submission_count > 0"
              type="primary"
              size="small"
              effect="plain"
              round
              class="ai-count-tag"
            >
              <el-icon class="mr-0.5" :size="12"><Cpu /></el-icon>
              AI 已分析 {{ row.submission_count }} 份
            </el-tag>
            <span v-else class="text-gray-400 text-xs">暂无提交</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button v-if="!row.is_published" size="small" type="success" :icon="Promotion" @click="handlePublish(row)">
              发布
            </el-button>
            <el-button size="small" :icon="Edit" @click="openEditDialog(row)">编辑</el-button>
            <el-button v-if="!row.is_published" size="small" type="danger" :icon="Delete" @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Dialog -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑作业' : '新建作业'" width="600px">
      <!-- AI 功能提示 -->
      <div class="ai-dialog-tip">
        <div class="ai-tip-icon">
          <el-icon :size="18"><Cpu /></el-icon>
        </div>
        <div class="ai-tip-content">
          <div class="ai-tip-title">AI 智能辅助</div>
          <div class="ai-tip-text">发布后学生可使用 AI 备课助手生成教案草稿，AI 将自动进行七维分析评估</div>
        </div>
      </div>
      
      <el-form :model="form" label-width="100px">
        <el-form-item label="作业标题" required>
          <el-input v-model="form.title" placeholder="如：第一次试讲作业" />
        </el-form-item>
        <el-form-item label="作业内容">
          <div class="content-input-wrapper">
            <el-input
              v-model="form.content"
              type="textarea"
              :rows="5"
              placeholder="详细描述作业要求..."
            />
            <el-tooltip content="学生提交后，AI 将自动分析教案质量并生成七维评估报告" placement="right">
              <div class="ai-input-hint">
                <el-icon :size="14"><Cpu /></el-icon>
              </div>
            </el-tooltip>
          </div>
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker v-model="form.deadline" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="提交要求">
          <el-checkbox v-model="form.require_lesson_plan">需要提交教案 (PDF)</el-checkbox>
          <el-checkbox v-model="form.require_video">需要提交视频</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
/* AI 对话框提示 */
.ai-dialog-tip {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.875rem 1rem;
  background: #ecfeff;
  border-radius: 0.75rem;
  border: 1px solid rgba(8, 145, 178, 0.15);
  margin-bottom: 1.25rem;
}

.ai-tip-icon {
  width: 32px;
  height: 32px;
  min-width: 32px;
  background: #0891b2;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.ai-tip-content {
  flex: 1;
}

.ai-tip-title {
  font-size: 0.8125rem;
  font-weight: 700;
  color: #0e7490;
  margin-bottom: 0.125rem;
}

.ai-tip-text {
  font-size: 0.75rem;
  color: #0891b2;
  line-height: 1.5;
}

/* 内容输入框 AI 提示 */
.content-input-wrapper {
  position: relative;
  width: 100%;
}

.ai-input-hint {
  position: absolute;
  top: 8px;
  right: -32px;
  width: 24px;
  height: 24px;
  background: #0891b2;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  cursor: help;
  transition: transform 0.2s;
}

.ai-input-hint:hover {
  transform: scale(1.15);
}

/* AI 分析计数标签 */
.ai-count-tag {
  font-size: 0.6875rem !important;
}
</style>
