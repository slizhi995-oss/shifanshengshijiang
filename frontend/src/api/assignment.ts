import request from '@/utils/request'

export interface BatchAssignParams {
  semester_id: number
  instructor_id: number
  student_ids: number[]
}

export const assignmentApi = {
  getMyStudents: (semesterId: number) => 
    request.get(`/assignments/instructor/${semesterId}`),
  
  getMyInstructor: (semesterId: number) => 
    request.get(`/assignments/student/my-instructor/${semesterId}`),
  
  getUnassigned: (semesterId: number) => 
    request.get(`/assignments/unassigned/${semesterId}`),
  
  getOverview: (semesterId: number) => 
    request.get(`/assignments/overview/${semesterId}`),
  
  batchAssign: (data: BatchAssignParams) => request.post('/assignments/batch', data),
  
  unassign: (semesterId: number, studentId: number) => 
    request.delete(`/assignments/${semesterId}/${studentId}`),
}
