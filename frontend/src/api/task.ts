import request from '@/utils/request'

export interface TaskCreate {
  title: string
  description?: string
  semester_id: number
  deadline?: string
  require_lesson_plan?: boolean
  require_video?: boolean
}

export interface TaskQuery {
  semester_id?: number
  status?: string
}

export const taskApi = {
  list: (params?: TaskQuery) => request.get('/tasks', { params }),
  
  get: (id: number) => request.get(`/tasks/${id}`),
  
  create: (data: TaskCreate) => request.post('/tasks', data),
  
  update: (id: number, data: Partial<TaskCreate>) => request.put(`/tasks/${id}`, data),
  
  delete: (id: number) => request.delete(`/tasks/${id}`),
  
  publish: (id: number) => request.post(`/tasks/${id}/publish`),
}
