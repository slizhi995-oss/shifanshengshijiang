<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/request'

const semesters = ref<any[]>([])
const selectedSemesterId = ref<number | null>(null)
const instructors = ref<any[]>([])
const unassignedStudents = ref<any[]>([])
const assignmentOverview = ref<any[]>([])
const loading = ref(false)
const selectedStudents = ref<number[]>([])
const selectedInstructor = ref<number | null>(null)
const importing = ref(false)
const importInputRef = ref<HTMLInputElement | null>(null)
const autoAssigning = ref(false)

// AI 智能分配
const aiAssignDialogVisible = ref(false)
const aiAssigning = ref(false)
const aiAssignResult = ref<any>(null)

// 生成默认头像URL
const getAvatarUrl = (userCode: string) => {
  const seed = userCode || 'default'
  return `https://api.dicebear.com/7.x/notionists/svg?seed=${seed}&backgroundColor=b6e3f4,c0aede,d1d4f9`
}

// 筛选相关
const filterOptions = ref<{ colleges: string[], majors: string[], classes: string[] }>({
  colleges: [],
  majors: [],
  classes: [],
})
const filterCollege = ref('')
const filterMajor = ref('')
const filterClass = ref('')

// 已分配情况筛选
const assignedFilterCollege = ref('')
const assignedFilterMajor = ref('')
const assignedFilterClass = ref('')
const assignedFilterInstructor = ref<number | null>(null)
const selectedAssignedStudents = ref<number[]>([])

// 一键分配弹窗
const autoAssignDialogVisible = ref(false)
const selectedInstructorIds = ref<number[]>([])  // 选中的老师ID列表
const sameClassGrouping = ref(false)  // 同班级分组选项

// 计算筛选后的学生列表
const filteredStudents = computed(() => {
  return unassignedStudents.value.filter(s => {
    if (filterCollege.value && s.college !== filterCollege.value) return false
    if (filterMajor.value && s.major !== filterMajor.value) return false
    if (filterClass.value && s.class_name !== filterClass.value) return false
    return true
  })
})

// 计算筛选后的已分配情况
const filteredAssignmentOverview = computed(() => {
  let filtered = assignmentOverview.value
  
  // 按指导老师筛选
  if (assignedFilterInstructor.value) {
    filtered = filtered.filter(g => g.instructor.id === assignedFilterInstructor.value)
  }
  
  // 按学生条件筛选
  if (assignedFilterCollege.value || assignedFilterMajor.value || assignedFilterClass.value) {
    filtered = filtered.map(group => ({
      ...group,
      students: group.students.filter((s: any) => {
        if (assignedFilterCollege.value && s.college !== assignedFilterCollege.value) return false
        if (assignedFilterMajor.value && s.major !== assignedFilterMajor.value) return false
        if (assignedFilterClass.value && s.class_name !== assignedFilterClass.value) return false
        return true
      })
    })).filter(g => g.students.length > 0)
  }
  
  return filtered
})

// 计算所有筛选后的已分配学生ID列表
const allFilteredAssignedStudentIds = computed(() => {
  const ids: number[] = []
  filteredAssignmentOverview.value.forEach(group => {
    group.students.forEach((s: any) => ids.push(s.id))
  })
  return ids
})

// Fetch active semesters
const fetchSemesters = async () => {
  const res: any = await api.get('/semesters')
  semesters.value = res.filter((s: any) => s.status === 'active' || s.status === 'draft')
  // 不再自动选择第一个批次，保持为空以便显示 placeholder，
  // 由用户手动选择后再加载分配数据
  if (!semesters.value.find(s => s.id === selectedSemesterId.value)) {
    selectedSemesterId.value = null
  }
}

