/**
 * 练习会话 API
 */
import api from '@/utils/request'

export interface PracticeMessage {
    role: 'user' | 'assistant'
    content: string
    timestamp?: string
}

export interface PracticeSession {
    id: number
    student_id: number
    semester_id?: number
    session_type: string
    topic?: string
    messages: PracticeMessage[]
    report?: {
        strengths: string[]
        weaknesses: string[]
        suggestions: string[]
        score?: number
    }
    status: 'active' | 'completed' | 'archived'
    created_at: string
    updated_at: string
}

export interface CreateSessionRequest {
    semester_id?: number
    session_type: string
    topic?: string
}

export const practiceApi = {
    /**
     * 创建会话
     */
    createSession(data: CreateSessionRequest) {
        return api.post<{ success: boolean; data: { session_id: number } }>('/practice-sessions', data)
    },

    /**
     * 获取会话列表
     */
    listSessions(params?: { page?: number; page_size?: number; status?: string }) {
        return api.get<{ success: boolean; data: { items: PracticeSession[]; total: number } }>(
            '/practice-sessions',
            { params }
        )
    },

    /**
     * 获取会话详情
     */
    getSession(sessionId: number) {
        return api.get<{ success: boolean; data: PracticeSession }>(`/practice-sessions/${sessionId}`)
    },

    /**
     * 保存消息
     */
    saveMessage(sessionId: number, message: PracticeMessage) {
        return api.post<{ success: boolean }>(`/practice-sessions/${sessionId}/messages`, message)
    },

    /**
     * 生成报告
     */
    generateReport(sessionId: number) {
        return api.post<{ success: boolean; data: PracticeSession['report'] }>(
            `/practice-sessions/${sessionId}/report`
        )
    },

    /**
     * 完成会话
     */
    completeSession(sessionId: number) {
        return api.put<{ success: boolean }>(`/practice-sessions/${sessionId}`, { status: 'completed' })
    },

    /**
     * 删除会话
     */
    deleteSession(sessionId: number) {
        return api.delete<{ success: boolean }>(`/practice-sessions/${sessionId}`)
    }
}

export default practiceApi
