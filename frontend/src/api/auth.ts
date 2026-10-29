import request from '@/utils/request'

export interface LoginParams {
  user_code: string
  password: string
}

export interface ChangePasswordParams {
  old_password: string
  new_password: string
  confirm_password: string
}

export const authApi = {
  login: (data: LoginParams) => request.post('/auth/login', data),
  
  changePassword: (data: ChangePasswordParams) => 
    request.post('/auth/change-password', data),
  
  me: () => request.get('/auth/me'),
  
  refresh: () => request.post('/auth/refresh'),
}