// Fetch instructors and assignment data
const fetchAssignmentData = async () => {
  if (!selectedSemesterId.value) return
  loading.value = true
  try {
    const [instructorsRes, unassignedRes, overviewRes, optionsRes]: any = await Promise.all([
      api.get('/users/role/instructor'),
      api.get(`/assignments/unassigned/${selectedSemesterId.value}`),
      api.get(`/assignments/overview/${selectedSemesterId.value}`),
      api.get(`/assignments/filter/options/${selectedSemesterId.value}`)
    ])
    instructors.value = instructorsRes
    unassignedStudents.value = unassignedRes
    // 后端返回的是 AssignmentOverview 对象，这里只取其中的 groups 数组用于展示
    assignmentOverview.value = overviewRes.groups || []
    filterOptions.value = optionsRes
    // 重置筛选条件
    filterCollege.value = ''
    filterMajor.value = ''
    filterClass.value = ''
    selectedStudents.value = []
    // 重置已分配筛选条件
    assignedFilterCollege.value = ''
    assignedFilterMajor.value = ''
    assignedFilterClass.value = ''
    assignedFilterInstructor.value = null
    selectedAssignedStudents.value = []
  } finally {
    loading.value = false
  }
}

const handleDownloadTemplate = async () => {
  if (!selectedSemesterId.value) {
    ElMessage.warning('请先选择批次')
    return
  }

  try {
    const response: any = await api.get('/assignments/import/template', {
      responseType: 'blob',
    })

    const blob = new Blob([response])
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', 'assignment_import_template.xlsx')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (error) {
    // 错误由全局拦截器处理
  }
}

const handleImportClick = () => {
  if (!selectedSemesterId.value) {
    ElMessage.warning('请先选择批次')
    return
  }
  if (importInputRef.value) {
    importInputRef.value.click()
  }
}

