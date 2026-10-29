/**
 * 成长画像 API
 */
import api from '@/utils/request'

export interface RadarDimension {
    dimension: string
    label: string
    score: number
    category: 'lesson_plan' | 'video'
}

export interface TrendData {
    date: string
    overall_score: number
    lesson_plan_score?: number
    video_score?: number
    task_title?: string
}

export interface ActionItem {
    priority: number
    dimension: string
    current_score: number
    suggestion: string
}

export interface ProfileData {
    radar: RadarDimension[]
    trend: TrendData[]
    action_items: ActionItem[]
    overall_score: number
    stats: {
        total_submissions: number
        approved_submissions: number
        average_score: number
    }
}

export interface StudentProfileSummary {
    student_id: number
    name: string
    student_code: string
    overall_score: number
    total_submissions: number
    approved_submissions: number
    last_updated?: string
}

export interface ClassOverview {
    total_students: number
    avg_score: number
    completed_rate: number
    score_distribution: {
        excellent: number
        good: number
        average: number
        pass: number
        fail: number
    }
    dimension_averages: RadarDimension[]
}

export const profileApi = {
    /**
     * 获取当前学生的成长画像
     */
    getMyProfile(semesterId?: number) {
        const params = semesterId ? { semester_id: semesterId } : {}
        return api.get<ProfileData>('/profile/me', { params })
    },

    /**
     * 获取指定学生的成长画像 (老师/管理员)
     */
    getStudentProfile(studentId: number, semesterId?: number) {
        const params = semesterId ? { semester_id: semesterId } : {}
        return api.get<ProfileData>(`/profile/students/${studentId}`, { params })
    },

    /**
     * 获取班级概览 (老师)
     */
    getClassOverview(semesterId: number) {
        return api.get<ClassOverview>('/profile/overview', { params: { semester_id: semesterId } })
    },

    /**
     * 获取学生列表带画像摘要 (老师)
     */
    getStudentsWithProfile(semesterId: number, page = 1, pageSize = 20) {
        return api.get<{ items: StudentProfileSummary[]; total: number }>('/profile/students', {
            params: { semester_id: semesterId, page, page_size: pageSize }
        })
    },

    /**
     * 触发画像重算
     */
    recomputeProfile(studentId?: number, semesterId?: number) {
        return api.post('/profile/recompute', null, {
            params: { student_id: studentId, semester_id: semesterId }
        })
    }
}

export default profileApi
