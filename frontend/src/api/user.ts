import request from '@/utils/request'

export interface UserQuery {
  page?: number
  page_size?: number
  role?: string
  keyword?: string
}

export interface UserCreate {
  user_code: string
  name: string
  role: 'admin' | 'instructor' | 'student'
  email?: string
  phone?: string
}

export const userApi = {
  list: (params?: UserQuery) => request.get('/users', { params }),
  
  get: (id: number) => request.get(`/users/${id}`),
  
  getByRole: (role: string) => request.get(`/users/role/${role}`),
  
  create: (data: UserCreate) => request.post('/users', data),
  
  update: (id: number, data: Partial<UserCreate>) => request.put(`/users/${id}`, data),
  
  delete: (id: number) => request.delete(`/users/${id}`),
  
  resetPassword: (id: number) => request.post(`/users/${id}/reset-password`),
  
  toggleActive: (id: number) => request.post(`/users/${id}/toggle-active`),
  
  importExcel: (formData: FormData) => request.post('/users/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  
  downloadTemplate: () => request.get('/users/import-template', { responseType: 'blob' }),
}