const handleImportChange = async (e: Event) => {
  const input = e.target as HTMLInputElement
  if (!input.files || !input.files[0]) return

  if (!selectedSemesterId.value) {
    ElMessage.warning('请先选择批次')
    return
  }

  const file = input.files[0]
  const formData = new FormData()
  formData.append('file', file)

  try {
    importing.value = true
    const res: any = await api.post(`/assignments/import?semester_id=${selectedSemesterId.value}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    ElMessage.success(`导入完成：成功 ${res.success_count} 条，失败 ${res.fail_count} 条`)
    fetchAssignmentData()
  } catch (error) {
    // 错误由全局拦截器处理
  } finally {
    importing.value = false
    input.value = ''
  }
}

// Handle batch assignment
const handleBatchAssign = async () => {
  if (!selectedInstructor.value) {
    ElMessage.warning('请选择指导老师')
    return
  }
  if (selectedStudents.value.length === 0) {
    ElMessage.warning('请选择学生')
    return
  }

  try {
    await api.post('/assignments/batch', {
      semester_id: selectedSemesterId.value,
      instructor_id: selectedInstructor.value,
      student_ids: selectedStudents.value
    })
    ElMessage.success(`成功分配 ${selectedStudents.value.length} 名学生`)
    selectedStudents.value = []
    selectedInstructor.value = null
    fetchAssignmentData()
  } catch (error) {}
}

// Handle unassign
const handleUnassign = async (studentId: number) => {
  try {
    await api.delete(`/assignments/${selectedSemesterId.value}/${studentId}`)
    ElMessage.success('已取消分配')
    fetchAssignmentData()
  } catch (error) {
    // Error handled by interceptor
  }
}

// 批量取消分配
const handleBatchUnassign = async () => {
  if (selectedAssignedStudents.value.length === 0) {
    ElMessage.warning('请先选择要取消分配的学生')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `确定要取消 ${selectedAssignedStudents.value.length} 名学生的分配吗？`,
      '批量取消分配',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    await api.delete('/assignments/batch', {
      data: {
        semester_id: selectedSemesterId.value,
        student_ids: selectedAssignedStudents.value
      }
    })
    
    ElMessage.success(`成功取消 ${selectedAssignedStudents.value.length} 名学生的分配`)
    selectedAssignedStudents.value = []
    fetchAssignmentData()
  } catch (error: any) {
    if (error !== 'cancel') {
      // Error handled by interceptor
    }
  }
}

// 全选/取消全选已分配学生
const handleSelectAllAssigned = () => {
  if (selectedAssignedStudents.value.length === allFilteredAssignedStudentIds.value.length && allFilteredAssignedStudentIds.value.length > 0) {
    selectedAssignedStudents.value = []
  } else {
    selectedAssignedStudents.value = [...allFilteredAssignedStudentIds.value]
  }
}

const openAutoAssignDialog = () => {
  if (!selectedSemesterId.value) {
    ElMessage.warning('请先选择批次')
    return
  }
  if (filteredStudents.value.length === 0) {
    ElMessage.warning('没有需要分配的学生')
    return
  }
  // 默认选中所有老师
  selectedInstructorIds.value = instructors.value.map(i => i.id)
  sameClassGrouping.value = false // 重置同班级分组选项
  autoAssignDialogVisible.value = true
}

// 计算每个老师将分配的学生数
const autoAssignPreview = computed(() => {
  const studentCount = filteredStudents.value.length
  const instructorCount = selectedInstructorIds.value.length
  if (instructorCount === 0) return []
  
  // 如果启用同班级分组，按班级统计
  if (sameClassGrouping.value) {
    // 按班级分组学生
    const classGroups: { [key: string]: any[] } = {}
    filteredStudents.value.forEach(student => {
      const className = student.class_name || '未分班'
      if (!classGroups[className]) {
        classGroups[className] = []
      }
      classGroups[className].push(student)
    })
    
    // 将班级按人数排序（大班级优先）
    const sortedClasses = Object.entries(classGroups).sort((a, b) => b[1].length - a[1].length)
    
    const totalStudents = filteredStudents.value.length
    const totalInstructors = selectedInstructorIds.value.length
    
    // 第一步：按比例计算每个班级应该分配多少老师
    const classInstructorAllocation: { [key: string]: number } = {}
    let allocatedInstructors = 0
    
    sortedClasses.forEach(([className, students], idx) => {
      const classSize = students.length
      let instructorsForClass: number
      
      if (idx === sortedClasses.length - 1) {
        // 最后一个班级分配剩余的所有老师
        instructorsForClass = totalInstructors - allocatedInstructors
      } else {
        // 按比例分配，至少分配1个老师
        instructorsForClass = Math.max(1, Math.floor(classSize / totalStudents * totalInstructors))
      }
      
      classInstructorAllocation[className] = instructorsForClass
      allocatedInstructors += instructorsForClass
    })
    
    // 第二步：为每个班级分配具体的老师并统计
    const instructorCounts: { [key: number]: number } = {}
    selectedInstructorIds.value.forEach(id => {
      instructorCounts[id] = 0
    })
    
    let instructorIndex = 0
    
    sortedClasses.forEach(([className, students]) => {
      const numInstructors = classInstructorAllocation[className]
      
      // 从老师池中取出相应数量的老师
      const classInstructors: number[] = []
      for (let i = 0; i < numInstructors; i++) {
        if (instructorIndex < selectedInstructorIds.value.length) {
          classInstructors.push(selectedInstructorIds.value[instructorIndex])
          instructorIndex++
        }
      }
      
      // 在班级内部，将学生轮流分配给这些老师
      students.forEach((_, studentIdx) => {
        const instructorId = classInstructors[studentIdx % classInstructors.length]
        instructorCounts[instructorId] += 1
      })
    })
    
    return selectedInstructorIds.value.map(id => {
      const instructor = instructors.value.find(i => i.id === id)
      return {
        id,
        name: instructor?.name || '',
        count: instructorCounts[id] || 0
      }
    })
  }
  
  // 普通平均分配
  const baseCount = Math.floor(studentCount / instructorCount)
  const remainder = studentCount % instructorCount
  
  return selectedInstructorIds.value.map((id, index) => {
    const instructor = instructors.value.find(i => i.id === id)
    return {
      id,
      name: instructor?.name || '',
      count: baseCount + (index < remainder ? 1 : 0)
    }
  })
})

// 执行一键分配
const handleAutoAssign = async () => {
  if (selectedInstructorIds.value.length === 0) {
    ElMessage.warning('请至少选择一位指导老师')
    return
  }
  
  // 如果启用了同班级分组但没有选择班级筛选，给出提示
  if (sameClassGrouping.value && !filterClass.value) {
    ElMessage.warning('启用"同班级分组"时，建议先筛选班级')
  }
  
  try {
    autoAssigning.value = true
    const res: any = await api.post(`/assignments/auto-assign/${selectedSemesterId.value}`, {
      class_name: filterClass.value || null,
      college: filterCollege.value || null,
      major: filterMajor.value || null,
      instructor_ids: selectedInstructorIds.value,
      same_class_grouping: sameClassGrouping.value, // 传递同班级分组参数
    })
    ElMessage.success(res.message || `成功分配 ${res.assigned_count} 名学生`)
    autoAssignDialogVisible.value = false
    fetchAssignmentData()
  } catch (error) {
    // 错误由全局拦截器处理
  } finally {
    autoAssigning.value = false
  }
}

// 全选/取消全选当前筛选的学生
const handleSelectAll = () => {
  if (selectedStudents.value.length === filteredStudents.value.length) {
    selectedStudents.value = []
  } else {
    selectedStudents.value = filteredStudents.value.map(s => s.id)
  }
}

// AI 智能分配
const handleAIAssign = async () => {
  if (!selectedSemesterId.value) {
    ElMessage.warning('请先选择批次')
    return
  }
  aiAssigning.value = true
  aiAssignResult.value = null
  aiAssignDialogVisible.value = true
  try {
    const res: any = await api.post('/admin/ai-assignment', {
      semester_id: selectedSemesterId.value,
      instructor_ids: instructors.value.map((i: any) => i.id),
    })
    if (res.success) {
      aiAssignResult.value = res.data
    }
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || 'AI 智能分配失败')
  } finally {
    aiAssigning.value = false
  }
}

// 执行AI分配方案
const executeAIAssign = async () => {
  if (!aiAssignResult.value?.assignments) return
  try {
    for (const assignment of aiAssignResult.value.assignments) {
      if (assignment.students.length > 0) {
        await api.post('/assignments/batch', {
          semester_id: selectedSemesterId.value,
          instructor_id: assignment.instructor_id,
          student_ids: assignment.students.map((s: any) => s.id),
        })
      }
    }
    ElMessage.success('AI 分配方案已执行')
    aiAssignDialogVisible.value = false
    fetchAssignmentData()
  } catch (error) {
    ElMessage.error('执行分配方案失败')
  }
}

onMounted(fetchSemesters)
</script>

<template>
  <div v-loading="loading">
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-2xl font-bold">分组分配</h2>
      <div class="flex items-center gap-3">
        <el-select
          v-model="selectedSemesterId"
          placeholder="选择批次"
          @change="fetchAssignmentData"
          class="w-72"
          style="min-width: 180px;"
        >
          <el-option v-for="s in semesters" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <input
          ref="importInputRef"
          type="file"
          accept=".xlsx,.xls"
          class="hidden"
          @change="handleImportChange"
        />
        <el-button @click="handleDownloadTemplate">下载模板</el-button>
        <el-button type="primary" @click="handleImportClick" :loading="importing">导入分配</el-button>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Left: Unassigned Students -->
      <el-card>
        <template #header>
          <div class="flex justify-between items-center">
            <span class="font-bold">待分配学生 ({{ filteredStudents.length }}/{{ unassignedStudents.length }})</span>
          </div>
        </template>
        
        <!-- 筛选条件和操作按钮 - 整合为一行 -->
        <div class="mb-4 flex items-center justify-between gap-2 flex-wrap">
          <div class="flex items-center gap-2">
            <el-select v-model="filterCollege" placeholder="学院" clearable size="small" style="width: 120px">
              <el-option v-for="c in filterOptions.colleges" :key="c" :label="c" :value="c" />
            </el-select>
            <el-select v-model="filterMajor" placeholder="专业" clearable size="small" style="width: 120px">
              <el-option v-for="m in filterOptions.majors" :key="m" :label="m" :value="m" />
            </el-select>
            <el-select v-model="filterClass" placeholder="班级" clearable size="small" style="width: 140px">
              <el-option v-for="c in filterOptions.classes" :key="c" :label="c" :value="c" />
            </el-select>
          </div>
          <div class="flex items-center gap-2">
            <el-button size="small" @click="handleSelectAll">
              {{ selectedStudents.length === filteredStudents.length && filteredStudents.length > 0 ? '取消全选' : '全选' }}
            </el-button>
            <el-button type="warning" size="small" @click="handleAIAssign" :disabled="filteredStudents.length === 0" :loading="aiAssigning">
              AI分配
            </el-button>
            <el-button type="success" size="small" @click="openAutoAssignDialog" :disabled="filteredStudents.length === 0">
              一键分配
            </el-button>
          </div>
        </div>
        
        <div v-if="!selectedSemesterId" class="text-center py-8 text-gray-400">
          请先选择批次
        </div>
        <div v-else-if="filteredStudents.length === 0" class="text-center py-8 text-gray-400">
          {{ unassignedStudents.length === 0 ? '暂无未分配学生' : '没有匹配的学生' }}
        </div>
        
        <div class="max-h-96 overflow-y-auto">
          <el-checkbox-group v-model="selectedStudents" class="space-y-2">
            <div v-for="student in filteredStudents" :key="student.id" 
                 class="p-3 border rounded hover:bg-gray-50">
              <el-checkbox :label="student.id" class="!items-start w-full">
                <div class="flex flex-col">
                  <div class="flex items-center gap-2">
                    <span class="font-medium">{{ student.name }}</span>
                    <span class="text-gray-400 text-sm">({{ student.user_code }})</span>
                  </div>
                  <div class="text-xs text-gray-500 mt-1">
                    <span v-if="student.college">{{ student.college }}</span>
                    <span v-if="student.major"> · {{ student.major }}</span>
                    <span v-if="student.class_name"> · {{ student.class_name }}</span>
                  </div>
                </div>
              </el-checkbox>
            </div>
          </el-checkbox-group>
        </div>

        <!-- Batch Assign Action -->
        <div v-if="unassignedStudents.length > 0" class="mt-4 pt-4 border-t">
          <div class="flex items-center gap-4">
            <el-select v-model="selectedInstructor" placeholder="选择指导老师" class="flex-1">
              <el-option v-for="i in instructors" :key="i.id" :label="i.name" :value="i.id" />
            </el-select>
            <el-button type="primary" @click="handleBatchAssign" :disabled="selectedStudents.length === 0">
              分配选中 ({{ selectedStudents.length }})
            </el-button>
          </div>
        </div>
      </el-card>

      <!-- Right: Assigned Groups -->
      <el-card>
        <template #header>
          <div class="flex justify-between items-center">
            <span class="font-bold">已分配情况 ({{ allFilteredAssignedStudentIds.length }}人)</span>
          </div>
        </template>

        <!-- 筛选条件和操作按钮 -->
        <div v-if="selectedSemesterId && assignmentOverview.length > 0" class="mb-4">
          <div class="flex items-center gap-2 mb-3 flex-wrap">
            <el-select v-model="assignedFilterInstructor" placeholder="指导老师" clearable size="small" style="width: 140px">
              <el-option v-for="i in instructors" :key="i.id" :label="i.name" :value="i.id" />
            </el-select>
            <el-select v-model="assignedFilterCollege" placeholder="学院" clearable size="small" style="width: 120px">
              <el-option v-for="c in filterOptions.colleges" :key="c" :label="c" :value="c" />
            </el-select>
            <el-select v-model="assignedFilterMajor" placeholder="专业" clearable size="small" style="width: 120px">
              <el-option v-for="m in filterOptions.majors" :key="m" :label="m" :value="m" />
            </el-select>
            <el-select v-model="assignedFilterClass" placeholder="班级" clearable size="small" style="width: 140px">
              <el-option v-for="c in filterOptions.classes" :key="c" :label="c" :value="c" />
            </el-select>
          </div>
          <div class="flex items-center gap-2">
            <el-button size="small" @click="handleSelectAllAssigned">
              {{ selectedAssignedStudents.length === allFilteredAssignedStudentIds.length && allFilteredAssignedStudentIds.length > 0 ? '取消全选' : '全选' }}
            </el-button>
            <el-button 
              type="danger" 
              size="small" 
              @click="handleBatchUnassign" 
              :disabled="selectedAssignedStudents.length === 0"
            >
              批量取消 ({{ selectedAssignedStudents.length }})
            </el-button>
          </div>
        </div>

        <div v-if="!selectedSemesterId" class="text-center py-8 text-gray-400">
          请先选择批次
        </div>
        <div v-else-if="assignmentOverview.length === 0" class="text-center py-8 text-gray-400">
          暂无分配数据
        </div>
        <div v-else-if="filteredAssignmentOverview.length === 0" class="text-center py-8 text-gray-400">
          没有匹配的分配数据
        </div>

        <el-collapse v-else>
          <el-collapse-item
            v-for="group in filteredAssignmentOverview"
            :key="group.instructor.id"
          >
            <template #title>
              <div class="flex items-center">
                <el-avatar :size="32" :src="getAvatarUrl(group.instructor.user_code)" class="mr-3 border-2 border-white shadow-sm bg-cyan-50" />
                <span class="font-medium">{{ group.instructor.name }}</span>
                <el-tag size="small" class="ml-2">{{ group.students.length }} 人</el-tag>
              </div>
            </template>
            <div class="space-y-2">
              <div v-for="student in group.students" :key="student.id"
                   class="flex justify-between items-center p-3 bg-gray-50 rounded hover:bg-gray-100 transition-colors">
                <div class="flex items-center gap-3 flex-1">
                  <el-checkbox 
                    :model-value="selectedAssignedStudents.includes(student.id)" 
                    @change="(val: any) => {
                      if (val) {
                        if (!selectedAssignedStudents.includes(student.id)) {
                          selectedAssignedStudents.push(student.id)
                        }
                      } else {
                        const index = selectedAssignedStudents.indexOf(student.id)
                        if (index > -1) {
                          selectedAssignedStudents.splice(index, 1)
                        }
                      }
                    }"
                  />
                  <div class="flex flex-col gap-1 flex-1">
                    <div class="flex items-center gap-2">
                      <span class="font-medium text-gray-800">{{ student.name }}</span>
                      <span class="text-gray-400 text-sm">({{ student.user_code }})</span>
                    </div>
                    <div class="text-xs text-gray-600">
                      <span v-if="student.college" class="mr-2">{{ student.college }}</span>
                      <span v-if="student.major" class="mr-2">{{ student.major }}</span>
                      <span v-if="student.class_name">{{ student.class_name }}</span>
                    </div>
                  </div>
                </div>
                <el-button size="small" type="danger" text @click="handleUnassign(student.id)">
                  取消分配
                </el-button>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </el-card>
    </div>

    <!-- 一键分配弹窗 -->
    <el-dialog v-model="autoAssignDialogVisible" title="一键分配" width="500px">
      <div class="mb-4">
        <div class="text-gray-600 mb-2">
          将 <span class="font-bold text-blue-600">{{ filteredStudents.length }}</span> 名学生
          <span v-if="filterClass" class="text-gray-500">（{{ filterClass }}）</span>
          平均分配给以下指导老师：
        </div>
      </div>

      <!-- 同班级分组选项 -->
      <div class="mb-4 p-3 bg-blue-50 rounded border border-blue-200">
        <el-switch 
          v-model="sameClassGrouping" 
          active-text="同班级分组" 
          inactive-text="混合分组"
          class="mr-2"
        />
        <div class="text-xs text-gray-600 mt-2">
          <span v-if="sameClassGrouping" class="text-blue-600">
            ✓ 启用后，按学生比例分配老师给各班级，每个老师只负责一个班级的学生
          </span>
          <span v-else class="text-gray-500">
            混合分组模式下，学生将平均分配给所有老师，不考虑班级
          </span>
        </div>
      </div>

      <!-- 选择老师 -->
      <div class="mb-4">
        <div class="flex justify-between items-center mb-2">
          <span class="text-sm font-medium">选择指导老师</span>
          <el-button 
            size="small" 
            text 
            @click="selectedInstructorIds = selectedInstructorIds.length === instructors.length ? [] : instructors.map(i => i.id)"
          >
            {{ selectedInstructorIds.length === instructors.length ? '取消全选' : '全选' }}
          </el-button>
        </div>
        <el-checkbox-group v-model="selectedInstructorIds" class="flex flex-wrap gap-2">
          <el-checkbox 
            v-for="i in instructors" 
            :key="i.id" 
            :label="i.id"
            class="!mr-0"
          >
            {{ i.name }}
          </el-checkbox>
        </el-checkbox-group>
      </div>

      <!-- 分配预览 -->
      <div v-if="autoAssignPreview.length > 0" class="bg-gray-50 rounded p-3">
        <div class="flex justify-between items-center mb-2">
          <div class="text-sm font-medium">分配预览</div>
          <el-tag v-if="sameClassGrouping" type="info" size="small">按班级分组</el-tag>
        </div>
        <div v-if="sameClassGrouping" class="text-xs text-blue-600 mb-2 bg-blue-50 p-2 rounded">
          同班级分组：按学生数比例分配老师给各班级，保证负载均衡且每个老师只负责一个班级
        </div>
        <div class="grid grid-cols-2 gap-2 text-sm">
          <div 
            v-for="item in autoAssignPreview" 
            :key="item.id"
            class="flex justify-between items-center p-2 bg-white rounded"
            :class="{ 'opacity-50': item.count === 0 }"
          >
            <span>{{ item.name }}</span>
            <el-tag size="small" :type="item.count === 0 ? 'info' : undefined">{{ item.count }} 人</el-tag>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="autoAssignDialogVisible = false">取消</el-button>
        <el-button 
          type="primary" 
          :loading="autoAssigning" 
          :disabled="selectedInstructorIds.length === 0"
          @click="handleAutoAssign"
        >
          确认分配
        </el-button>
      </template>
    </el-dialog>

    <!-- AI 智能分配对话框 -->
    <el-dialog v-model="aiAssignDialogVisible" title="AI 智能分配方案" width="650px" top="5vh">
      <div v-if="aiAssigning" class="text-center py-12">
        <div class="ai-loading-spinner"></div>
        <p class="mt-4 text-gray-600 font-medium">AI 正在分析最优分配方案...</p>
        <p class="text-sm text-gray-400 mt-1">考虑导师负载、学生需求等因素</p>
      </div>
      <div v-else-if="aiAssignResult">
        <div v-if="aiAssignResult.message" class="text-center py-8 text-gray-500">{{ aiAssignResult.message }}</div>
        <template v-else>
          <div class="flex items-center justify-between mb-4 bg-blue-50 p-3 rounded-lg">
            <div>
              <span class="text-sm text-gray-600">待分配：<strong class="text-blue-600">{{ aiAssignResult.total_unassigned }}</strong> 人</span>
              <span class="ml-4 text-sm text-gray-600">导师：<strong class="text-blue-600">{{ aiAssignResult.total_instructors }}</strong> 人</span>
            </div>
            <el-tag type="success">均衡度: {{ aiAssignResult.balance_score }}%</el-tag>
          </div>
          <div class="space-y-3">
            <div v-for="a in aiAssignResult.assignments" :key="a.instructor_id" class="p-4 border rounded-lg">
              <div class="flex items-center justify-between mb-2">
                <div class="font-medium">{{ a.instructor_name }}</div>
                <div class="flex items-center gap-2">
                  <el-tag size="small" type="info">已有 {{ a.current_students }} 人</el-tag>
                  <el-tag size="small" type="success">+{{ a.new_students }} 人</el-tag>
                  <el-tag size="small">共 {{ a.total_after }} 人</el-tag>
                </div>
              </div>
              <div class="text-xs text-gray-500 mb-2">{{ a.reason }}</div>
              <div class="flex flex-wrap gap-1">
                <el-tag v-for="s in a.students.slice(0, 10)" :key="s.id" size="small" class="!mr-0">
                  {{ s.name }}
                </el-tag>
                <el-tag v-if="a.students.length > 10" size="small" type="info">+{{ a.students.length - 10 }}人</el-tag>
              </div>
            </div>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="aiAssignDialogVisible = false">取消</el-button>
        <el-button v-if="aiAssignResult?.assignments?.length" type="primary" @click="executeAIAssign">
          执行此方案
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>
