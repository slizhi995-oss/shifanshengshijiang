import request from '@/utils/request'

export interface SemesterCreate {
  name: string
  description?: string
  start_date?: string
  end_date?: string
}

export const semesterApi = {
  list: () => request.get('/semesters'),
  
  get: (id: number) => request.get(`/semesters/${id}`),
  
  getActive: () => request.get('/semesters/active'),
  
  create: (data: SemesterCreate) => request.post('/semesters', data),
  
  update: (id: number, data: Partial<SemesterCreate>) => request.put(`/semesters/${id}`, data),
  
  delete: (id: number) => request.delete(`/semesters/${id}`),
  
  start: (id: number) => request.post(`/semesters/${id}/start`),
  
  end: (id: number) => request.post(`/semesters/${id}/end`),
}
