import request from '@/utils/request'

export interface SendMessageParams {
  receiver_id: number
  content: string
}

export const messageApi = {
  getContacts: () => request.get('/messages/contacts'),
  
  getConversation: (userId: number) => request.get(`/messages/conversation/${userId}`),
  
  send: (data: SendMessageParams) => request.post('/messages', data),
  
  markRead: (id: number) => request.post(`/messages/${id}/read`),
  
  getUnreadCount: () => request.get('/messages/unread-count'),
}
