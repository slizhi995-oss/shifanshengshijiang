import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/request'
import router from '@/router'

export interface User {
  id: number
  user_code: string
  name: string
  role: 'admin' | 'instructor' | 'student'
  is_super_admin?: boolean // 是否为超级管理员
  is_default_password: boolean
  avatar?: string
  college?: string | null
  major?: string | null
  class_name?: string | null
  head_teacher?: string | null
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref<User | null>(JSON.parse(localStorage.getItem('user') || 'null'))
  
  const isAuthenticated = computed(() => !!token.value)
  const isDefaultPassword = computed(() => user.value?.is_default_password || false)
  const userRole = computed(() => user.value?.role)

  function setToken(newToken: string) {
    token.value = newToken
    localStorage.setItem('token', newToken)
  }

  function setUser(newUser: User) {
    user.value = newUser
    localStorage.setItem('user', JSON.stringify(newUser))
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    router.push('/login')
  }

  async function login(loginData: any) {
    try {
      const res: any = await api.post('/auth/login', loginData)
      setToken(res.access_token)
      setUser(res.user)
      
      if (res.is_default_password) {
        ElMessage.warning('首次登录，请修改密码')
        router.push('/change-password')
      } else {
        ElMessage.success('登录成功')
        // Redirect based on role
        switch (res.user.role) {
          case 'admin':
            router.push('/admin/dashboard')
            break
          case 'instructor':
            router.push('/instructor/dashboard')
            break
          case 'student':
            router.push('/student/dashboard')
            break
        }
      }
      return true
    } catch (error) {
      return false
    }
  }

  async function fetchUser() {
    try {
      const res: any = await api.get('/auth/me')
      setUser(res)
    } catch (error) {
      logout()
    }
  }

  return {
    token,
    user,
    isAuthenticated,
    isDefaultPassword,
    userRole,
    login,
    logout,
    fetchUser,
    setUser
  }
})
