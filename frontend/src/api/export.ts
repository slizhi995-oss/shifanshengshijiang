/**
 * 数据导出 API
 */
import api from '@/utils/request'

export const exportApi = {
    /**
     * 导出成绩 CSV
     */
    async exportGradesCSV(semesterId: number) {
        const response = await api.get('/export/grades/csv', {
            params: { semester_id: semesterId },
            responseType: 'blob'
        })
        return response
    },

    /**
     * 导出提交记录 CSV
     */
    async exportSubmissionsCSV(semesterId: number) {
        const response = await api.get('/export/submissions/csv', {
            params: { semester_id: semesterId },
            responseType: 'blob'
        })
        return response
    },

    /**
     * 导出 AI 分析报告
     */
    async exportAnalysis(submissionId: number) {
        const response = await api.get(`/export/analysis/${submissionId}`, {
            responseType: 'blob'
        })
        return response
    },

    /**
     * 导出批次汇总
     */
    async exportSemesterSummary(semesterId: number) {
        const response = await api.get(`/export/semester/${semesterId}/summary`, {
            responseType: 'blob'
        })
        return response
    }
}

/**
 * 下载 Blob 文件
 */
export function downloadBlob(blob: Blob, filename: string) {
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
}

export default exportApi
