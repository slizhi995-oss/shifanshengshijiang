<script setup lang="ts">
/**
 * 批量评分组件
 * 老师可批量给多个提交打分
 */
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/request'
import { 
  Edit, Check, Close, Document, VideoCamera,
  Select, MagicStick
} from '@element-plus/icons-vue'

const props = defineProps<{
  visible: boolean
  submissions: any[]
}>()

const emit = defineEmits(['update:visible', 'success'])

const loading = ref(false)
const selectedSubmissions = ref<any[]>([])
const batchScore = ref(0)
const batchFeedback = ref('')
const useAIScore = ref(false)

// 可批量评分的提交（待批改或已评分）
const eligibleSubmissions = computed(() => {
  return props.submissions.filter(s => 
    s.status === 'pending' || s.status === 'graded'
  )
})

// 选择全部
const selectAll = () => {
  selectedSubmissions.value = [...eligibleSubmissions.value]
}

// 取消全部
const deselectAll = () => {
  selectedSubmissions.value = []
}

// 切换选择
const toggleSelection = (submission: any) => {
  const index = selectedSubmissions.value.findIndex(s => s.id === submission.id)
  if (index >= 0) {
    selectedSubmissions.value.splice(index, 1)
  } else {
    selectedSubmissions.value.push(submission)
  }
}

// 是否选中
const isSelected = (submission: any) => {
  return selectedSubmissions.value.some(s => s.id === submission.id)
}

// 批量评分
const handleBatchGrade = async () => {
  if (selectedSubmissions.value.length === 0) {
    ElMessage.warning('请选择需要评分的提交')
    return
  }
  
  if (batchScore.value <= 0) {
    ElMessage.warning('请输入分数')
    return
  }
  
  await ElMessageBox.confirm(
    `确定要给 ${selectedSubmissions.value.length} 个提交统一打 ${batchScore.value} 分吗？`,
    '确认批量评分',
    { type: 'warning' }
  )
  
  loading.value = true
  let successCount = 0
  let failCount = 0
  
  for (const submission of selectedSubmissions.value) {
    try {
      await api.post(`/submissions/${submission.id}/grade`, {
        total_score: batchScore.value,
        feedback: batchFeedback.value || '批量评分'
      })
      successCount++
    } catch (error) {
      failCount++
    }
  }
  
  loading.value = false
  
  if (successCount > 0) {
    ElMessage.success(`成功评分 ${successCount} 个提交${failCount > 0 ? `，失败 ${failCount} 个` : ''}`)
    emit('success')
    close()
  } else {
    ElMessage.error('评分失败')
  }
}

// 批量通过
const handleBatchApprove = async () => {
  if (selectedSubmissions.value.length === 0) {
    ElMessage.warning('请选择需要通过的提交')
    return
  }
  
  // 检查是否都有分数
  const withoutScore = selectedSubmissions.value.filter(s => !s.total_score && batchScore.value <= 0)
  if (withoutScore.length > 0 && batchScore.value <= 0) {
    ElMessage.warning('部分提交没有分数，请先设置批量分数')
    return
  }
  
  await ElMessageBox.confirm(
    `确定要通过 ${selectedSubmissions.value.length} 个提交吗？`,
    '确认批量通过',
    { type: 'warning' }
  )
  
  loading.value = true
  let successCount = 0
  let failCount = 0
  
  for (const submission of selectedSubmissions.value) {
    try {
      const data = batchScore.value > 0 ? {
        total_score: batchScore.value,
        feedback: batchFeedback.value || '批量通过'
      } : undefined
      
      await api.post(`/submissions/${submission.id}/approve`, data)
      successCount++
    } catch (error) {
      failCount++
    }
  }
  
  loading.value = false
  
  if (successCount > 0) {
    ElMessage.success(`成功通过 ${successCount} 个提交${failCount > 0 ? `，失败 ${failCount} 个` : ''}`)
    emit('success')
    close()
  } else {
    ElMessage.error('操作失败')
  }
}

