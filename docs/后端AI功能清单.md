# 后端 AI 功能实现清单

> 更新时间: 2026-02-01
> 用于计算机设计大赛人工智能应用赛道

## 一、核心 AI 功能模块

### 1. 教案智能分析 `/api/v1/ai/*`

| 接口 | 方法 | 功能 | 状态 |
|-----|------|-----|------|
| `/ai/status` | GET | 获取AI服务状态 | ✅ |
| `/ai/parse_file` | POST | 解析上传文档 | ✅ |
| `/ai/analyze` | POST | 教案7维度分析 | ✅ |
| `/ai/summary` | POST | 生成教案摘要 | ✅ |
| `/ai/improve` | POST | 获取改进建议 | ✅ |
| `/ai/feedback` | POST | 生成AI评语 | ✅ |
| `/ai/generate` | POST | AI生成教案 | ✅ |
| `/ai/assistant/start` | POST | 启动备课助手 | ✅ |
| `/ai/assistant/chat` | POST | 备课助手对话 | ✅ |
| `/ai/assistant/report` | POST | 生成练习报告 | ✅ |
| `/ai/batch/analyze` | POST | 批量教案分析 | ✅ |

### 2. 视频多模态分析 `/api/v1/video-analysis/*`

| 接口 | 方法 | 功能 | 状态 |
|-----|------|-----|------|
| `/video-analysis/analyze` | POST | 上传并分析视频 | ✅ |
| `/video-analysis/submissions/{id}/analyze` | POST | 分析已提交的视频 | ✅ |
| `/video-analysis/submissions/{id}/generate-ai-feedback` | POST | 生成AI反馈 | ✅ |
| `/video-analysis/speech/transcribe` | POST | 语音转文字 | ✅ |
| `/video-analysis/speech/analyze` | POST | 语音特征分析 | ✅ |
| `/video-analysis/vision/analyze` | POST | 视觉分析(手势/姿态) | ✅ |

### 3. 成长画像服务 `/api/v1/profile/*`

| 接口 | 方法 | 功能 | 状态 |
|-----|------|-----|------|
| `/profile/me` | GET | 学生查看自己画像 | ✅ 新增 |
| `/profile/students/{id}` | GET | 老师查看学生画像 | ✅ 新增 |
| `/profile/overview` | GET | 班级概览 | ✅ 新增 |
| `/profile/students` | GET | 学生列表带画像 | ✅ 新增 |
| `/profile/recompute` | POST | 触发画像重算 | ✅ 新增 |

### 4. AI运营看板 `/api/v1/admin/ai-ops/*`

| 接口 | 方法 | 功能 | 状态 |
|-----|------|-----|------|
| `/admin/ai-ops/overview` | GET | 用量统计概览 | ✅ 新增 |
| `/admin/ai-ops/failures` | GET | 失败任务列表 | ✅ 新增 |
| `/admin/ai-ops/retry` | POST | 批量重试 | ✅ 新增 |
| `/admin/ai-ops/audit` | GET | 审计日志 | ✅ 新增 |
| `/admin/ai-ops/thresholds` | GET/PUT | 阈值设置 | ✅ 新增 |
| `/admin/ai-ops/status` | GET | AI服务状态 | ✅ 新增 |

### 5. 备课练习会话 `/api/v1/practice-sessions/*`

| 接口 | 方法 | 功能 | 状态 |
|-----|------|-----|------|
| `/practice-sessions` | GET | 获取会话列表 | ✅ 新增 |
| `/practice-sessions` | POST | 创建新会话 | ✅ 新增 |
| `/practice-sessions/{id}` | GET | 获取会话详情 | ✅ 新增 |
| `/practice-sessions/{id}/messages` | PUT | 保存消息 | ✅ 新增 |
| `/practice-sessions/{id}/report` | POST | 生成报告 | ✅ 新增 |
| `/practice-sessions/{id}` | DELETE | 删除会话 | ✅ 新增 |
| `/practice-sessions/stats/me` | GET | 练习统计 | ✅ 新增 |

### 6. 数据导出 `/api/v1/export/*`

| 接口 | 方法 | 功能 | 状态 |
|-----|------|-----|------|
| `/export/grades/csv` | GET | 导出成绩CSV | ✅ 新增 |
| `/export/submissions/csv` | GET | 导出提交记录CSV | ✅ 新增 |
| `/export/analysis/{id}` | GET | 导出AI分析报告 | ✅ 新增 |
| `/export/semester/{id}/summary` | GET | 导出批次汇总 | ✅ 新增 |

### 7. 统计数据 `/api/v1/statistics/*`

| 接口 | 方法 | 功能 | 状态 |
|-----|------|-----|------|
| `/statistics/student/dashboard` | GET | 学生仪表盘统计 | ✅ 新增 |
| `/statistics/instructor/dashboard` | GET | 老师仪表盘统计 | ✅ 新增 |
| `/statistics/admin/dashboard` | GET | 管理员仪表盘统计 | ✅ 新增 |
| `/statistics/semester/{id}/summary` | GET | 批次汇总统计 | ✅ 新增 |

### 8. AI辅助批改（提交模块扩展）

| 接口 | 方法 | 功能 | 状态 |
|-----|------|-----|------|
| `/submissions/{id}/ai-grade` | POST | AI综合批改 | ✅ 新增 |
| `/submissions/{id}/analysis` | GET | 获取AI分析结果 | ✅ 新增 |

