/**
 * AI 运营看板 API
 */
import request from '@/utils/request'

export interface AIOverview {
    usage_summary: {
        total_tokens: number
        total_audio_seconds: number
        analysis_count: number
        estimated_cost_rmb: number
    }
    failure_stats: {
        total_triggered: number
        success_count: number
        failed_count: number
        failure_rate: number
    }
    top_users: Array<{
        user_id: number
        name?: string
        student_id?: string
        tokens: number
        audio: number
        count: number
    }>
    daily_trend: Array<{
        date: string
        tokens: number
        audio: number
        count: number
        failed: number
    }>
    range: string
    start_date: string
    end_date: string
}

export interface FailedTask {
    submission_id: number
    task_id: number
    student_id: number
    student_name?: string
    video_path: string
    error_reason: string
    created_at?: string
}

export interface ThresholdSettings {
    daily_token_limit?: number
    daily_audio_seconds_limit?: number
    failure_rate_threshold?: number
}

export interface AuditLog {
    id: number
    action: string
    submission_id: number
    user_id: number
    user_name?: string
    timestamp?: string
    details: any
}

export const aiOpsApi = {
    /**
     * 获取 AI 运营概览
     */
    getOverview: (range: 'day' | 'week' | 'month' = 'week', semesterId?: number): Promise<{ success: boolean; data: AIOverview }> =>
        request.get('/admin/ai-ops/overview', { params: { range, semester_id: semesterId } }),

    /**
     * 获取失败任务列表
     */
    getFailures: (page: number = 1, pageSize: number = 20, semesterId?: number): Promise<{ success: boolean; data: { items: FailedTask[]; total: number } }> =>
        request.get('/admin/ai-ops/failures', { params: { page, page_size: pageSize, semester_id: semesterId } }),

    /**
     * 批量重试失败任务
     */
    retryFailures: (submissionIds: number[]): Promise<{ success: boolean; message: string; data: { results: any[]; success_count: number; total: number } }> =>
        request.post('/admin/ai-ops/retry', { submission_ids: submissionIds }),

    /**
     * 获取审计日志
     */
    getAuditLogs: (page: number = 1, pageSize: number = 50): Promise<{ success: boolean; data: { items: AuditLog[] } }> =>
        request.get('/admin/ai-ops/audit', { params: { page, page_size: pageSize } }),

    /**
     * 获取阈值设置
     */
    getThresholds: (): Promise<{ success: boolean; data: ThresholdSettings }> =>
        request.get('/admin/ai-ops/thresholds'),

    /**
     * 更新阈值设置
     */
    updateThresholds: (settings: ThresholdSettings): Promise<{ success: boolean; message: string }> =>
        request.put('/admin/ai-ops/thresholds', settings),

    /**
     * 获取 AI 服务状态
     */
    getStatus: (): Promise<{ success: boolean; data: { enabled: boolean; provider: string; text_model: string; vision_enabled: boolean; use_cloud_vision: boolean; client_initialized: boolean } }> =>
        request.get('/admin/ai-ops/status'),
}

export default aiOpsApi
