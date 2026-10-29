import request from '@/utils/request'

export interface MonitorQuery {
  instructor_id?: number
  page?: number
  page_size?: number
}

export const adminApi = {
  getDashboard: () => request.get('/admin/dashboard'),
  
  getMonitor: (semesterId: number, params?: MonitorQuery) => 
    request.get(`/admin/monitor/${semesterId}`, { params }),
  
  getInstructors: (semesterId: number) => 
    request.get(`/admin/instructors/${semesterId}`),
  
  exportData: (semesterId: number) => 
    request.get(`/admin/export/${semesterId}`, { responseType: 'blob' }),
}
