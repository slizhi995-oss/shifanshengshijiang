/**
 * API 模块统一导出
 */
export { authApi } from './auth'
export { userApi } from './user'
export { semesterApi } from './semester'
export { assignmentApi } from './assignment'
export { taskApi } from './task'
export { submissionApi } from './submission'
export { messageApi } from './message'
export { adminApi } from './admin'
export { aiApi } from './ai'
export { profileApi } from './profile'
export { statisticsApi } from './statistics'
export { exportApi, downloadBlob } from './export'
export { rubricApi } from './rubric'
export { practiceApi } from './practice'
export { notificationApi } from './notification'
export { aiOpsApi } from './aiOps'

// Re-export types
export type { LoginParams, ChangePasswordParams } from './auth'
export type { UserQuery, UserCreate } from './user'
export type { SemesterCreate } from './semester'
export type { BatchAssignParams } from './assignment'
export type { TaskCreate, TaskQuery } from './task'
export type { SubmissionQuery, ApproveData, RejectData } from './submission'
export type { SendMessageParams } from './message'
export type { MonitorQuery } from './admin'