// 关闭
const close = () => {
  selectedSubmissions.value = []
  batchScore.value = 0
  batchFeedback.value = ''
  emit('update:visible', false)
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="批量评分"
    width="800px"
    class="batch-grade-dialog"
    @close="close"
  >
    <!-- 操作栏 -->
    <div class="action-bar">
      <div class="selection-info">
        <el-button size="small" @click="selectAll" :icon="Select">全选</el-button>
        <el-button size="small" @click="deselectAll">取消</el-button>
        <span class="ml-3 text-gray-500 text-sm">
          已选 {{ selectedSubmissions.length }} / {{ eligibleSubmissions.length }} 个
        </span>
      </div>
    </div>

    <!-- 提交列表 -->
    <div class="submission-list" v-loading="loading">
      <div 
        v-for="submission in eligibleSubmissions" 
        :key="submission.id"
        class="submission-item"
        :class="{ 'selected': isSelected(submission) }"
        @click="toggleSelection(submission)"
      >
        <el-checkbox :model-value="isSelected(submission)" @click.stop @change="toggleSelection(submission)" />
        
        <div class="student-info">
          <span class="student-name">{{ submission.student?.name }}</span>
          <span class="student-code">{{ submission.student?.user_code }}</span>
        </div>
        
        <div class="task-info">
          <el-icon class="text-red-500" v-if="submission.lesson_plan_path"><Document /></el-icon>
          <el-icon class="text-blue-500" v-if="submission.video_path"><VideoCamera /></el-icon>
          <span class="task-title">{{ submission.task?.title }}</span>
        </div>
        
        <div class="score-info">
          <el-tag v-if="submission.total_score" type="primary" effect="plain">
            {{ submission.total_score }}分
          </el-tag>
          <el-tag v-else type="info" effect="plain">未评分</el-tag>
        </div>
        
        <el-tag :type="submission.status === 'pending' ? 'warning' : 'primary'" size="small">
          {{ submission.status === 'pending' ? '待批改' : '已评分' }}
        </el-tag>
      </div>
    </div>

    <!-- 批量设置 -->
    <div class="batch-settings">
      <el-form label-width="80px">
        <el-form-item label="统一分数">
          <el-input-number v-model="batchScore" :min="0" :max="100" :step="5" />
          <span class="ml-2 text-gray-400 text-sm">留空则使用各提交现有分数</span>
        </el-form-item>
        <el-form-item label="统一评语">
          <el-input 
            v-model="batchFeedback" 
            type="textarea" 
            :rows="2" 
            placeholder="可选，留空则使用默认评语"
          />
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button 
        type="warning" 
        :icon="Edit" 
        :loading="loading"
        :disabled="selectedSubmissions.length === 0"
        @click="handleBatchGrade"
      >
        批量评分
      </el-button>
      <el-button 
        type="success" 
        :icon="Check" 
        :loading="loading"
        :disabled="selectedSubmissions.length === 0"
        @click="handleBatchApprove"
      >
        批量通过
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding: 0.75rem;
  background: #f9fafb;
  border-radius: 0.5rem;
}

.submission-list {
  max-height: 300px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.submission-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: all 0.2s;
}

.submission-item:hover {
  border-color: #c7d2fe;
  background: #f0fdfa;
}

.submission-item.selected {
  border-color: #0891b2;
  background: #ecfeff;
}

.student-info {
  display: flex;
  flex-direction: column;
  min-width: 100px;
}

.student-name {
  font-weight: 600;
  color: #374151;
  font-size: 0.875rem;
}

.student-code {
  font-size: 0.75rem;
  color: #9ca3af;
}

.task-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
}

.task-title {
  font-size: 0.875rem;
  color: #6b7280;
}

.score-info {
  min-width: 60px;
  text-align: center;
}

.batch-settings {
  padding: 1rem;
  background: #f9fafb;
  border-radius: 0.5rem;
}
</style>
