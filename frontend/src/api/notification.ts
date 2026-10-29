/**
 * 通知 API
 */
import api from '@/utils/request'

export interface Notification {
    id: number
    type: 'system' | 'task' | 'grade' | 'message' | 'comment'
    title: string
    content: string
    is_read: boolean
    created_at: string
    link?: string
}

export const notificationApi = {
    /**
     * 获取通知列表
     */
    list(params?: { page?: number; page_size?: number; type?: string; unread_only?: boolean }) {
        return api.get<{ success: boolean; data: { items: Notification[]; total: number } }>(
            '/notifications',
            { params }
        )
    },

    /**
     * 获取未读数量
     */
    getUnreadCount() {
        return api.get<{ success: boolean; data: { count: number } }>('/notifications/unread-count')
    },

    /**
     * 标记已读
     */
    markAsRead(notificationId: number) {
        return api.put<{ success: boolean }>(`/notifications/${notificationId}/read`)
    },

    /**
     * 批量标记已读
     */
    batchMarkAsRead(ids: number[]) {
        return api.put<{ success: boolean }>('/notifications/batch-read', { ids })
    },

    /**
     * 全部已读
     */
    markAllAsRead() {
        return api.put<{ success: boolean }>('/notifications/read-all')
    },

    /**
     * 删除通知
     */
    delete(notificationId: number) {
        return api.delete<{ success: boolean }>(`/notifications/${notificationId}`)
    }
}

export default notificationApi
