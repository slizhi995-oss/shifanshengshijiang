/**
 * 评分规则 API
 */
import api from '@/utils/request'

export interface DimensionConfig {
    name: string
    key: string
    weight: number
    description: string
}

export interface GradeLevelConfig {
    min_score: number
    max_score: number
    label: string
    description: string
}

export interface GradingRubric {
    id: number
    name: string
    description?: string
    semester_id?: number
    lesson_plan_weight: number
    video_weight: number
    lesson_plan_dimensions?: DimensionConfig[]
    video_dimensions?: DimensionConfig[]
    grade_levels?: GradeLevelConfig[]
    is_default: boolean
    is_active: boolean
    created_at?: string
    updated_at?: string
}

export interface CreateRubricRequest {
    name: string
    description?: string
    semester_id?: number
    lesson_plan_weight: number
    video_weight: number
    lesson_plan_dimensions?: DimensionConfig[]
    video_dimensions?: DimensionConfig[]
    grade_levels?: GradeLevelConfig[]
    is_default?: boolean
}

export interface UpdateRubricRequest extends Partial<CreateRubricRequest> {
    is_active?: boolean
}

export interface ApplyRubricResult {
    rubric_id: number
    rubric_name: string
    submission_id: number
    lesson_plan_score: number
    video_score: number
    total_score: number
    grade_label: string
    weights: {
        lesson_plan: number
        video: number
    }
    lesson_plan_details: Array<{
        dimension: string
        key: string
        weight: number
        score: number
        weighted_score: number
    }>
}

export interface DefaultDimensions {
    lesson_plan_dimensions: DimensionConfig[]
    video_dimensions: DimensionConfig[]
    grade_levels: GradeLevelConfig[]
}

export const rubricApi = {
    /**
     * 获取评分规则列表
     */
    list(semesterId?: number, includeGlobal = true) {
        return api.get<{ success: boolean; data: { items: GradingRubric[] } }>('/rubrics', {
            params: { semester_id: semesterId, include_global: includeGlobal }
        })
    },

    /**
     * 获取默认维度配置
     */
    getDefaults() {
        return api.get<{ success: boolean; data: DefaultDimensions }>('/rubrics/defaults')
    },

    /**
     * 创建评分规则
     */
    create(data: CreateRubricRequest) {
        return api.post<{ success: boolean; data: { id: number; name: string } }>('/rubrics', data)
    },

    /**
     * 获取评分规则详情
     */
    get(rubricId: number) {
        return api.get<{ success: boolean; data: GradingRubric }>(`/rubrics/${rubricId}`)
    },

    /**
     * 更新评分规则
     */
    update(rubricId: number, data: UpdateRubricRequest) {
        return api.put<{ success: boolean }>(`/rubrics/${rubricId}`, data)
    },

    /**
     * 删除评分规则
     */
    delete(rubricId: number) {
        return api.delete<{ success: boolean }>(`/rubrics/${rubricId}`)
    },

    /**
     * 应用规则计算分数
     */
    apply(rubricId: number, submissionId: number) {
        return api.post<{ success: boolean; data: ApplyRubricResult }>(
            `/rubrics/${rubricId}/apply`,
            null,
            { params: { submission_id: submissionId } }
        )
    }
}

export default rubricApi
