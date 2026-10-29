import request from '@/utils/request'

export interface Textbook {
  stage?: string; display_title?: string
  id: number; title: string; subject: string; grade: string; edition: string; volume: string
  publisher: string; page_count: number; original_filename: string; status: string; is_published: boolean
}
export interface Chapter {
  directory_layout?: 'flat' | 'sections'
  display_title?: string
  unit_title?: string; section_title?: string; is_unit?: boolean; is_nested?: boolean
  id: number; book_id: number; title: string; parent_title: string; start_page: number; end_page: number
  printed_pages: string; is_published: boolean; content?: string; score?: number; book_title?: string
}
export interface TextbookAsset {
  asset_id: string; book_id: number; chapter_id: number | null; title: string; pdf_page: number
  figure_number: string; description: string; tags: string[]; conditions: string
  width: number; height: number; is_reviewed: boolean
}
type Envelope<T> = { success: boolean; data: T }
const get = <T>(url: string, params = {}) => request.get(url, { params }) as unknown as Promise<Envelope<T>>

export const textbookApi = {
  books: (params = {}) => get<Textbook[]>('/textbooks', params),
  upload: (body: FormData) => request.post('/textbooks', body, { timeout: 180000 }) as unknown as Promise<Envelope<Textbook>>,
  saveBook: (id: number, body: object) => request.patch(`/textbooks/${id}`, body) as unknown as Promise<Envelope<Textbook>>,
  chapters: (book: number) => get<Chapter[]>(`/textbooks/${book}/chapters`),
  chapter: (id: number) => get<Chapter>(`/textbooks/chapters/${id}`),
  createChapter: (book: number, body: object) => request.post(`/textbooks/${book}/chapters`, body) as unknown as Promise<Envelope<Chapter>>,
  saveChapter: (id: number, body: object) => request.put(`/textbooks/chapters/${id}`, body) as unknown as Promise<Envelope<Chapter>>,
  assets: (book: number, start_page?: number, end_page?: number) => get<TextbookAsset[]>(`/textbooks/${book}/assets`, { start_page, end_page }),
  uploadAsset: (book: number, body: FormData) => request.post(`/textbooks/${book}/assets`, body) as unknown as Promise<Envelope<TextbookAsset>>,
  saveAsset: (asset: TextbookAsset) => request.patch(`/textbooks/assets/${asset.asset_id}`, asset) as unknown as Promise<Envelope<TextbookAsset>>,
  recommend: (subject: string, grade: string, topic: string, book_id?: number) => get<Chapter[]>('/textbooks/recommend', { subject, grade, topic, book_id }),
  image: (id: string) => request.get(`/textbooks/assets/${id}/image`, { responseType: 'blob' }) as unknown as Promise<Blob>,
  pdf: (id: number) => request.get(`/textbooks/${id}/pdf`, { responseType: 'blob' }) as unknown as Promise<Blob>,
  page: (book: number, page: number) => get<{ content: string }>(`/textbooks/${book}/pages/${page}`),
  bundle: (id: number) => request.get(`/textbooks/lessons/${id}/bundle`, { responseType: 'blob' }) as unknown as Promise<Blob>,
}

export const materialImagePattern = /!\[([^\]\n]{1,240})\]\(\/api\/v1\/textbooks\/assets\/(tb-[a-f0-9]{32})\/image\)/g
