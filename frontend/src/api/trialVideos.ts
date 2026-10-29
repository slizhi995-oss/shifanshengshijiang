import api from '@/utils/request'

export interface TrialVideo {
  id: number
  title: string
  subject: string
  description: string
  author: string
  college?: string
  can_delete?: boolean
  presenter_type: 'student' | 'teacher'
  source: 'student' | 'example'
  created_at: string
  published_at: string | null
  is_public?: boolean
  semester_id?: number | null
  original_name?: string
  file_size?: number
  file_status?: string
  available?: boolean
  expires_at?: string | null
  blocked?: boolean
  moderation_reason?: string
  analysis_status?: string
}

export interface VideoOptions {
  subjects: string[]
  semesters: { id: number; name: string; instructor_name: string | null }[]
  max_bytes: number
  user_max_bytes: number
  used_bytes: number
  private_days: number
}

export interface VideoPage {
  items: TrialVideo[]
  total: number
  used_bytes?: number
  total_bytes?: number
}

export interface VideoAnalysis {
  status: string
  analysis: Record<string, any> | null
  error: string
}

export interface TrialVideoComment {
  id: number
  content: string
  author_name: string
  author_avatar: string
  author_role: 'student' | 'instructor' | 'admin'
  is_video_author: boolean
  created_at: string
  can_delete: boolean
  parent_id: number | null
  reply_count: number
  is_deleted: boolean
}

export interface VideoCommentPage {
  items: TrialVideoComment[]
  total: number
  comment_count: number
}

export const trialVideosApi = {
  detail: (id: number): Promise<TrialVideo> => api.get(`/trial-videos/${id}`),
  commentContext: (id: number, commentId: number): Promise<{ root_page: number; thread: TrialVideoComment[] }> =>
    api.get(`/trial-videos/${id}/comments/${commentId}/context`),
  options: (): Promise<VideoOptions> => api.get('/trial-videos/upload-options'),
  evaluate: (file: File, progress: (percent: number) => void): Promise<{ task_id: string; status: string }> => {
    const data = new FormData()
    data.append('video', file)
    return api.post('/video-analysis/upload-analyze', data, {
      timeout: 1800000,
      onUploadProgress: event => progress(event.total ? Math.round(event.loaded * 100 / event.total) : 0),
    })
  },
  evaluation: (taskId: string): Promise<VideoAnalysis> => api.get(`/video-analysis/standalone/${taskId}`),
  cover: (id: number): Promise<Blob> => api.get(`/trial-videos/${id}/cover`, { responseType: 'blob', timeout: 30000 }),
  upload: (data: FormData, progress: (percent: number) => void): Promise<TrialVideo> =>
    api.post('/trial-videos/upload', data, {
      timeout: 1800000,
      onUploadProgress: event => progress(event.total ? Math.round(event.loaded * 100 / event.total) : 0),
    }),
  publicList: (source: string, page = 1): Promise<VideoPage> =>
    api.get('/trial-videos/public', { params: { source, page, page_size: 100 } }),
  mine: (page = 1): Promise<VideoPage> => api.get('/trial-videos/mine', { params: { page } }),
  instructor: (page = 1): Promise<VideoPage> => api.get('/trial-videos/instructor', { params: { page } }),
  admin: (source: string, page = 1): Promise<VideoPage> =>
    api.get('/trial-videos/admin', { params: { source, page } }),
  update: (id: number, data: Record<string, unknown>): Promise<TrialVideo> => api.patch(`/trial-videos/${id}`, data),
  remove: (id: number) => api.delete(`/trial-videos/${id}`),
  takedown: (id: number, reason: string) => api.post(`/trial-videos/${id}/takedown`, { reason }),
  playback: (id: number): Promise<{ url: string }> => api.post(`/trial-videos/${id}/playback`),
  analysis: (id: number): Promise<VideoAnalysis> => api.get(`/trial-videos/${id}/analysis`),
  comments: (id: number, page = 1, parentId?: number, pageSize = 20): Promise<VideoCommentPage> =>
    api.get(`/trial-videos/${id}/comments`, { params: { page, page_size: pageSize, parent_id: parentId } }),
  addComment: (id: number, content: string, parentId?: number): Promise<TrialVideoComment> =>
    api.post(`/trial-videos/${id}/comments`, { content, ...(parentId !== undefined ? { parent_id: parentId } : {}) }),
  removeComment: (id: number, commentId: number) => api.delete(`/trial-videos/${id}/comments/${commentId}`),
}

export function videoDate(value?: string | null) {
  if (!value) return '—'
  return new Date(value.endsWith('Z') || /[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`)
    .toLocaleString('zh-CN', { hour12: false })
}

export function videoSize(value = 0) {
  return value >= 1024 ** 3 ? `${(value / 1024 ** 3).toFixed(2)} GB` : `${(value / 1024 ** 2).toFixed(1)} MB`
}
