<script setup lang="ts">
/**
 * AI 评语生成器组件
 * 根据成绩和分析结果生成评语建议
 */
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { 
  MagicStick, Refresh, Check, Edit, CopyDocument, 
  Star
} from '@element-plus/icons-vue'
import { aiApi } from '@/api'

interface ScoreData {
  lessonPlanScore?: number
  videoScore?: number
  totalScore: number
  analysisResult?: any
}

const props = defineProps<{
  submissionId: number
  scoreData: ScoreData
  studentName?: string
}>()

const emit = defineEmits<{
  (e: 'use-feedback', feedback: string): void
}>()

const loading = ref(false)
const generated = ref(false)
const feedback = ref('')
const editMode = ref(false)
const editedFeedback = ref('')

// 预设评语模板
const templates = [
  { label: '优秀', minScore: 90, text: '{name}同学表现出色！教案结构完整、教学目标明确，视频试讲语言流畅、自信大方。继续保持！' },
  { label: '良好', minScore: 80, text: '{name}同学基本功扎实，教案有层次，试讲有条理。建议进一步优化教学方法，增加师生互动环节。' },
  { label: '中等', minScore: 70, text: '{name}同学完成了本次试讲任务，但仍有提升空间。建议加强教案结构设计，注意语速和板书规范。' },
  { label: '待提升', minScore: 0, text: '{name}同学需要更多练习。建议认真研究教材，完善教案各环节，多进行模拟试讲以提升表现。' }
]

// 根据分数获取模板
const matchedTemplate = computed(() => {
  const score = props.scoreData.totalScore
  return templates.find(t => score >= t.minScore) || templates[templates.length - 1]
})

// 使用模板
const useTemplate = () => {
  const name = props.studentName || '该'
  feedback.value = matchedTemplate.value.text.replace('{name}', name)
  generated.value = true
}

// AI 生成评语
const generateFeedback = async () => {
  loading.value = true
  try {
    const res: any = await aiApi.generateFeedback({
      submission_id: props.submissionId,
      analysis_result: props.scoreData.analysisResult
    })
    
    if (res.success && res.data?.feedback) {
      feedback.value = res.data.feedback
      generated.value = true
    } else {
      // 回退到模板
      useTemplate()
    }
  } catch (error) {
    console.error('生成评语失败:', error)
    // 回退到模板
    useTemplate()
    ElMessage.warning('AI 生成失败，已使用模板评语')
  } finally {
    loading.value = false
  }
}

// 重新生成
const regenerate = () => {
  generated.value = false
  feedback.value = ''
  generateFeedback()
}

// 编辑评语
const startEdit = () => {
  editedFeedback.value = feedback.value
  editMode.value = true
}

const saveEdit = () => {
  feedback.value = editedFeedback.value
  editMode.value = false
}

const cancelEdit = () => {
  editMode.value = false
}

// 使用评语
const useFeedback = () => {
  emit('use-feedback', feedback.value)
  ElMessage.success('评语已应用')
}

// 复制评语
const copyFeedback = async () => {
  try {
    await navigator.clipboard.writeText(feedback.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}
</script>

<template>
  <div class="feedback-generator">
    <!-- 未生成状态 -->
    <div v-if="!generated" class="generate-prompt">
      <div class="prompt-icon">
        <el-icon><MagicStick /></el-icon>
      </div>
      <div class="prompt-content">
        <h4>AI 智能评语助手</h4>
        <p>根据成绩和分析结果，自动生成个性化评语建议</p>
        <div class="prompt-actions">
          <el-button 
            type="primary" 
            :icon="MagicStick" 
            :loading="loading"
            @click="generateFeedback"
          >
            AI 生成评语
          </el-button>
          <el-button @click="useTemplate">使用模板</el-button>
        </div>
      </div>
    </div>
    
    <!-- 已生成状态 -->
    <div v-else class="generated-content">
      <div class="content-header">
        <div class="header-left">
          <el-icon class="text-cyan-600"><Star /></el-icon>
          <span class="font-medium">AI 生成评语</span>
          <el-tag type="success" size="small" effect="plain">
            {{ matchedTemplate.label }}
          </el-tag>
        </div>
        <div class="header-actions">
          <el-button :icon="Refresh" size="small" @click="regenerate">重新生成</el-button>
        </div>
      </div>
      
      <!-- 评语内容 -->
      <div v-if="!editMode" class="feedback-text" @click="startEdit">
        {{ feedback }}
        <el-icon class="edit-hint"><Edit /></el-icon>
      </div>
      
      <!-- 编辑模式 -->
      <div v-else class="feedback-edit">
        <el-input 
          v-model="editedFeedback" 
          type="textarea" 
          :rows="4"
          placeholder="编辑评语内容..."
        />
        <div class="edit-actions">
          <el-button size="small" @click="cancelEdit">取消</el-button>
          <el-button type="primary" size="small" @click="saveEdit">保存</el-button>
        </div>
      </div>
      
      <!-- 操作按钮 -->
      <div class="content-footer">
        <el-button :icon="CopyDocument" @click="copyFeedback">复制</el-button>
        <el-button type="primary" :icon="Check" @click="useFeedback">
          使用此评语
        </el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.feedback-generator {
  background: white;
  border-radius: 12px;
  overflow: hidden;
}

/* 生成提示 */
.generate-prompt {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 24px;
  background: #ecfeff;
  border: 1px solid #cffafe;
}

.prompt-icon {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  background: #0891b2;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 28px;
}

.prompt-content h4 {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 4px;
}

.prompt-content p {
  font-size: 13px;
  color: #64748b;
  margin: 0 0 16px;
}

.prompt-actions {
  display: flex;
  gap: 12px;
}

/* 生成内容 */
.generated-content {
  padding: 20px;
}

.content-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.feedback-text {
  padding: 16px;
  background: #f8fafc;
  border-radius: 10px;
  line-height: 1.7;
  color: #334155;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.feedback-text:hover {
  background: #f1f5f9;
}

.feedback-text .edit-hint {
  position: absolute;
  top: 12px;
  right: 12px;
  color: #94a3b8;
  opacity: 0;
  transition: opacity 0.2s;
}

.feedback-text:hover .edit-hint {
  opacity: 1;
}

.feedback-edit {
  margin-bottom: 16px;
}

.edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}

.content-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
}

@media (max-width: 640px) {
  .generate-prompt {
    flex-direction: column;
    text-align: center;
  }
  
  .prompt-actions {
    flex-direction: column;
    width: 100%;
  }
  
  .content-footer {
    flex-direction: column;
  }
  
  .content-footer .el-button {
    width: 100%;
  }
}
</style>
</script>
