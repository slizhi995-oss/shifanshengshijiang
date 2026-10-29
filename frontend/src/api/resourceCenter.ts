import request from '@/utils/request'

export interface AudioSource {
  book_title?: string; edition?: string; volume?: string; chapter_title?: string; parent_title?: string; printed_pages?: string
}
export interface ResourceLesson {
  id: number; textbook_lesson_id?: number; title: string; subject: string; grade: string
  created_at: string; audio_count: number; match_status: string; source: AudioSource
}
export interface LessonAudio {
  resource_id: string; title: string; unit_title: string; series: string; volume: string; stage: string
  section: string; audio_kind: string; printed_page?: number; description: string; textbook_excerpt: string
  available: boolean; audio_content_verified: boolean; reason: string; size_bytes: number
}
export interface AudioLessonDetail extends ResourceLesson { content: string; audios: LessonAudio[] }
export interface AudioLibraryStatus {
  total: number; ready: number; pending_review: number; book_count: number; indexed: boolean
}

export const resourceCenterApi = {
  status: () => request.get('/resources/audio-status') as unknown as Promise<AudioLibraryStatus>,
  list: (params: { keyword?: string; page?: number }) => request.get('/resources/audio-lessons', { params, timeout: 30000 }) as unknown as
    Promise<{ items: ResourceLesson[]; total: number }>,
  detail: (id: number, silent = false) => request.get(`/resources/audio-lessons/${id}`, { silent }) as unknown as Promise<AudioLessonDetail>,
  resolve: (id: number, silent = false) => request.get(`/resources/audio-lessons/by-textbook/${id}`, { silent }) as unknown as Promise<ResourceLesson>,
  rematch: (id: number) => request.post(`/resources/audio-lessons/${id}/rematch`) as unknown as Promise<AudioLessonDetail>,
  file: (lessonId: number, resourceId: string) => request.get(
    `/resources/audio-lessons/${lessonId}/audio/${encodeURIComponent(resourceId)}/file`,
    { responseType: 'blob', timeout: 60000 }) as unknown as Promise<Blob>,
}
