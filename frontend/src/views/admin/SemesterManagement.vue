<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, Cpu } from '@element-plus/icons-vue'
import api from '@/utils/request'

interface Semester {
  id: number
  name: string
  status: string
  start_date: string
  end_date: string
  description: string
  created_at: string
}

const semesters = ref<Semester[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)

const form = reactive({
  id: 0,
  name: '',
  start_date: '',
  end_date: '',
  description: ''
})

const formRef = ref()

const fetchSemesters = async () => {
  loading.value = true
  try {
    const res: any = await api.get('/semesters')
    semesters.value = res
  } finally {
    loading.value = false
  }
}

const openCreateDialog = () => {
  isEdit.value = false
  Object.assign(form, { id: 0, name: '', start_date: '', end_date: '', description: '' })
  dialogVisible.value = true
}

const openEditDialog = (row: Semester) => {
  isEdit.value = true
  Object.assign(form, row)
  dialogVisible.value = true
}

const handleSubmit = async () => {
  try {
    if (isEdit.value) {
      await api.put(`/semesters/${form.id}`, form)
      ElMessage.success('更新成功')
    } else {
      await api.post('/semesters', form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchSemesters()
  } catch (error) {
    // handled by interceptor
  }
}

const handleStart = async (row: Semester) => {
  try {
    await api.post(`/semesters/${row.id}/start`)
    ElMessage.success('批次已开启')
    fetchSemesters()
  } catch (error) {}
}

const handleEnd = async (row: Semester) => {
  await ElMessageBox.confirm('确定结束该批次吗？结束后无法重新开启。', '提示')
  try {
    await api.post(`/semesters/${row.id}/end`)
    ElMessage.success('批次已结束')
    fetchSemesters()
  } catch (error) {}
}

const handleDelete = async (row: Semester) => {
  await ElMessageBox.confirm('确定删除该批次吗？', '警告', { type: 'warning' })
  try {
    await api.delete(`/semesters/${row.id}`)
    ElMessage.success('删除成功')
    fetchSemesters()
  } catch (error) {}
}

const getStatusTag = (status: string) => {
  switch (status) {
    case 'draft': return { type: 'info', text: '草稿' }
    case 'active': return { type: 'success', text: '进行中' }
    case 'completed': return { type: 'warning', text: '已结束' }
    default: return { type: 'info', text: status }
  }
}

// AI 批次总结
const aiSummaryVisible = ref(false)
const aiSummaryLoading = ref(false)
const aiSummaryData = ref<any>(null)
const aiSummaryText = ref('')
const aiSummaryDisplayed = ref('')
let summaryTimer: ReturnType<typeof setInterval> | null = null

const openAISummary = async (row: Semester) => {
  aiSummaryVisible.value = true
  aiSummaryLoading.value = true
  aiSummaryData.value = null
  aiSummaryText.value = ''
  aiSummaryDisplayed.value = ''
  try {
    const res: any = await api.get(`/admin/semester-summary/${row.id}`)
    if (res.success && res.data) {
      aiSummaryData.value = res.data.stats
      if (res.data.ai_summary) {
        aiSummaryText.value = res.data.ai_summary
        let i = 0
        if (summaryTimer) clearInterval(summaryTimer)
        summaryTimer = setInterval(() => {
          if (i < res.data.ai_summary.length) { aiSummaryDisplayed.value += res.data.ai_summary[i]; i++ }
          else { if (summaryTimer) clearInterval(summaryTimer) }
        }, 25)
      }
    }
  } catch {
    ElMessage.error('AI 总结生成失败')
  } finally {
    aiSummaryLoading.value = false
  }
}

onMounted(fetchSemesters)
</script>

<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-2xl font-bold">批次管理</h2>
      <el-button type="primary" :icon="Plus" @click="openCreateDialog">新建批次</el-button>
    </div>

    <el-card>
      <el-table :data="semesters" v-loading="loading" stripe>
        <el-table-column prop="name" label="批次名称" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusTag(row.status).type as any">
              {{ getStatusTag(row.status).text }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="start_date" label="开始日期" width="120" />
        <el-table-column prop="end_date" label="结束日期" width="120" />
        <el-table-column prop="description" label="描述" show-overflow-tooltip />
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'draft'" size="small" type="success" @click="handleStart(row)">开启</el-button>
            <el-button v-if="row.status === 'active'" size="small" type="warning" @click="handleEnd(row)">结束</el-button>
            <el-button size="small" :icon="Edit" @click="openEditDialog(row)">编辑</el-button>
            <el-button v-if="row.status === 'draft'" size="small" type="danger" :icon="Delete" @click="handleDelete(row)">删除</el-button>
            <el-button v-if="row.status === 'completed' || row.status === 'active'" size="small" type="primary" plain @click="openAISummary(row)">
              <el-icon class="mr-0.5"><Cpu /></el-icon>AI总结
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Dialog -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑批次' : '新建批次'" width="500px">
      <el-form ref="formRef" :model="form" label-width="80px">
        <el-form-item label="批次名称" prop="name" required>
          <el-input v-model="form.name" placeholder="如：2025春季试讲" />
        </el-form-item>
        <el-form-item label="开始日期" prop="start_date">
          <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="结束日期" prop="end_date">
          <el-date-picker v-model="form.end_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- AI 批次总结对话框 -->
    <el-dialog v-model="aiSummaryVisible" title="AI 批次总结报告" width="650px">
      <div v-loading="aiSummaryLoading">
        <!-- 统计数据 -->
        <div v-if="aiSummaryData" class="mb-4">
          <el-descriptions :column="3" size="small" border>
            <el-descriptions-item label="批次名称">{{ aiSummaryData.semester_name }}</el-descriptions-item>
            <el-descriptions-item label="状态">{{ aiSummaryData.status }}</el-descriptions-item>
            <el-descriptions-item label="学生数">{{ aiSummaryData.total_students }}</el-descriptions-item>
            <el-descriptions-item label="导师数">{{ aiSummaryData.total_instructors }}</el-descriptions-item>
            <el-descriptions-item label="任务数">{{ aiSummaryData.total_tasks }}</el-descriptions-item>
            <el-descriptions-item label="提交数">{{ aiSummaryData.total_submissions }}</el-descriptions-item>
            <el-descriptions-item label="通过数">{{ aiSummaryData.approved }}</el-descriptions-item>
            <el-descriptions-item label="平均分">{{ aiSummaryData.avg_score }}</el-descriptions-item>
            <el-descriptions-item label="通过率">{{ aiSummaryData.pass_rate }}%</el-descriptions-item>
          </el-descriptions>
        </div>

        <!-- AI 总结 -->
        <el-card shadow="never" style="background: #f0f9ff; border-color: #bae6fd;">
          <div class="flex items-start gap-3">
            <div class="w-8 h-8 rounded-lg bg-cyan-100 flex items-center justify-center text-cyan-600 flex-shrink-0">
              <el-icon :size="16"><Cpu /></el-icon>
            </div>
            <div class="flex-1">
              <div class="flex items-center gap-2 mb-2">
                <span class="font-semibold text-sm text-gray-700">AI 智能总结</span>
                <span class="inline-block w-1.5 h-1.5 rounded-full bg-cyan-500" :class="{ 'animate-pulse': aiSummaryLoading }"></span>
              </div>
              <div v-if="aiSummaryLoading && !aiSummaryDisplayed" class="text-sm text-gray-400">AI 正在生成批次总结报告...</div>
              <div v-else-if="aiSummaryDisplayed" class="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">
                {{ aiSummaryDisplayed }}<span v-if="aiSummaryLoading" class="text-cyan-500 font-bold animate-pulse">|</span>
              </div>
              <div v-else class="text-sm text-gray-400">AI 分析功能暂不可用</div>
            </div>
          </div>
        </el-card>
      </div>
      <template #footer>
        <el-button @click="aiSummaryVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>
