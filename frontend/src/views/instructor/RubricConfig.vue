<script setup lang="ts">
/**
 * 评分规则配置页面
 * 老师可自定义评分维度和权重
 */
import { ref, onMounted, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/request'
import { 
  Setting, Plus, Edit, Delete, Document, VideoCamera,
  Check, Close, Star, Refresh
} from '@element-plus/icons-vue'

const loading = ref(false)
const semesters = ref<any[]>([])
const selectedSemesterId = ref<number | null>(null)

// 规则列表
const rubrics = ref<any[]>([])

// 编辑对话框
const showEditDialog = ref(false)
const editMode = ref<'create' | 'edit'>('create')
const editingRubric = ref<any>({
  name: '',
  description: '',
  semester_id: null,
  lesson_plan_weight: 40,
  video_weight: 60,
  lesson_plan_dimensions: [],
  video_dimensions: [],
  grade_levels: [],
  is_default: false
})

// 默认维度配置
const defaultDimensions = ref<any>({
  lesson_plan_dimensions: [],
  video_dimensions: [],
  grade_levels: []
})

// 获取批次列表
const fetchSemesters = async () => {
  try {
    const res: any = await api.get('/semesters')
    semesters.value = res
    const active = res.find((s: any) => s.status === 'active')
    if (active) {
      selectedSemesterId.value = active.id
    } else if (res.length > 0) {
      selectedSemesterId.value = res[0].id
    }
    if (selectedSemesterId.value) {
      await fetchRubrics()
    }
  } catch (error) {
    ElMessage.error('获取批次失败')
  }
}

// 获取评分规则列表
const fetchRubrics = async () => {
  loading.value = true
  try {
    const res: any = await api.get('/rubrics', {
      params: { semester_id: selectedSemesterId.value, include_global: true }
    })
    if (res.success) {
      rubrics.value = res.data?.items || []
    }
  } catch (error) {
    ElMessage.error('获取规则失败')
  } finally {
    loading.value = false
  }
}

// 获取默认配置
const fetchDefaults = async () => {
  try {
    const res: any = await api.get('/rubrics/defaults')
    if (res.success) {
      defaultDimensions.value = res.data
    }
  } catch (error) {
    // 使用空默认值
  }
}

// 打开创建对话框
const openCreateDialog = () => {
  editMode.value = 'create'
  editingRubric.value = {
    name: '',
    description: '',
    semester_id: selectedSemesterId.value,
    lesson_plan_weight: 40,
    video_weight: 60,
    lesson_plan_dimensions: JSON.parse(JSON.stringify(defaultDimensions.value.lesson_plan_dimensions)),
    video_dimensions: JSON.parse(JSON.stringify(defaultDimensions.value.video_dimensions)),
    grade_levels: JSON.parse(JSON.stringify(defaultDimensions.value.grade_levels)),
    is_default: false
  }
  showEditDialog.value = true
}

// 打开编辑对话框
const openEditDialog = async (rubric: any) => {
  editMode.value = 'edit'
  try {
    const res: any = await api.get(`/rubrics/${rubric.id}`)
    if (res.success) {
      editingRubric.value = { ...res.data }
      showEditDialog.value = true
    }
  } catch (error) {
    ElMessage.error('获取规则详情失败')
  }
}

// 保存规则
const saveRubric = async () => {
  if (!editingRubric.value.name) {
    ElMessage.warning('请输入规则名称')
    return
  }
  
  // 验证权重
  if (Math.abs(editingRubric.value.lesson_plan_weight + editingRubric.value.video_weight - 100) > 0.01) {
    ElMessage.warning('教案权重 + 视频权重必须等于100')
    return
  }
  
  loading.value = true
  try {
    if (editMode.value === 'create') {
      await api.post('/rubrics', editingRubric.value)
      ElMessage.success('规则创建成功')
    } else {
      await api.put(`/rubrics/${editingRubric.value.id}`, editingRubric.value)
      ElMessage.success('规则更新成功')
    }
    showEditDialog.value = false
    fetchRubrics()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    loading.value = false
  }
}

// 删除规则
const deleteRubric = async (rubric: any) => {
  await ElMessageBox.confirm(`确定删除规则「${rubric.name}」？`, '确认删除', {
    type: 'warning'
  })
  
  try {
    await api.delete(`/rubrics/${rubric.id}`)
    ElMessage.success('规则已删除')
    fetchRubrics()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

// 设为默认
const setDefault = async (rubric: any) => {
  try {
    await api.put(`/rubrics/${rubric.id}`, { is_default: true })
    ElMessage.success('已设为默认规则')
    fetchRubrics()
  } catch (error) {
    ElMessage.error('设置失败')
  }
}

// 添加维度
const addDimension = (type: 'lesson_plan' | 'video') => {
  const dimensions = type === 'lesson_plan' 
    ? editingRubric.value.lesson_plan_dimensions 
    : editingRubric.value.video_dimensions
  
  dimensions.push({
    name: '',
    key: `dim_${Date.now()}`,
    weight: 10,
    description: ''
  })
}

// 删除维度
const removeDimension = (type: 'lesson_plan' | 'video', index: number) => {
  const dimensions = type === 'lesson_plan' 
    ? editingRubric.value.lesson_plan_dimensions 
    : editingRubric.value.video_dimensions
  
  dimensions.splice(index, 1)
}

// 计算维度总权重
const lessonPlanDimensionTotal = computed(() => {
  return editingRubric.value.lesson_plan_dimensions.reduce((sum: number, d: any) => sum + d.weight, 0)
})

const videoDimensionTotal = computed(() => {
  return editingRubric.value.video_dimensions.reduce((sum: number, d: any) => sum + d.weight, 0)
})

// 权重同步
watch(() => editingRubric.value.lesson_plan_weight, (val) => {
  editingRubric.value.video_weight = 100 - val
})

watch(selectedSemesterId, () => {
  fetchRubrics()
})

onMounted(async () => {
  await Promise.all([fetchSemesters(), fetchDefaults()])
})
</script>

<template>
  <div v-loading="loading" class="rubric-container">
    <!-- 页面头部 -->
    <div class="page-header">
      <div>
        <h2 class="text-2xl font-bold text-gray-800 flex items-center gap-2">
          <el-icon class="text-cyan-600"><Setting /></el-icon>
          评分规则配置
        </h2>
        <p class="text-gray-500 text-sm mt-1">自定义评分维度和权重</p>
      </div>
      <div class="flex items-center gap-3">
        <el-select
          v-model="selectedSemesterId"
          placeholder="选择批次"
          class="w-48"
          size="large"
        >
          <el-option
            v-for="s in semesters"
            :key="s.id"
            :label="s.name"
            :value="s.id"
          />
        </el-select>
        <el-button type="primary" :icon="Plus" @click="openCreateDialog">
          创建规则
        </el-button>
      </div>
    </div>

    <!-- 规则列表 -->
    <div class="rubric-list">
      <el-empty v-if="rubrics.length === 0" description="暂无评分规则，点击右上角创建" />
      
      <el-card 
        v-for="rubric in rubrics" 
        :key="rubric.id"
        class="rubric-card"
        shadow="hover"
      >
        <div class="rubric-header">
          <div class="flex items-center gap-2">
            <h3 class="text-lg font-bold text-gray-800">{{ rubric.name }}</h3>
            <el-tag v-if="rubric.is_default" type="success" size="small" effect="dark">默认</el-tag>
            <el-tag v-if="!rubric.is_active" type="info" size="small" effect="plain">已禁用</el-tag>
          </div>
          <div class="flex items-center gap-2">
            <el-button text :icon="Star" @click="setDefault(rubric)" v-if="!rubric.is_default">
              设为默认
            </el-button>
            <el-button text :icon="Edit" @click="openEditDialog(rubric)">编辑</el-button>
            <el-button text type="danger" :icon="Delete" @click="deleteRubric(rubric)">删除</el-button>
          </div>
        </div>
        
        <p v-if="rubric.description" class="text-gray-500 text-sm mt-2">{{ rubric.description }}</p>
        
        <div class="rubric-weights">
          <div class="weight-item">
            <el-icon class="text-blue-500"><Document /></el-icon>
            <span>教案权重</span>
            <el-tag type="primary" effect="plain">{{ rubric.lesson_plan_weight }}%</el-tag>
          </div>
          <div class="weight-item">
            <el-icon class="text-orange-500"><VideoCamera /></el-icon>
            <span>视频权重</span>
            <el-tag type="warning" effect="plain">{{ rubric.video_weight }}%</el-tag>
          </div>
        </div>
        
        <div class="text-xs text-gray-400 mt-3">
          创建于 {{ rubric.created_at ? new Date(rubric.created_at).toLocaleDateString() : '-' }}
        </div>
      </el-card>
    </div>

    <!-- 编辑对话框 -->
    <el-dialog
      v-model="showEditDialog"
      :title="editMode === 'create' ? '创建评分规则' : '编辑评分规则'"
      width="800px"
      class="rubric-edit-dialog"
    >
      <el-form label-width="100px">
        <el-form-item label="规则名称" required>
          <el-input v-model="editingRubric.name" placeholder="如：2024年春季试讲评分规则" />
        </el-form-item>
        
        <el-form-item label="规则描述">
          <el-input v-model="editingRubric.description" type="textarea" :rows="2" placeholder="可选的规则说明" />
        </el-form-item>
        
        <el-form-item label="权重配置">
          <div class="weight-config">
            <div class="weight-slider">
              <span class="text-blue-600 font-medium">教案 {{ editingRubric.lesson_plan_weight }}%</span>
              <el-slider 
                v-model="editingRubric.lesson_plan_weight" 
                :min="0" 
                :max="100"
                :show-tooltip="false"
                class="flex-1 mx-4"
              />
              <span class="text-orange-600 font-medium">视频 {{ editingRubric.video_weight }}%</span>
            </div>
          </div>
        </el-form-item>
        
        <el-divider content-position="left">
          <div class="flex items-center gap-2">
            <el-icon class="text-blue-500"><Document /></el-icon>
            <span>教案评分维度</span>
            <el-tag size="small" :type="lessonPlanDimensionTotal === 100 ? 'success' : 'danger'">
              总权重: {{ lessonPlanDimensionTotal }}%
            </el-tag>
          </div>
        </el-divider>
        
        <div class="dimensions-list">
          <div 
            v-for="(dim, index) in editingRubric.lesson_plan_dimensions" 
            :key="dim.key"
            class="dimension-item"
          >
            <el-input v-model="dim.name" placeholder="维度名称" class="w-32" />
            <el-input-number v-model="dim.weight" :min="0" :max="100" class="w-24" />
            <span class="text-gray-400">%</span>
            <el-input v-model="dim.description" placeholder="维度描述" class="flex-1" />
            <el-button text type="danger" :icon="Delete" @click="removeDimension('lesson_plan', index)" />
          </div>
          <el-button text :icon="Plus" @click="addDimension('lesson_plan')">添加维度</el-button>
        </div>
        
        <el-divider content-position="left">
          <div class="flex items-center gap-2">
            <el-icon class="text-orange-500"><VideoCamera /></el-icon>
            <span>视频评分维度</span>
            <el-tag size="small" :type="videoDimensionTotal === 100 ? 'success' : 'danger'">
              总权重: {{ videoDimensionTotal }}%
            </el-tag>
          </div>
        </el-divider>
        
        <div class="dimensions-list">
          <div 
            v-for="(dim, index) in editingRubric.video_dimensions" 
            :key="dim.key"
            class="dimension-item"
          >
            <el-input v-model="dim.name" placeholder="维度名称" class="w-32" />
            <el-input-number v-model="dim.weight" :min="0" :max="100" class="w-24" />
            <span class="text-gray-400">%</span>
            <el-input v-model="dim.description" placeholder="维度描述" class="flex-1" />
            <el-button text type="danger" :icon="Delete" @click="removeDimension('video', index)" />
          </div>
          <el-button text :icon="Plus" @click="addDimension('video')">添加维度</el-button>
        </div>
        
        <el-form-item label="设为默认" class="mt-4">
          <el-switch v-model="editingRubric.is_default" />
          <span class="text-gray-400 text-sm ml-2">默认规则将在批改时自动应用</span>
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="saveRubric" :loading="loading">
          {{ editMode === 'create' ? '创建' : '保存' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.rubric-container {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

.rubric-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 1rem;
}

.rubric-card {
  border-radius: 0.75rem;
  transition: transform 0.2s;
}

.rubric-card:hover {
  transform: translateY(-2px);
}

.rubric-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.rubric-weights {
  display: flex;
  gap: 1.5rem;
  margin-top: 1rem;
  padding: 0.75rem;
  background: #f9fafb;
  border-radius: 0.5rem;
}

.weight-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: #374151;
}

.weight-config {
  width: 100%;
}

.weight-slider {
  display: flex;
  align-items: center;
  width: 100%;
}

.dimensions-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1rem;
  background: #fafafa;
  border-radius: 0.5rem;
}

.dimension-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

@media (max-width: 640px) {
  .rubric-list {
    grid-template-columns: 1fr;
  }
  
  .dimension-item {
    flex-wrap: wrap;
  }
}
</style>
