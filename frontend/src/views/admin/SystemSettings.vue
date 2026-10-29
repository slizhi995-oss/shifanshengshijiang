<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, Picture } from '@element-plus/icons-vue'
import api from '@/utils/request'

interface SystemSettings {
  site_name: string
  site_logo_url: string
  login_bg_url: string
  school_name: string
  default_avatar_url: string
  footer_text: string
}

const loading = ref(false)
const saving = ref(false)
const uploadingLogo = ref(false)
const uploadingBg = ref(false)
const uploadingAvatar = ref(false)

const settings = reactive<SystemSettings>({
  site_name: '智教领航',
  site_logo_url: '',
  login_bg_url: '',
  school_name: '高校师范',
  default_avatar_url: '',
  footer_text: ''
})

const fetchSettings = async () => {
  loading.value = true
  try {
    const res: any = await api.get('/system/settings')
    Object.assign(settings, res)
  } catch (error) {
    // 如果没有设置，使用默认值
  } finally {
    loading.value = false
  }
}

const handleSave = async () => {
  saving.value = true
  try {
    await api.put('/system/settings', settings)
    ElMessage.success('系统设置已保存')
  } catch (error) {
    // Error handled by interceptor
  } finally {
    saving.value = false
  }
}

const handleUploadLogo = async (options: any) => {
  const { file } = options
  const formData = new FormData()
  formData.append('file', file)
  
  uploadingLogo.value = true
  try {
    const res: any = await api.post('/system/upload/logo', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    settings.site_logo_url = res.url
    ElMessage.success('Logo上传成功')
  } catch (error) {
    ElMessage.error('Logo上传失败')
  } finally {
    uploadingLogo.value = false
  }
  return false
}

const handleUploadBg = async (options: any) => {
  const { file } = options
  const formData = new FormData()
  formData.append('file', file)
  
  uploadingBg.value = true
  try {
    const res: any = await api.post('/system/upload/background', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    settings.login_bg_url = res.url
    ElMessage.success('背景图上传成功')
  } catch (error) {
    ElMessage.error('背景图上传失败')
  } finally {
    uploadingBg.value = false
  }
  return false
}

const handleUploadAvatar = async (options: any) => {
  const { file } = options
  const formData = new FormData()
  formData.append('file', file)
  
  uploadingAvatar.value = true
  try {
    const res: any = await api.post('/system/upload/avatar', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    settings.default_avatar_url = res.url
    ElMessage.success('默认头像上传成功')
  } catch (error) {
    ElMessage.error('默认头像上传失败')
  } finally {
    uploadingAvatar.value = false
  }
  return false
}

onMounted(fetchSettings)
</script>

<template>
  <div v-loading="loading">
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-2xl font-bold">系统设置</h2>
      <el-button type="primary" @click="handleSave" :loading="saving">保存设置</el-button>
    </div>

    <el-row :gutter="20">
      <!-- 基本信息设置 -->
      <el-col :xs="24" :lg="12">
        <el-card class="mb-6">
          <template #header>
            <div class="font-bold">基本信息</div>
          </template>
          <el-form label-width="120px" label-position="left">
            <el-form-item label="网站名称">
              <el-input 
                v-model="settings.site_name" 
                placeholder="请输入网站名称"
                maxlength="50"
                show-word-limit
              />
            </el-form-item>
            <el-form-item label="学校名称">
              <el-input 
                v-model="settings.school_name" 
                placeholder="请输入学校名称"
                maxlength="50"
                show-word-limit
              />
            </el-form-item>
            <el-form-item label="页脚文字">
              <el-input 
                v-model="settings.footer_text" 
                type="textarea"
                :rows="3"
                placeholder="请输入页脚文字（如版权信息等）"
                maxlength="200"
                show-word-limit
              />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 图片资源设置 -->
      <el-col :xs="24" :lg="12">
        <el-card class="mb-6">
          <template #header>
            <div class="font-bold">图片资源</div>
          </template>
          <el-form label-width="120px" label-position="left">
            <!-- Logo上传 -->
            <el-form-item label="网站Logo">
              <div class="flex items-center gap-4">
                <el-upload
                  :http-request="handleUploadLogo"
                  :show-file-list="false"
                  accept="image/*"
                >
                  <el-button :loading="uploadingLogo" :icon="UploadFilled">
                    上传Logo
                  </el-button>
                </el-upload>
                <div v-if="settings.site_logo_url" class="flex items-center gap-2">
                  <img 
                    :src="settings.site_logo_url" 
                    alt="Logo预览" 
                    class="w-12 h-12 object-contain rounded border"
                  />
                  <span class="text-xs text-gray-500">当前Logo</span>
                </div>
              </div>
              <div class="text-xs text-gray-400 mt-1">
                建议尺寸：200x200px，支持PNG/JPG格式
              </div>
            </el-form-item>

            <!-- 登录背景上传 -->
            <el-form-item label="登录页背景">
              <div class="flex flex-col gap-2">
                <el-upload
                  :http-request="handleUploadBg"
                  :show-file-list="false"
                  accept="image/*"
                >
                  <el-button :loading="uploadingBg" :icon="Picture">
                    上传背景图
                  </el-button>
                </el-upload>
                <div v-if="settings.login_bg_url" class="mt-2">
                  <img 
                    :src="settings.login_bg_url" 
                    alt="背景预览" 
                    class="w-full h-32 object-cover rounded border"
                  />
                  <span class="text-xs text-gray-500">当前背景图</span>
                </div>
              </div>
              <div class="text-xs text-gray-400 mt-1">
                建议尺寸：1920x1080px或更高，支持JPG/PNG格式
              </div>
            </el-form-item>

            <!-- 默认头像上传 -->
            <el-form-item label="默认用户头像">
              <div class="flex items-center gap-4">
                <el-upload
                  :http-request="handleUploadAvatar"
                  :show-file-list="false"
                  accept="image/*"
                >
                  <el-button :loading="uploadingAvatar" :icon="UploadFilled">
                    上传头像
                  </el-button>
                </el-upload>
                <div v-if="settings.default_avatar_url" class="flex items-center gap-2">
                  <img 
                    :src="settings.default_avatar_url" 
                    alt="头像预览" 
                    class="w-12 h-12 rounded-full object-cover border"
                  />
                  <span class="text-xs text-gray-500">当前默认头像</span>
                </div>
              </div>
              <div class="text-xs text-gray-400 mt-1">
                建议尺寸：200x200px，支持PNG/JPG格式，圆形效果
              </div>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <!-- 预览区域 -->
    <el-card>
      <template #header>
        <div class="font-bold">效果预览</div>
      </template>
      <div class="space-y-4">
        <div class="p-4 bg-gray-50 rounded">
          <div class="text-sm font-medium mb-2">网站标题栏</div>
          <div class="flex items-center gap-3 p-3 bg-white rounded shadow-sm">
            <img 
              v-if="settings.site_logo_url" 
              :src="settings.site_logo_url" 
              alt="Logo" 
              class="w-8 h-8 object-contain"
            />
            <div v-else class="w-8 h-8 bg-gray-200 rounded flex items-center justify-center text-xs">
              Logo
            </div>
            <span class="font-bold text-gray-800">{{ settings.site_name || '网站名称' }}</span>
          </div>
        </div>

        <div class="p-4 bg-gray-50 rounded">
          <div class="text-sm font-medium mb-2">登录页背景</div>
          <div 
            class="h-40 rounded shadow-sm bg-cover bg-center flex items-center justify-center"
            :style="{ backgroundImage: settings.login_bg_url ? `url(${settings.login_bg_url})` : 'none', background: settings.login_bg_url ? undefined : '#0891b2' }"
          >
            <div class="text-white text-2xl font-bold drop-shadow-lg">
              {{ settings.school_name || '学校名称' }}
            </div>
          </div>
        </div>

        <div class="p-4 bg-gray-50 rounded">
          <div class="text-sm font-medium mb-2">默认用户头像</div>
          <div class="flex items-center gap-3">
            <img 
              v-if="settings.default_avatar_url" 
              :src="settings.default_avatar_url" 
              alt="默认头像" 
              class="w-16 h-16 rounded-full object-cover border-2 border-white shadow"
            />
            <div v-else class="w-16 h-16 rounded-full bg-cyan-600 flex items-center justify-center text-white text-xl font-bold">
              用户
            </div>
            <div>
              <div class="text-sm font-medium">示例用户</div>
              <div class="text-xs text-gray-500">未设置头像时显示</div>
            </div>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.el-upload {
  width: 100%;
}
</style>
