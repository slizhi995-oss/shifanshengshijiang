<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, UploadUserFile } from 'element-plus'
import { Download, Upload, UploadFilled, Search, Refresh, Delete, Plus, Cpu } from '@element-plus/icons-vue'
import api from '@/utils/request'
import { aiApi } from '@/api/ai'

const users = ref([])
const total = ref(0)
const loading = ref(false)
const importDialogVisible = ref(false)
const importLoading = ref(false)
const fileList = ref<UploadUserFile[]>([])
const selectedUsers = ref<any[]>([])
const tableRef = ref()

// 新增用户
const addDialogVisible = ref(false)
const addLoading = ref(false)
const addFormRef = ref()
const addForm = reactive({
  user_code: '',
  name: '',
  college: '',
  major: '',
})
const addFormRules = {
  user_code: [{ required: true, message: '请输入工号', trigger: 'blur' }],
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
}

// 筛选选项
const filterOptions = ref({
  colleges: [] as string[],
  majors: [] as string[],
})

const query = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
  college: '',
  major: '',
  is_active: '', // 新增状态筛选
})

const fetchFilterOptions = async () => {
  try {
    const res: any = await api.get('/users/filter/options', { params: { role: 'instructor' } })
    filterOptions.value.colleges = res.colleges || []
    filterOptions.value.majors = res.majors || []
  } catch (e) {
    // 忽略错误
  }
}

