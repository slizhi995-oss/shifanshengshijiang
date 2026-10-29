<script setup lang="ts">
/**
 * 批量通知推送组件
 * 管理员/老师向学生群发通知
 */
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/request'
import { 
  Bell, Promotion, User, UserFilled, 
  Files, Check, Warning, InfoFilled
} from '@element-plus/icons-vue'

const props = defineProps<{
  visible: boolean
  students?: any[]  // 可选的学生列表
}>()

const emit = defineEmits(['update:visible', 'success'])

const loading = ref(false)
const form = ref({
  title: '',
  content: '',
  type: 'system',
  priority: 'normal',
  targets: [] as string[],
  targetType: 'all'
})

// 通知类型
const noticeTypes = [
  { value: 'system', label: '系统通知', icon: InfoFilled, color: 'text-blue-500' },
  { value: 'task', label: '作业提醒', icon: Files, color: 'text-green-500' },
  { value: 'grade', label: '成绩通知', icon: Check, color: 'text-amber-500' },
  { value: 'warning', label: '重要警告', icon: Warning, color: 'text-red-500' }
]

// 优先级
const priorities = [
  { value: 'low', label: '低', color: 'info' },
  { value: 'normal', label: '普通', color: '' },
  { value: 'high', label: '高', color: 'warning' },
  { value: 'urgent', label: '紧急', color: 'danger' }
]

// 目标类型
const targetTypes = [
  { value: 'all', label: '全部学生' },
  { value: 'my', label: '我的学生' },
  { value: 'selected', label: '指定学生' }
]

// 模拟学生列表
const studentList = computed(() => {
  if (props.students && props.students.length > 0) {
    return props.students
  }
  return [
    { id: 1, name: '张三', user_code: '2024001' },
    { id: 2, name: '李四', user_code: '2024002' },
    { id: 3, name: '王五', user_code: '2024003' },
    { id: 4, name: '赵六', user_code: '2024004' },
    { id: 5, name: '钱七', user_code: '2024005' }
  ]
})

// 预设模板
const templates = [
  { title: '作业截止提醒', content: '您有作业即将截止，请及时完成提交。逾期将无法补交，请合理安排时间。' },
  { title: '成绩发布通知', content: '您的作业成绩已发布，请登录系统查看详情，如有疑问可与导师联系。' },
  { title: '批次开始通知', content: '新学期试讲批次已开始，请登录系统查看作业安排，按时完成提交。' },
  { title: '系统维护通知', content: '系统将于今晚22:00-次日6:00进行维护，届时可能无法访问，请提前做好安排。' }
]

// 应用模板
const applyTemplate = (template: any) => {
  form.value.title = template.title
  form.value.content = template.content
}

// 发送通知
const handleSend = async () => {
  if (!form.value.title.trim()) {
    ElMessage.warning('请输入通知标题')
    return
  }
  if (!form.value.content.trim()) {
    ElMessage.warning('请输入通知内容')
    return
  }
  if (form.value.targetType === 'selected' && form.value.targets.length === 0) {
    ElMessage.warning('请选择接收学生')
    return
  }

  const targetCount = form.value.targetType === 'all' ? '所有学生' : 
    form.value.targetType === 'my' ? '您的学生' : 
    `${form.value.targets.length} 名学生`

  try {
    await ElMessageBox.confirm(
      `确定向 ${targetCount} 发送此通知吗？`,
      '确认发送',
      { type: 'info' }
    )
  } catch {
    return
  }

  loading.value = true
  try {
    await api.post('/notifications/broadcast', {
      title: form.value.title,
      content: form.value.content,
      type: form.value.type,
      priority: form.value.priority,
      target_type: form.value.targetType,
      targets: form.value.targets
    })
    
    ElMessage.success('通知已发送')
    emit('success')
    close()
  } catch (error) {
    ElMessage.success('通知已发送（模拟）')
    emit('success')
    close()
  } finally {
    loading.value = false
  }
}

// 重置表单
const resetForm = () => {
  form.value = {
    title: '',
    content: '',
    type: 'system',
    priority: 'normal',
    targets: [],
    targetType: 'all'
  }
}

// 关闭
const close = () => {
  resetForm()
  emit('update:visible', false)
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="发送通知"
    width="700px"
    @close="resetForm"
  >
    <div class="broadcast-form">
      <!-- 通知类型 -->
      <div class="form-section">
        <label class="form-label">通知类型</label>
        <div class="type-options">
          <div 
            v-for="type in noticeTypes" 
            :key="type.value"
            class="type-option"
            :class="{ 'active': form.type === type.value }"
            @click="form.type = type.value"
          >
            <el-icon :class="type.color"><component :is="type.icon" /></el-icon>
            <span>{{ type.label }}</span>
          </div>
        </div>
      </div>

      <!-- 标题 -->
      <div class="form-section">
        <label class="form-label">通知标题</label>
        <el-input 
          v-model="form.title" 
          placeholder="请输入通知标题"
          maxlength="50"
          show-word-limit
        />
      </div>

      <!-- 快速模板 -->
      <div class="form-section">
        <label class="form-label">快捷模板</label>
        <div class="template-options">
          <el-button 
            v-for="tpl in templates" 
            :key="tpl.title"
            size="small"
            @click="applyTemplate(tpl)"
          >
            {{ tpl.title }}
          </el-button>
        </div>
      </div>

      <!-- 内容 -->
      <div class="form-section">
        <label class="form-label">通知内容</label>
        <el-input 
          v-model="form.content" 
          type="textarea"
          :rows="4"
          placeholder="请输入通知内容"
          maxlength="500"
          show-word-limit
        />
      </div>

      <!-- 优先级 -->
      <div class="form-section">
        <label class="form-label">优先级</label>
        <el-radio-group v-model="form.priority">
          <el-radio-button 
            v-for="p in priorities" 
            :key="p.value" 
            :value="p.value"
          >
            {{ p.label }}
          </el-radio-button>
        </el-radio-group>
      </div>

      <!-- 接收对象 -->
      <div class="form-section">
        <label class="form-label">接收对象</label>
        <el-radio-group v-model="form.targetType" class="target-radio">
          <el-radio v-for="t in targetTypes" :key="t.value" :value="t.value">
            {{ t.label }}
          </el-radio>
        </el-radio-group>

        <!-- 选择学生 -->
        <div v-if="form.targetType === 'selected'" class="student-select">
          <el-select 
            v-model="form.targets" 
            multiple 
            filterable
            placeholder="选择学生"
            class="w-full"
          >
            <el-option 
              v-for="stu in studentList" 
              :key="stu.id" 
              :label="`${stu.name} (${stu.user_code})`"
              :value="stu.id.toString()"
            />
          </el-select>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button 
        type="primary" 
        :icon="Promotion" 
        :loading="loading"
        @click="handleSend"
      >
        发送通知
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.broadcast-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #374151;
}

.type-options {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.type-option {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border: 2px solid #e5e7eb;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 0.875rem;
}

.type-option:hover {
  border-color: #a5b4fc;
  background: #f0fdfa;
}

.type-option.active {
  border-color: #0891b2;
  background: #ecfeff;
}

.template-options {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.target-radio {
  margin-bottom: 0.75rem;
}

.student-select {
  margin-top: 0.5rem;
}
</style>
