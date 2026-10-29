<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, UploadUserFile } from 'element-plus'
import { Download, Upload, UploadFilled, Search, Refresh, Delete } from '@element-plus/icons-vue'
import api from '@/utils/request'

const users = ref([])
const total = ref(0)
const loading = ref(false)
const importDialogVisible = ref(false)
const importLoading = ref(false)
const fileList = ref<UploadUserFile[]>([])

const query = reactive({
  page: 1,
  page_size: 20,
  role: '',
  keyword: ''
})

const fetchUsers = async () => {
  loading.value = true
  try {
    const params: any = {
      page: query.page,
      page_size: query.page_size,
    }
    if (query.role) params.role = query.role
    if (query.keyword) params.keyword = query.keyword

    const res: any = await api.get('/users', { params })
    users.value = res.items
    total.value = res.total
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

  try {
    const res: any = await api.post('/users/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    ElMessage.success(`成功导入 ${res.success_count} 条数据，失败 ${res.fail_count} 条`)
    importDialogVisible.value = false
    fileList.value = []
    fetchUsers()
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

onMounted(fetchUsers)
</script>

<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-2xl font-bold">用户管理</h2>
      <div class="space-x-4">
        <el-button type="primary" :icon="Download" @click="downloadTemplate">下载模板</el-button>
        <el-button type="success" :icon="Upload" @click="importDialogVisible = true">导入用户</el-button>
      </div>
    </div>

    <!-- Filters + User Table -->
    <el-card>
      <template #header>
        <div class="flex items-center gap-4">
          <el-select
            v-model="query.role"
            placeholder="选择角色"
            clearable
            @change="handleSearch"
            style="width: 160px;"
          >
            <el-option label="管理员" value="admin" />
            <el-option label="指导老师" value="instructor" />
            <el-option label="学生" value="student" />
          </el-select>
          <el-input
            v-model="query.keyword"
            placeholder="搜索姓名 / 工号 / 学院 / 班级"
            :prefix-icon="Search"
            clearable
            @clear="handleSearch"
            @keyup.enter="handleSearch"
            style="width: 260px;"
          />
          <el-button type="primary" @click="handleSearch">查询</el-button>
        </div>
      </template>

      <el-table :data="users" v-loading="loading" stripe :style="{ width: '100%' }">
        <el-table-column prop="user_code" label="工号/学号" width="140" />
        <el-table-column prop="name" label="姓名" width="120" />
        <el-table-column prop="role" label="角色" width="120">
          <template #default="scope">
            <el-tag v-if="scope.row.role === 'admin'" type="danger">管理员</el-tag>
            <el-tag v-else-if="scope.row.role === 'instructor'" type="primary">指导老师</el-tag>
            <el-tag v-else type="success">学生</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="college" label="学院" min-width="140" />
        <el-table-column prop="major" label="专业" min-width="140" />
        <el-table-column prop="class_name" label="班级" min-width="120" />
        <el-table-column prop="head_teacher" label="班主任" min-width="120" />
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
        <el-table-column label="操作" fixed="right" width="300">
          <template #default="{ row }">
            <div class="flex gap-1">
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
            </div>
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

    <!-- Import Dialog -->
    <el-dialog v-model="importDialogVisible" title="批量导入用户" width="500px">
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
  </div>
</template>
