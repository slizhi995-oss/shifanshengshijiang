import request from '@/utils/request'

export type ResourceType = 'video' | 'animation' | 'interactive' | 'article' | 'document' | 'webpage'
export const resourceTypeLabels: Record<ResourceType, string> = {
  video: '视频', animation: '动画', interactive: '交互演示', article: '图文资料', document: '文档', webpage: '网页资料',
}
export function isBilibiliVideo(item: LessonVideo) {
  try {
    const url = new URL(item.url)
    const match = url.pathname.match(/^\/video\/(BV[0-9A-Za-z]{10})\/?$/)
    const page = Number(url.searchParams.get('p') || 1)
    return ['http:', 'https:'].includes(url.protocol) && ['www.bilibili.com', 'bilibili.com', 'm.bilibili.com'].includes(url.hostname)
      && !url.username && !url.password && ['', '80', '443'].includes(url.port) && !!match
      && match[1] === item.bvid && Number.isInteger(page) && page >= 1 && page <= 1000
  } catch { return false }
}
export interface VideoNeed {
  id: string; section: string; purpose: string; keywords: string[]; method: 'ai' | 'text' | 'manual'
  textbook?: { book_title: string; edition: string; volume: string; chapter_title: string; printed_pages: string }
  source_excerpt?: string; required_content?: string; essential_terms?: string[]
  status?: 'matched' | 'searching' | 'pending'; match_count?: number
  supplement_count?: number
}
export interface LessonVideo {
  id: string | number; bvid: string; page: number; title: string; section: string; purpose: string
  url: string; embed_url: string; source?: string; snippet?: string; reason?: string
  ranking?: 'ai' | 'search'; content_verified?: boolean
  cover_url?: string
  site_name?: string; resource_type?: ResourceType
  match_type?: 'direct' | 'reference' | 'candidate'; evidence_quote?: string; score?: number
  need_id?: string; source_excerpt?: string; required_content?: string
}
export interface VideoSearchState {
  lesson_id: number; configured: boolean; status: string; message: string; query: string
  needs: VideoNeed[]; items: LessonVideo[]; selected: LessonVideo[]; searched_at: string | null
  stale: boolean; fallback_url: string; next_search_at: string | null
}
export const lessonVideosApi = {
  metadata: (lessonId: number, bvid: string) => request.get(
    `/resources/audio-lessons/${lessonId}/videos/${encodeURIComponent(bvid)}/metadata`, { timeout: 8000, silent: true }) as unknown as
    Promise<{ availability: 'available' | 'unavailable' | 'unknown'; cover_url: string; title: string }>,
  get: (id: number, silent = false) => request.get(`/resources/audio-lessons/${id}/videos`, { silent }) as unknown as Promise<VideoSearchState>,
  search: (id: number, query = '', force = false, silent = false) => request.post(
    `/resources/audio-lessons/${id}/videos/search`, { query, force }, { silent }) as unknown as Promise<VideoSearchState>,
  add: (id: number, body: { candidate_id?: string; url?: string; title?: string; section?: string; purpose?: string; resource_type?: ResourceType }) =>
    request.post(`/resources/audio-lessons/${id}/videos`, body) as unknown as Promise<VideoSearchState>,
  remove: (id: number, videoId: number | string) => request.delete(
    `/resources/audio-lessons/${id}/videos/${encodeURIComponent(videoId)}`) as unknown as Promise<VideoSearchState>,
}
