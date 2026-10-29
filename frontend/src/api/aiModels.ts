/**
 * AI 模型配置 API
 */
import request from '@/utils/request'

export interface AIModelConfig {
    id: number
    name: string
    provider: string
    model_id: string
    api_base_url?: string
    model_type: 'text' | 'audio' | 'vision'
    is_enabled: boolean
    is_default: boolean
    priority: number
    max_tokens: number
    temperature: number
    price_per_1k_tokens: number
    description?: string
    remark?: string
    api_key_masked?: string
    api_key?: string
    monthly_quota?: number
    created_at?: string
    updated_at?: string
}

export interface AIModelUsageLogItem {
    id: number
    model_config_id: number
    model_name: string
    user_id: number
    username: string
    usage_type: string
    input_tokens: number
    output_tokens: number
    total_tokens: number
    audio_seconds: number
    latency_ms: number
    estimated_cost: number
    is_success: boolean
    error_message?: string
    created_at: string
}

export interface AIModelConfigCreate {
    name: string
    provider: string
    model_id: string
    api_key: string
    api_base_url?: string
    model_type?: string
    is_enabled?: boolean
    is_default?: boolean
    priority?: number
    max_tokens?: number
    temperature?: number
    price_per_1k_tokens?: number
    description?: string
    remark?: string
    monthly_quota?: number
}

export interface AIModelConfigUpdate {
    name?: string
    provider?: string
    model_id?: string
    api_key?: string
    api_base_url?: string
    model_type?: string
    is_enabled?: boolean
    is_default?: boolean
    priority?: number
    max_tokens?: number
    temperature?: number
    price_per_1k_tokens?: number
    description?: string
    remark?: string
    monthly_quota?: number
}

export const aiModelApi = {
    // 获取所有模型配置（管理员）
    getModels: (params?: { model_type?: string; include_disabled?: boolean }) =>
        request.get<{ success: boolean; data: { items: AIModelConfig[]; total: number } }>(
            '/admin/ai-models/models',
            { params }
        ),

    // 获取单个模型详情（管理员可看完整 API Key）
    getModel: (modelId: number) =>
        request.get<{ success: boolean; data: AIModelConfig }>(`/admin/ai-models/models/${modelId}`),

    // 添加模型配置
    createModel: (data: AIModelConfigCreate) =>
        request.post<{ success: boolean; message: string; data: { id: number; name: string } }>(
            '/admin/ai-models/models',
            data
        ),

    // 更新模型配置
    updateModel: (modelId: number, data: AIModelConfigUpdate) =>
        request.put<{ success: boolean; message: string }>(`/admin/ai-models/models/${modelId}`, data),

    // 删除模型配置
    deleteModel: (modelId: number) =>
        request.delete<{ success: boolean; message: string }>(`/admin/ai-models/models/${modelId}`),

    // 设置为默认模型
    setDefaultModel: (modelId: number) =>
        request.post<{ success: boolean; message: string }>(`/admin/ai-models/models/${modelId}/set-default`),

    // 启用/禁用模型
    toggleModel: (modelId: number) =>
        request.post<{ success: boolean; message: string; data: { is_enabled: boolean } }>(
            `/admin/ai-models/models/${modelId}/toggle`
        ),

    // 测试模型连接
    testConnection: (data: AIModelConfigCreate) =>
        request.post<{ success: boolean; message: string; data?: any }>(
            '/admin/ai-models/models/test-connection',
            data,
            { timeout: 120000 }
        ),

    // 获取可用模型列表（用户端）
    getAvailableModels: (modelType?: string) =>
        request.get<{ success: boolean; data: { items: AIModelConfig[]; total: number } }>(
            '/admin/ai-models/available-models',
            { params: { model_type: modelType } }
        ),

    // 获取模型使用统计
    getUsageStats: (params?: { range?: string; model_id?: number }) =>
        request.get<{ success: boolean; data: any }>('/admin/ai-models/usage-stats', { params }),

    // 查询模型 API 账户余额
    checkBalance: (modelId: number) =>
        request.get<{ success: boolean; data: any }>(`/admin/ai-models/models/${modelId}/balance`),

    // 获取详细调用日志
    getUsageLogs: (params?: {
        model_id?: number
        usage_type?: string
        is_success?: boolean
        range?: string
        page?: number
        page_size?: number
    }) =>
        request.get<{ success: boolean; data: { items: AIModelUsageLogItem[]; total: number; page: number; page_size: number } }>(
            '/admin/ai-models/usage-logs',
            { params }
        ),
}

export default aiModelApi
