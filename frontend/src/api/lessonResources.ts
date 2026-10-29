import request from '@/utils/request'

export interface LessonSource {
  book_id: number | null; chapter_id: number | null; book_title: string; edition: string; volume: string
  chapter_title: string; start_page: number; end_page: number; printed_pages: string; available: boolean
}
export interface LessonResourceSummary {
  id: number; title: string; subject: string; grade: string; created_at: string
  source: LessonSource; image_count: number; pending_count: number
}
export interface LessonMaterial {
  asset_id: string; title: string; available: boolean; figure_number: string; pdf_page: number | null
  description: string; conditions: string; usages: { section: string; caption: string; excerpt: string }[]
}
export interface LessonResources extends LessonResourceSummary {
  content: string; materials: LessonMaterial[]
  pending: { kind: 'image' | 'video'; section: string; description: string }[]
}
export const lessonResourcesApi = {
  list: (params: { keyword?: string; page?: number }) => request.get('/resources/lessons', { params }) as unknown as
    Promise<{ items: LessonResourceSummary[]; total: number }>,
  detail: (id: number) => request.get(`/resources/lessons/${id}`) as unknown as Promise<LessonResources>,
}
