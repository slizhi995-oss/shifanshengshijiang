/**
 * 统计数据 API
 */
import api from '@/utils/request'

export interface StudentDashboardStats {
    tasks: {
        total: number
        submitted: number
        approved: number
        completion_rate: number
    }
    scores: {
        average: number
        highest: number
        latest: number | null
    }
    practice: {
        sessions: number
        messages: number
    }
    recent_submissions: Array<{
        id: number
        task_title: string
        status: string
        score: number | null
        submitted_at: string
    }>
}

export interface InstructorDashboardStats {
    students: {
        total: number
        submitted: number
        all_approved: number
    }
    tasks: {
        total: number
        avg_submissions: number
    }
    grading: {
        pending: number
        graded: number
        approved: number
    }
    scores: {
        average: number
        distribution: {
            '90+': number
            '80-89': number
            '70-79': number
            '60-69': number
            '<60': number
        }
    }
    recent_pending: Array<{
        id: number
        student_name: string
        task_title: string
        submitted_at: string
    }>
}

export interface AdminDashboardStats {
    users: {
        total: number
        students: number
        instructors: number
        admins: number
    }
    semesters: {
        total: number
        active: number
    }
    submissions: {
        total: number
        approved: number
        approval_rate: number
    }
    ai: {
        analyzed_submissions: number
        ai_usage_rate: number
    }
    activity: {
        recent_7d_submissions: number
    }
}

export interface SemesterSummary {
    semester: {
        id: number
        name: string
        status: string
    }
    counts: {
        tasks: number
        students: number
        instructors: number
        submissions: number
    }
    scores: {
        average: number
        min: number
        max: number
    }
    status_breakdown: {
        pending: number
        graded: number
        approved: number
        rejected: number
    }
}

export const statisticsApi = {
    /**
     * 获取学生仪表盘统计
     */
    getStudentDashboard(semesterId?: number) {
        const params = semesterId ? { semester_id: semesterId } : {}
        return api.get<{ success: boolean; data: StudentDashboardStats }>('/statistics/student/dashboard', { params })
    },

    /**
     * 获取老师仪表盘统计
     */
    getInstructorDashboard(semesterId: number) {
        return api.get<{ success: boolean; data: InstructorDashboardStats }>('/statistics/instructor/dashboard', {
            params: { semester_id: semesterId }
        })
    },

    /**
     * 获取管理员仪表盘统计
     */
    getAdminDashboard() {
        return api.get<{ success: boolean; data: AdminDashboardStats }>('/statistics/admin/dashboard')
    },

    /**
     * 获取批次汇总
     */
    getSemesterSummary(semesterId: number) {
        return api.get<{ success: boolean; data: SemesterSummary }>(`/statistics/semester/${semesterId}/summary`)
    }
}

export default statisticsApi
