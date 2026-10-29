<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Lock, Key } from '@element-plus/icons-vue'
import api from '@/utils/request'

const authStore = useAuthStore()
const router = useRouter()
const loading = ref(false)

const form = reactive({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

const formRef = ref()

const validatePass = (rule: any, value: string, callback: any) => {
  if (value === '') {
    callback(new Error('请输入新密码'))
  } else {
    if (form.confirm_password !== '') {
      if (!formRef.value) return
      formRef.value.validateField('confirm_password')
    }
    callback()
  }
}

const validatePass2 = (rule: any, value: string, callback: any) => {
  if (value === '') {
    callback(new Error('请再次输入新密码'))
  } else if (value !== form.new_password) {
    callback(new Error('两次输入的新密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  old_password: [{ required: true, message: '请输入当前旧密码', trigger: 'blur' }],
  new_password: [
    { required: true, validator: validatePass, trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' }
  ],
  confirm_password: [
    { required: true, validator: validatePass2, trigger: 'blur' }
  ]
}

const handleChangePassword = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid: boolean) => {
    if (valid) {
      loading.value = true
      try {
        await api.post('/auth/change-password', form)
        ElMessage.success('密码修改成功，欢迎进入系统')

        // 刷新当前用户信息，清除默认密码标记
        await authStore.fetchUser()

        // 根据角色直接进入对应首页
        const role = authStore.userRole
        switch (role) {
          case 'admin':
            router.push('/admin/dashboard')
            break
          case 'instructor':
            router.push('/instructor/dashboard')
            break
          case 'student':
            router.push('/student/dashboard')
            break
          default:
            router.push('/')
        }
      } catch (error) {
        // Error handled by interceptor
      } finally {
        loading.value = false
      }
    }
  })
}
</script>

<template>
  <div class="change-pwd-container min-h-screen flex items-center justify-center p-4 bg-slate-900 relative overflow-hidden">
    <!-- 背景氛围光晕 -->
    <div class="absolute top-1/4 left-1/3 w-96 h-96 bg-indigo-500/20 rounded-full blur-3xl pointer-events-none"></div>
    <div class="absolute bottom-1/4 right-1/3 w-96 h-96 bg-cyan-500/15 rounded-full blur-3xl pointer-events-none"></div>

    <div class="w-full max-w-md relative z-10">
      <div class="bg-white/95 backdrop-blur-2xl rounded-3xl p-8 shadow-2xl border border-white/60">
        <!-- 头部图标与标题 -->
        <div class="text-center mb-6">
          <div class="w-14 h-14 mx-auto rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shadow-sm mb-3">
            <el-icon :size="28"><Lock /></el-icon>
          </div>
          <h2 class="text-2xl font-bold text-slate-800 tracking-tight">修改账号密码</h2>
          <p class="text-xs text-slate-500 mt-1.5 leading-relaxed">
            为了保障您的账号与实训数据安全，建议设置强密码
          </p>
        </div>

        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large">
          <el-form-item prop="old_password">
            <template #label>
              <span class="text-xs font-semibold text-slate-600">当前旧密码（初始通常为学工号）</span>
            </template>
            <el-input 
              v-model="form.old_password" 
              type="password" 
              placeholder="请输入当前旧密码"
              :prefix-icon="Key"
              show-password
            />
          </el-form-item>
          
          <el-form-item prop="new_password">
            <template #label>
              <span class="text-xs font-semibold text-slate-600">设定新密码</span>
            </template>
            <el-input 
              v-model="form.new_password" 
              type="password" 
              placeholder="密码长度不低于6位"
              :prefix-icon="Lock"
              show-password
            />
          </el-form-item>
          
          <el-form-item prop="confirm_password" class="mb-6">
            <template #label>
              <span class="text-xs font-semibold text-slate-600">确认新密码</span>
            </template>
            <el-input 
              v-model="form.confirm_password" 
              type="password" 
              placeholder="请再次输入新密码"
              :prefix-icon="Lock"
              show-password
              @keyup.enter="handleChangePassword"
            />
          </el-form-item>

          <el-form-item class="mb-0">
            <el-button 
              type="primary" 
              class="w-full !h-12 !text-base !font-bold !rounded-xl !border-none text-white shadow-lg shadow-indigo-500/25" 
              :loading="loading"
              @click="handleChangePassword"
            >
              确认保存并进入系统
            </el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.change-pwd-container {
  background: radial-gradient(circle at 50% 50%, #1e1b4b 0%, #0f172a 100%);
}
</style>
