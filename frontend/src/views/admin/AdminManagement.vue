<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Delete, Cpu } from '@element-plus/icons-vue'
import api from '@/utils/request'
import { useAuthStore } from '@/stores/auth'
import { aiApi } from '@/api/ai'

const authStore = useAuthStore()

const users = ref([])
const total = ref(0)
const loading = ref(false)
const addDialogVisible = ref(false)
const addLoading = ref(false)
const addFormRef = ref()

// 筛选选项
const filterOptions = ref<{ colleges: string[] }>({
  colleges: [],
})

const addForm = reactive({
  user_code: '',
  name: '',
  college: '',
  password: '',
  confirmPassword: ''
})

const addFormRules = {
  user_code: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  college: [{ required: true, message: '请输入学院', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少6位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (rule: any, value: any, callback: any) => {
        if (value !== addForm.password) {
          callback(new Error('两次密码输入不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

const query = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
  college: '',
  is_active: null as boolean | null
})

// 获取筛选选项
const fetchFilterOptions = async () => {
  try {
    const res: any = await api.get('/users/filter/options', {
      params: { role: 'admin' }
    })
    filterOptions.value = res
  } catch (error) {
    // Error handled by interceptor
  }
}

const fetchAdmins = async () => {
  loading.value = true
  try {
    const params: any = {
      page: query.page,
      page_size: query.page_size,
      role: 'admin'
    }
    if (query.keyword) params.keyword = query.keyword
    if (query.college) params.college = query.college
    if (query.is_active !== null) params.is_active = query.is_active

    const res: any = await api.get('/users', { params })
    users.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  query.page = 1
  fetchAdmins()
}

const handlePageChange = (page: number) => {
  query.page = page
  fetchAdmins()
}

const openAddDialog = () => {
  addForm.user_code = ''
  addForm.name = ''
  addForm.college = ''
  addForm.password = ''
  addForm.confirmPassword = ''
  addDialogVisible.value = true
}

const handleAddAdmin = async () => {
  if (!addFormRef.value) return
  await addFormRef.value.validate(async (valid: boolean) => {
    if (valid) {
      addLoading.value = true
      try {
        await api.post('/users/admin', {
          user_code: addForm.user_code,
          name: addForm.name,
          college: addForm.college,
          password: addForm.password,
          role: 'admin'
        })
        ElMessage.success('管理员添加成功')
        addDialogVisible.value = false
        fetchAdmins()
      } catch (error) {
        // Error handled by interceptor
      } finally {
        addLoading.value = false
      }
    }
  })
}

const handleResetPassword = async (row: any) => {
  try {
    await api.post(`/users/${row.id}/reset-password`)
    ElMessage.success(`已重置用户 ${row.name} 的密码为账号`)
  } catch (error) {
    // Error handled by interceptor
  }
}

const handleDelete = async (row: any) => {
  if (row.is_super_admin) {
    ElMessage.warning('不能删除超级管理员')
    return
  }
  try {
    await ElMessageBox.confirm(
      '确定永久删除该管理员吗？此操作不可恢复！',
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    await api.delete(`/users/${row.id}/permanent`)
    ElMessage.success('管理员已删除')
    fetchAdmins()
  } catch (error: any) {
    if (error !== 'cancel') {
      // Error handled by interceptor
    }
  }
}

// 禁用/启用管理员
const handleToggleStatus = async (row: any) => {
  if (row.is_super_admin) {
    ElMessage.warning('不能禁用超级管理员')
    return
  }
  
  const action = row.is_active ? '禁用' : '启用'
  try {
    await ElMessageBox.confirm(
      `确定要${action}该管理员吗？`,
      `${action}确认`,
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    await api.put(`/users/${row.id}`, {
      is_active: !row.is_active
    })
    ElMessage.success(`已${action}管理员`)
    fetchAdmins()
  } catch (error: any) {
    if (error !== 'cancel') {
      // Error handled by interceptor
    }
  }
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
      role: row.is_super_admin ? 'super_admin' : 'admin',
      college: row.college || '未知',
      is_active: row.is_active,
      context: 'AI用户画像：请根据管理员基本信息生成一段简短的管理员画像描述，包括管理职责和建议，60-120字'
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
  fetchAdmins()
  fetchFilterOptions()
})
</script>

<template>
  <div class="h-full flex flex-col">
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-2xl font-bold">管理员管理</h2>
      <el-button type="primary" :icon="Plus" @click="openAddDialog">添加管理员</el-button>
    </div>

    <el-card class="flex-1" body-style="height: 100%; display: flex; flex-direction: column;">
      <!-- 筛选条件 -->
      <div class="mb-4 flex items-center gap-3 flex-wrap">
        <el-select
          v-model="query.college"
          placeholder="学院"
          clearable
          size="small"
          style="width: 140px"
        >
          <el-option v-for="c in filterOptions.colleges" :key="c" :label="c" :value="c" />
        </el-select>
        <el-select
          v-model="query.is_active"
          placeholder="状态"
          clearable
          size="small"
          style="width: 120px"
        >
          <el-option label="启用" :value="true" />
          <el-option label="禁用" :value="false" />
        </el-select>
        <el-input
          v-model="query.keyword"
          placeholder="搜索姓名/账号"
          :prefix-icon="Search"
          clearable
          size="small"
          @clear="handleSearch"
          @keyup.enter="handleSearch"
          style="width: 200px;"
        />
        <el-button type="primary" size="small" @click="handleSearch">查询</el-button>
      </div>

      <!-- 数据表格 -->
      <div class="flex-1 overflow-hidden">
        <el-table :data="users" v-loading="loading" stripe height="100%">
        <el-table-column prop="user_code" label="账号" width="150" />
        <el-table-column prop="name" label="姓名" width="120" />
        <el-table-column prop="college" label="学院" width="180" show-overflow-tooltip />
        <el-table-column label="角色" width="130">
          <template #default="scope">
            <el-tag :type="scope.row.is_super_admin ? 'danger' : 'primary'">
              {{ scope.row.is_super_admin ? '超级管理员' : '普通管理员' }}
            </el-tag>
          </template>
        </el-table-column>
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
            <template v-if="!row.is_super_admin">
              <el-button 
                size="small" 
                :type="row.is_active ? 'warning' : 'success'"
                @click="handleToggleStatus(row)"
              >
                {{ row.is_active ? '禁用' : '启用' }}
              </el-button>
              <el-popconfirm 
                title="确定重置密码为账号吗？" 
                @confirm="handleResetPassword(row)"
              >
                <template #reference>
                  <el-button size="small">重置密码</el-button>
                </template>
              </el-popconfirm>
              <el-button 
                size="small" 
                type="danger"
                @click="handleDelete(row)"
              >
                删除
              </el-button>
            </template>
            <el-tag v-else type="info" size="small">系统账号</el-tag>
            <el-button size="small" type="primary" plain @click="openAIProfile(row)">
              <el-icon class="mr-0.5"><Cpu /></el-icon>AI画像
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      </div>

      <!-- 分页 -->
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

    <!-- Add Admin Dialog -->
    <el-dialog v-model="addDialogVisible" title="添加管理员" width="500px">
      <el-form ref="addFormRef" :model="addForm" :rules="addFormRules" label-width="100px">
        <el-form-item label="账号" prop="user_code">
          <el-input v-model="addForm.user_code" placeholder="请输入管理员账号" />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="addForm.name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="学院" prop="college">
          <el-input v-model="addForm.college" placeholder="请输入学院名称" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input 
            v-model="addForm.password" 
            type="password" 
            placeholder="请输入密码（至少6位）" 
            show-password
          />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input 
            v-model="addForm.confirmPassword" 
            type="password" 
            placeholder="请再次输入密码" 
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleAddAdmin" :loading="addLoading">确定</el-button>
      </template>
    </el-dialog>

    <!-- AI 画像对话框 -->
    <el-dialog v-model="aiProfileVisible" title="AI 管理员画像" width="500px">
      <div v-if="aiProfileUser" class="mb-4">
        <el-descriptions :column="2" size="small" border>
          <el-descriptions-item label="姓名">{{ aiProfileUser.name }}</el-descriptions-item>
          <el-descriptions-item label="账号">{{ aiProfileUser.user_code }}</el-descriptions-item>
          <el-descriptions-item label="学院">{{ aiProfileUser.college || '-' }}</el-descriptions-item>
          <el-descriptions-item label="角色">
            <el-tag :type="aiProfileUser.is_super_admin ? 'danger' : 'primary'" size="small">
              {{ aiProfileUser.is_super_admin ? '超级管理员' : '普通管理员' }}
            </el-tag>
          </el-descriptions-item>
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
