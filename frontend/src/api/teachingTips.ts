import request from '@/utils/request'

export interface TeachingTip {
  id: number; bvid: string; page: number; url: string; title: string; category: string
  description: string; cover_url: string; sort_order: number; is_published: boolean
}
export type TeachingTipInput = Omit<TeachingTip, 'id' | 'bvid' | 'page'>
export const teachingTipsApi = {
  list: () => request.get('/resources/teaching-tips') as unknown as Promise<{ items: TeachingTip[] }>,
  coverMetadata: (id: number) => request.get(`/resources/teaching-tips/${id}/metadata`) as unknown as
    Promise<{ cover_url: string }>,
  admin: () => request.get('/admin/teaching-tips') as unknown as Promise<{ items: TeachingTip[] }>,
  metadata: (url: string) => request.post('/admin/teaching-tips/metadata', { url }) as unknown as
    Promise<{ title: string; cover_url: string; availability: string }>,
  uploadCover: (file: File) => {
    const body = new FormData()
    body.append('file', file)
    return request.post('/admin/teaching-tips/covers', body) as unknown as Promise<{ cover_url: string }>
  },
  create: (body: TeachingTipInput) => request.post('/admin/teaching-tips', body),
  update: (id: number, body: TeachingTipInput) => request.put(`/admin/teaching-tips/${id}`, body),
  remove: (id: number) => request.delete(`/admin/teaching-tips/${id}`),
}
