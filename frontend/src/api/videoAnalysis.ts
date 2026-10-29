/**
 * 视频分析 API
 */
import request from '@/utils/request'

export interface VideoAnalysisResult {
  status: 'not_analyzed' | 'processing' | 'completed'
  message?: string
  analysis?: {
    duration: number
    transcript: string
    speech_rate: number
    pause_count: number
    filler_word_count: number
    filler_words: Record<string, number>
    overall_score: number
    suggestions: string[]
    time_distribution?: Record<string, number>
    gesture_analysis?: {
      posture_score: number
      gesture_score: number
      overall_gesture_score: number
      frame_analyzed: number
    }
  }
}

export interface AIFeedbackResult {
  feedback: string
  suggested_score: number
  lesson_plan_score?: number
  video_score?: number
}

/**
 * 触发视频分析
 */
export function triggerVideoAnalysis(submissionId: number) {
  return request<{
    message: string
    submission_id: number
    status: string
  }>({
    url: `/video-analysis/submissions/${submissionId}/analyze-video`,
    method: 'post',
  })
}

/**
 * 获取视频分析结果
 */
export function getVideoAnalysis(submissionId: number) {
  return request<VideoAnalysisResult>({
    url: `/video-analysis/submissions/${submissionId}/video-analysis`,
    method: 'get',
  })
}

/**
 * 重新分析视频（仅老师）
 */
export function reanalyzeVideo(submissionId: number) {
  return request<{
    message: string
    submission_id: number
    status: string
  }>({
    url: `/video-analysis/submissions/${submissionId}/reanalyze-video`,
    method: 'post',
  })
}

/**
 * 生成AI综合评语
 */
export function generateAIFeedback(submissionId: number) {
  return request<AIFeedbackResult>({
    url: `/video-analysis/submissions/${submissionId}/generate-ai-feedback`,
    method: 'post',
  })
}