### 9. 评分规则管理 `/api/v1/rubrics/*`

| 接口 | 方法 | 功能 | 状态 |
|-----|------|-----|------|
| `/rubrics` | GET | 获取评分规则列表 | ✅ 新增 |
| `/rubrics` | POST | 创建评分规则 | ✅ 新增 |
| `/rubrics/defaults` | GET | 获取默认维度配置 | ✅ 新增 |
| `/rubrics/{id}` | GET | 获取规则详情 | ✅ 新增 |
| `/rubrics/{id}` | PUT | 更新评分规则 | ✅ 新增 |
| `/rubrics/{id}` | DELETE | 删除评分规则 | ✅ 新增 |
| `/rubrics/{id}/apply` | POST | 应用规则计算分数 | ✅ 新增 |

---

## 二、新增数据模型

### ProfileSnapshot（画像快照）
```python
- id: 主键
- student_id: 学生ID
- semester_id: 批次ID
- radar_json: 雷达图数据(JSON)
- trend_json: 趋势数据(JSON)
- action_items_json: 行动建议(JSON)
- overall_score: 综合评分
- total_submissions: 总提交数
- approved_submissions: 通过数
- created_at, updated_at: 时间戳
```

### PracticeSession（练习会话）
```python
- id: 主键
- student_id: 学生ID
- submission_id: 关联提交ID（可选）
- title: 会话标题
- grade: 年级
- personality: AI性格
- messages_json: 对话历史(JSON)
- report_json: 练习报告(JSON)
- message_count: 消息数量
- overall_rating: 评分
- started_at, ended_at: 起止时间
- created_at, updated_at: 时间戳
```

### GradingRubric（评分规则）
```python
- id: 主键
- name: 规则名称
- description: 规则描述
- instructor_id: 创建者ID
- semester_id: 批次ID(可选)
- is_default: 是否默认
- is_active: 是否启用
- lesson_plan_weight: 教案权重(0-100)
- video_weight: 视频权重(0-100)
- lesson_plan_dimensions: 教案维度配置(JSON)
- video_dimensions: 视频维度配置(JSON)
- grade_levels: 评分等级配置(JSON)
- created_at, updated_at: 时间戳
```

### AICallLog（AI调用日志）
```python
- id: 主键
- user_id: 调用者ID
- submission_id: 关联提交ID
- call_type: 调用类型
- provider: AI服务商
- model: 模型名称
- input_tokens: 输入Token数
- output_tokens: 输出Token数
- audio_seconds: 音频秒数
- latency_ms: 耗时(毫秒)
- is_success: 是否成功
- error_message: 错误信息
- request_summary: 请求概要
- ip_address: IP地址
- created_at: 创建时间
```

---

## 三、新增服务类

| 服务 | 文件 | 功能 |
|-----|------|-----|
| ProfileService | `services/profile_service.py` | 画像计算、雷达图、趋势、建议 |
| ComprehensiveGradingService | `services/grading_service.py` | 综合批改、建议评分 |
| ExportService | `services/export_service.py` | 数据导出CSV/JSON |
| AILogService | `services/ai_log_service.py` | AI调用日志、统计、审计 |

---

## 四、画像雷达图维度（13维）

### 教案类（7维）
- structure: 结构完整性
- objectives: 教学目标
- key_points: 重难点分析
- teaching_process: 教学过程
- teaching_methods: 教学方法
- board_design: 板书设计
- language: 教学语言

### 视频类（6维）
- speech_rate: 语速控制
- fluency: 表达流畅度
- gesture: 手势运用
- posture: 姿态仪表
- eye_contact: 眼神交流
- space_usage: 空间运用

---

## 五、关键特性

1. **自动画像更新**：提交通过后自动触发画像重算
2. **会话持久化**：备课助手对话入库，便于统计分析
3. **综合批改**：结合教案+视频生成综合评语和建议分数
4. **数据导出**：支持CSV（Excel兼容）和JSON格式
5. **分权限统计**：学生/老师/管理员各有专属仪表盘接口
6. **评分规则自定义**：老师可自定义评分维度和权重
7. **AI调用审计**：完整的调用日志和成本统计

---

## 六、环境配置

确保 `.env` 中配置了以下参数：

```env
# AI 基础配置
AI_ENABLED=True
AI_PROVIDER=dashscope  # 可选: dashscope/openai/deepseek

# 通义千问
DASHSCOPE_API_KEY=sk-xxx
DASHSCOPE_MODEL=qwen-plus

# 视频分析
ENABLE_GESTURE_ANALYSIS=True
USE_CLOUD_VISION=True
VIDEO_ANALYSIS_PROVIDER=dashscope
```

---

## 七、数据库迁移

运行以下命令创建新表：

```bash
cd backend
python -m scripts.init_db
```

这将自动创建以下新表：
- `profile_snapshots` - 画像快照
- `practice_sessions` - 练习会话
- `grading_rubrics` - 评分规则
- `ai_call_logs` - AI调用日志

---

## 八、API 汇总统计

| 模块 | 接口数量 |
|-----|---------|
| 成长画像 | 5 |
| AI运营看板 | 6 |
| 备课练习会话 | 7 |
| 数据导出 | 4 |
| 统计数据 | 4 |
| AI辅助批改 | 2 |
| 评分规则 | 7 |
| **总计新增** | **35** |
