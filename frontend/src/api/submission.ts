import request from '@/utils/request'

export interface SubmissionQuery {
  task_id?: number
  status?: 'pending' | 'graded' | 'approved' | 'rejected'
  page?: number
  page_size?: number
}

export interface InstructorReviewQuery {
  semester_id: number
  student_id?: number
  status_filter?: 'pending' | 'graded' | 'approved' | 'rejected'
  page?: number
  page_size?: number
}

export interface ApproveData {
  score?: number
  feedback?: string
}

export interface RejectData {
  reason: string
}

export interface GradeData {
  lesson_plan_score?: number
  video_score?: number
  total_score: number
  feedback?: string
}

export const submissionApi = {
  list: (params?: SubmissionQuery) => request.get('/submissions', { params }),
  
  get: (id: number) => request.get(`/submissions/${id}`),
  
  getMy: () => request.get('/submissions/my'),
  
  getToReview: (params: InstructorReviewQuery) => request.get('/submissions/instructor', { params }),
  
  upload: (formData: FormData, onProgress?: (percent: number) => void) => 
    request.post('/submissions/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e: any) => {
        if (onProgress && e.total) {
          onProgress(Math.round((e.loaded * 100) / e.total))
        }
      }
    }),
  
  // 保存评分（不改变通过状态）
  grade: (id: number, data: GradeData) => request.post(`/submissions/${id}/grade`, data),
  
  // 通过（可选传入评分，也可使用已有评分）
  approve: (id: number, data?: ApproveData) => request.post(`/submissions/${id}/approve`, data || {}),
  
  reject: (id: number, data: RejectData) => request.post(`/submissions/${id}/reject`, data),
}