const fetchUsers = async () => {
  loading.value = true
  try {
    const params: any = {
      page: query.page,
      page_size: query.page_size,
      role: 'instructor', // 只查询指导老师
    }
    if (query.keyword) params.keyword = query.keyword
    if (query.college) params.college = query.college
    if (query.major) params.major = query.major
    if (query.is_active !== '') params.is_active = query.is_active

    const res: any = await api.get('/users', { params })
    users.value = res.items
    total.value = res.total
    selectedUsers.value = [] // 重置选中项
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  query.page = 1
  fetchUsers()
}

const handlePageChange = (page: number) => {
  query.page = page
  fetchUsers()
}

const downloadTemplate = async () => {
  try {
    const response: any = await api.get('/users/import/template', { responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([response]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', 'user_import_template.xlsx')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  } catch (error) {
    ElMessage.error('下载模板失败')
  }
}

const handleImport = async () => {
  if (fileList.value.length === 0) {
    ElMessage.warning('请选择文件')
    return
  }

  importLoading.value = true
  const formData = new FormData()
  formData.append('file', fileList.value[0].raw as File)
  formData.append('role', 'instructor') // 指定只导入指导老师

  try {
    const res: any = await api.post('/users/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    
    // 更详细的导入结果提示
    if (res.fail_count === 0) {
      ElMessage.success(`成功导入 ${res.success_count} 名指导老师`)
    } else {
      ElMessage.warning({
        message: `导入完成：成功 ${res.success_count} 条，失败 ${res.fail_count} 条${res.error_details ? '\n' + res.error_details : ''}`,
        duration: 5000,
        dangerouslyUseHTMLString: true
      })
    }
    
    importDialogVisible.value = false
    fileList.value = []
    fetchUsers()
    fetchFilterOptions()
  } catch (error) {
    // Error handled by interceptor
  } finally {
    importLoading.value = false
  }
}

const handleResetPassword = async (row: any) => {
  try {
    await api.post(`/users/${row.id}/reset-password`)
    ElMessage.success(`已重置用户 ${row.name} 的密码`)
  } catch (error) {
    // Error handled by interceptor
  }
}

// 禁用/启用用户
const handleToggleStatus = async (row: any) => {
  try {
    if (row.is_active) {
      await api.delete(`/users/${row.id}`)
      ElMessage.success('用户已禁用')
    } else {
      await api.put(`/users/${row.id}`, { is_active: true })
      ElMessage.success('用户已启用')
    }
    fetchUsers()
  } catch (error) {
    // Error handled by interceptor
  }
}

// 永久删除用户
const handleDeletePermanent = async (row: any) => {
  try {
    await api.delete(`/users/${row.id}/permanent`)
    ElMessage.success('用户已删除')
    fetchUsers()
  } catch (error) {
    // Error handled by interceptor
  }
}

const handleReset = () => {
  query.keyword = ''
  query.college = ''
  query.major = ''
  query.is_active = ''
  query.page = 1
  fetchUsers()
}

// 批量操作相关
const handleSelectionChange = (selection: any[]) => {
  selectedUsers.value = selection
}

const handleBatchResetPassword = async () => {
  if (selectedUsers.value.length === 0) {
    ElMessage.warning('请先选择用户')
    return
  }
  try {
    const promises = selectedUsers.value.map(user => api.post(`/users/${user.id}/reset-password`))
    await Promise.all(promises)
    ElMessage.success(`已批量重置 ${selectedUsers.value.length} 名用户的密码`)
    selectedUsers.value = []
  } catch (error) {
    // Error handled by interceptor
  }
}

const handleBatchToggleStatus = async (isActive: boolean) => {
  if (selectedUsers.value.length === 0) {
    ElMessage.warning('请先选择用户')
    return
  }
  try {
    const promises = selectedUsers.value.map(user => {
      if (isActive) {
        return api.put(`/users/${user.id}`, { is_active: true })
      } else {
        return api.delete(`/users/${user.id}`)
      }
    })
    await Promise.all(promises)
    ElMessage.success(`已批量${isActive ? '启用' : '禁用'} ${selectedUsers.value.length} 名用户`)
    selectedUsers.value = []
    fetchUsers()
  } catch (error) {
    // Error handled by interceptor
  }
}

const handleBatchDelete = async () => {
  if (selectedUsers.value.length === 0) {
    ElMessage.warning('请先选择用户')
    return
  }
  try {
    const promises = selectedUsers.value.map(user => api.delete(`/users/${user.id}/permanent`))
    await Promise.all(promises)
    ElMessage.success(`已批量删除 ${selectedUsers.value.length} 名用户`)
    selectedUsers.value = []
    fetchUsers()
  } catch (error) {
    // Error handled by interceptor
  }
}

// 新增用户
const openAddDialog = () => {
  addForm.user_code = ''
  addForm.name = ''
  addForm.college = ''
  addForm.major = ''
  addDialogVisible.value = true
}

const handleAddUser = async () => {
  if (!addFormRef.value) return
  await addFormRef.value.validate(async (valid: boolean) => {
    if (valid) {
      addLoading.value = true
      try {
        await api.post('/users', {
          ...addForm,
          role: 'instructor',
        })
        ElMessage.success('指导老师添加成功')
        addDialogVisible.value = false
        fetchUsers()
        fetchFilterOptions()
      } catch (error) {
        // Error handled by interceptor
      } finally {
        addLoading.value = false
      }
    }
  })
}

// AI 画像
const aiProfileVisible = ref(false)
const aiProfileLoading = ref(false)
const aiProfileUser = ref<any>(null)
const aiProfileDisplayed = ref('')
let profileTimer: ReturnType<typeof setInterval> | null = null

const openAIProfile = async (row: any) => {
  aiProfileUser.value = row
  aiProfileVisible.value = true
  aiProfileLoading.value = true
  aiProfileDisplayed.value = ''
  try {
    const stats: Record<string, any> = {
      user_name: row.name,
      user_code: row.user_code,
      role: 'instructor',
      college: row.college || '未知',
      major: row.major || '未知',
      is_active: row.is_active,
      context: 'AI用户画像：请根据指导老师基本信息生成一段简短的导师画像描述，包括工作状态评估，60-120字'
    }
    const res = await aiApi.dataNarrative({ role: 'admin', stats })
    if (res.success && res.data?.narrative) {
      let i = 0
      if (profileTimer) clearInterval(profileTimer)
      profileTimer = setInterval(() => {
        if (i < res.data!.narrative.length) { aiProfileDisplayed.value += res.data!.narrative[i]; i++ }
        else { if (profileTimer) clearInterval(profileTimer) }
      }, 25)
    }
  } catch { aiProfileDisplayed.value = 'AI 画像生成失败' }
  finally { aiProfileLoading.value = false }
}

onMounted(() => {
  fetchFilterOptions()
  fetchUsers()
})
</script>

<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-2xl font-bold">指导老师管理</h2>
      <div class="space-x-4">
        <el-button type="primary" :icon="Plus" @click="openAddDialog">添加老师</el-button>
        <el-button :icon="Download" @click="downloadTemplate">下载模板</el-button>
        <el-button type="success" :icon="Upload" @click="importDialogVisible = true">批量导入</el-button>
      </div>
    </div>

    <!-- Filters + User Table -->
    <el-card>
      <template #header>
        <div class="flex items-center gap-4 flex-wrap">
          <el-select
            v-model="query.college"
            placeholder="选择学院"
            clearable
            filterable
            @change="handleSearch"
            style="width: 180px;"
          >
            <el-option v-for="c in filterOptions.colleges" :key="c" :label="c" :value="c" />
          </el-select>
          <el-select
            v-model="query.major"
            placeholder="选择专业"
            clearable
            filterable
            @change="handleSearch"
            style="width: 180px;"
          >
            <el-option v-for="m in filterOptions.majors" :key="m" :label="m" :value="m" />
          </el-select>
          <el-select
            v-model="query.is_active"
            placeholder="状态"
            clearable
            @change="handleSearch"
            style="width: 120px;"
          >
            <el-option label="启用" :value="true" />
            <el-option label="禁用" :value="false" />
          </el-select>
          <el-input
            v-model="query.keyword"
            placeholder="搜索姓名 / 工号"
            :prefix-icon="Search"
            clearable
            @clear="handleSearch"
            @keyup.enter="handleSearch"
            style="width: 200px;"
          />
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </div>
      </template>

      <!-- 批量操作区域 -->
      <div v-if="selectedUsers.length > 0" class="mb-4 p-3 bg-blue-50 rounded border border-blue-200">
        <div class="flex items-center justify-between">
          <span class="text-sm text-blue-700">已选中 {{ selectedUsers.length }} 项</span>
          <div class="flex gap-2">
            <el-popconfirm title="确定批量重置密码为工号吗？" @confirm="handleBatchResetPassword">
              <template #reference>
                <el-button size="small">批量重置密码</el-button>
              </template>
            </el-popconfirm>
            <el-popconfirm title="确定批量禁用吗？" @confirm="handleBatchToggleStatus(false)">
              <template #reference>
                <el-button size="small" type="warning">批量禁用</el-button>
              </template>
            </el-popconfirm>
            <el-popconfirm title="确定批量启用吗？" @confirm="handleBatchToggleStatus(true)">
              <template #reference>
                <el-button size="small" type="success">批量启用</el-button>
              </template>
            </el-popconfirm>
            <el-popconfirm title="确定批量删除吗？此操作不可恢复！" @confirm="handleBatchDelete">
              <template #reference>
                <el-button size="small" type="danger">批量删除</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </div>

      <el-table 
        ref="tableRef"
        :data="users" 
        v-loading="loading" 
        stripe 
        :style="{ width: '100%' }"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="user_code" label="工号" width="140" />
        <el-table-column prop="name" label="姓名" width="120" />
        <el-table-column prop="college" label="学院" min-width="160" />
        <el-table-column prop="major" label="专业" min-width="160" />
        <el-table-column label="状态" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.is_active ? 'success' : 'danger'">
              {{ scope.row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="190" show-overflow-tooltip>
          <template #default="scope">
            {{ new Date(scope.row.created_at).toLocaleString() }}
          </template>
        </el-table-column>
        <el-table-column label="操作" fixed="right" width="280">
          <template #default="{ row }">
            <el-popconfirm title="确定重置密码为工号吗？" @confirm="handleResetPassword(row)">
              <template #reference>
                <el-button size="small">重置密码</el-button>
              </template>
            </el-popconfirm>
            <el-popconfirm :title="row.is_active ? '确定禁用该用户吗？' : '确定启用该用户吗？'" @confirm="handleToggleStatus(row)">
              <template #reference>
                <el-button size="small" :type="row.is_active ? 'warning' : 'success'">
                  {{ row.is_active ? '禁用' : '启用' }}
                </el-button>
              </template>
            </el-popconfirm>
            <el-popconfirm title="确定永久删除该用户吗？此操作不可恢复！" @confirm="handleDeletePermanent(row)">
              <template #reference>
                <el-button size="small" type="danger">删除</el-button>
              </template>
            </el-popconfirm>
            <el-button size="small" type="primary" plain @click="openAIProfile(row)">
              <el-icon class="mr-0.5"><Cpu /></el-icon>AI画像
            </el-button>
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

    <!-- Add User Dialog -->
    <el-dialog v-model="addDialogVisible" title="添加指导老师" width="500px">
      <el-form ref="addFormRef" :model="addForm" :rules="addFormRules" label-width="80px">
        <el-form-item label="工号" prop="user_code">
          <el-input v-model="addForm.user_code" placeholder="请输入工号" />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="addForm.name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="学院">
          <el-input v-model="addForm.college" placeholder="请输入学院" />
        </el-form-item>
        <el-form-item label="专业">
          <el-input v-model="addForm.major" placeholder="请输入专业" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleAddUser" :loading="addLoading">确定</el-button>
      </template>
    </el-dialog>

    <!-- Import Dialog -->
    <el-dialog v-model="importDialogVisible" title="批量导入指导老师" width="500px">
      <el-upload
        class="upload-demo"
        drag
        action="#"
        :auto-upload="false"
        :limit="1"
        v-model:file-list="fileList"
        accept=".xlsx,.xls"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          拖拽文件到此处或 <em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            只能上传 xlsx/xls 文件，请先下载模板填写。
          </div>
        </template>
      </el-upload>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="importDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleImport" :loading="importLoading">
            确定导入
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- AI 画像对话框 -->
    <el-dialog v-model="aiProfileVisible" title="AI 导师画像" width="500px">
      <div v-if="aiProfileUser" class="mb-4">
        <el-descriptions :column="2" size="small" border>
          <el-descriptions-item label="姓名">{{ aiProfileUser.name }}</el-descriptions-item>
          <el-descriptions-item label="工号">{{ aiProfileUser.user_code }}</el-descriptions-item>
          <el-descriptions-item label="学院">{{ aiProfileUser.college || '-' }}</el-descriptions-item>
          <el-descriptions-item label="专业">{{ aiProfileUser.major || '-' }}</el-descriptions-item>
        </el-descriptions>
      </div>
      <el-card shadow="never" style="background: #f0f9ff; border-color: #bae6fd;">
        <div class="flex items-start gap-3">
          <div class="w-8 h-8 rounded-lg bg-cyan-100 flex items-center justify-center text-cyan-600 flex-shrink-0">
            <el-icon :size="16"><Cpu /></el-icon>
          </div>
          <div class="flex-1">
            <div class="flex items-center gap-2 mb-2">
              <span class="font-semibold text-sm text-gray-700">AI 智能画像</span>
              <span class="inline-block w-1.5 h-1.5 rounded-full bg-cyan-500" :class="{ 'animate-pulse': aiProfileLoading }"></span>
            </div>
            <div v-if="aiProfileLoading && !aiProfileDisplayed" class="text-sm text-gray-400">AI 正在生成画像...</div>
            <div v-else-if="aiProfileDisplayed" class="text-sm text-gray-600 leading-relaxed">
              {{ aiProfileDisplayed }}<span v-if="aiProfileLoading" class="text-cyan-500 font-bold animate-pulse">|</span>
            </div>
            <div v-else class="text-sm text-gray-400">暂无画像数据</div>
          </div>
        </div>
      </el-card>
      <template #footer>
        <el-button @click="aiProfileVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>
