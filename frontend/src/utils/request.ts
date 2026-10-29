import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

declare module 'axios' {
  interface AxiosRequestConfig {
    silent?: boolean
  }
}

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
})

// Request Interceptor
api.interceptors.request.use(
  (config) => {
    const authStore = useAuthStore()
    if (authStore.token) {
      config.headers.Authorization = `Bearer ${authStore.token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response Interceptor
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    const { response } = error
    if (error.config?.silent && response?.status !== 401) return Promise.reject(error)
    if (response) {
      switch (response.status) {
        case 401: {
          // Unauthorized
          const url = response.config?.url || ''
          if (url.includes('/auth/login')) {
            const detail = response.data?.detail || '用户名或密码错误'
            ElMessage.error(detail)
          } else {
            const authStore = useAuthStore()
            authStore.logout()
            router.push('/login')
            ElMessage.error('登录已过期，请重新登录')
          }
          break
        }
        case 403: {
          // 某些 403 是因为切换账号后残留请求，不需要弹错误
          const forbiddenUrl = response.config?.url || ''
          const silentForbiddenPrefixes = ['/admin/', '/instructor/class-insights']
          const authStoreFor403 = useAuthStore()
          const currentRole = authStoreFor403.userRole
          const isAdminRoute = silentForbiddenPrefixes.some(p => forbiddenUrl.includes(p))
          // 仅当用户确实在使用对应角色页面时才提示
          if (isAdminRoute && currentRole !== 'admin') {
            // 学生/教师访问管理员接口 - 静默处理（切换账号残留请求）
            console.warn('[403] 非管理员访问管理端接口，已静默处理:', forbiddenUrl)
          } else {
            ElMessage.error('权限不足')
          }
          break
        }
        case 404: {
          // 某些 404 是预期的业务逻辑（如学生未分配导师），不需要弹出错误
          const url = response.config?.url || ''
          const silentUrls = ['/assignments/student/my-instructor/', '/assignments/instructor/']
          const isSilent = silentUrls.some(u => url.includes(u))
          if (!isSilent) {
            ElMessage.error('请求的资源不存在')
          }
          break
        }
        case 422: {
          // Validation Error - Pydantic格式
          const detail = response.data?.detail
          let message = '数据验证失败'

          if (typeof detail === 'string') {
            message = detail
          } else if (Array.isArray(detail)) {
            // Pydantic返回的错误数组格式
            message = detail
              .map((err: any) => {
                // 尝试提取中文错误消息
                if (err.msg) return err.msg
                if (err.message) return err.message
                // 如果是ValueError等Python异常，从ctx中提取
                if (err.ctx && err.ctx.error) {
                  const errorStr = err.ctx.error.toString()
                  // 提取ValueError中的中文消息
                  const match = errorStr.match(/ValueError\(['"](.+)['"]\)/)
                  if (match) return match[1]
                  return errorStr
                }
                // 字段名 + 错误类型
                const field = err.loc ? err.loc.join('.') : '未知字段'
                return `${field}: ${err.type || '验证错误'}`
              })
              .join('；')
          } else if (detail && typeof detail === 'object') {
            message = (detail as any).msg || (detail as any).message || JSON.stringify(detail)
          }

          ElMessage.error(message)
          break
        }
        case 500:
          ElMessage.error('服务器内部错误')
          break
        default: {
          const detail = response.data?.detail
          let message = '发生错误'

          if (typeof detail === 'string') {
            message = detail
          } else if (Array.isArray(detail)) {
            message = detail
              .map((d: any) => d.msg || d.message || JSON.stringify(d))
              .join('；')
          } else if (detail && typeof detail === 'object') {
            message = (detail as any).msg || (detail as any).message || JSON.stringify(detail)
          }

          ElMessage.error(message)
        }
      }
    } else {
      ElMessage.error('网络连接失败')
    }
    return Promise.reject(error)
  }
)

export default api
