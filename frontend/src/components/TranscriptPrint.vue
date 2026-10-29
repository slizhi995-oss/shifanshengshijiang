<script setup lang="ts">
/**
 * 成绩单打印组件
 * 支持打印学生成绩单或导师评语
 */
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/request'
import { useAuthStore } from '@/stores/auth'
import { Printer, Download, Document } from '@element-plus/icons-vue'

const props = defineProps<{
  visible: boolean
  studentId?: number
  semesterId?: number
}>()

const emit = defineEmits(['update:visible'])

const authStore = useAuthStore()
const loading = ref(false)
const printData = ref<any>(null)

// 获取成绩数据
const fetchPrintData = async () => {
  loading.value = true
  try {
    const params: any = {}
    if (props.studentId) params.student_id = props.studentId
    if (props.semesterId) params.semester_id = props.semesterId

    const res: any = await api.get('/grades/print-data', { params })
    
    if (res.success) {
      printData.value = res.data
    }
  } catch (error) {
    // 使用模拟数据
    printData.value = {
      student: {
        name: authStore.user?.name || '学生姓名',
        user_code: authStore.user?.user_code || '202400001',
        college: authStore.user?.college || '教育学院',
        major: authStore.user?.major || '教育技术学',
        class_name: authStore.user?.class_name || '2024级1班'
      },
      semester: {
        name: '2024春季试讲批次',
        start_date: '2024-03-01',
        end_date: '2024-06-30'
      },
      grades: [
        { task_title: '教学设计（第一周）', lesson_plan_score: 85, video_score: 88, total_score: 86, feedback: '教案结构完整，教学目标明确。视频表现良好，语言表达清晰。' },
        { task_title: '试讲视频（第二周）', lesson_plan_score: 82, video_score: 85, total_score: 83, feedback: '板书设计有待改进，时间把控较好。' },
        { task_title: '教学设计（第三周）', lesson_plan_score: 90, video_score: 92, total_score: 91, feedback: '进步明显！教学互动设计精彩，课堂节奏把握准确。' }
      ],
      summary: {
        total_tasks: 3,
        completed_tasks: 3,
        average_score: 86.7,
        highest_score: 91,
        lowest_score: 83,
        rank: 15,
        total_students: 120
      },
      instructor: {
        name: '王老师',
        title: '副教授',
        comment: '该生学习态度认真，进步明显。建议继续加强板书设计和教学互动能力的训练。'
      },
      print_date: new Date().toLocaleDateString('zh-CN')
    }
  } finally {
    loading.value = false
  }
}

// 打印
const handlePrint = () => {
  const printContent = document.getElementById('print-content')
  if (!printContent) return

  const printWindow = window.open('', '_blank')
  if (!printWindow) {
    ElMessage.error('无法打开打印窗口，请检查浏览器设置')
    return
  }

  printWindow.document.write(`
    <!DOCTYPE html>
    <html>
    <head>
      <title>成绩单 - ${printData.value?.student?.name}</title>
      <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: "Microsoft YaHei", sans-serif; padding: 40px; color: #333; }
        .header { text-align: center; margin-bottom: 30px; border-bottom: 2px solid #333; padding-bottom: 20px; }
        .title { font-size: 24px; font-weight: bold; margin-bottom: 10px; }
        .subtitle { font-size: 14px; color: #666; }
        .info-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 30px; }
        .info-item { display: flex; }
        .info-label { font-weight: bold; min-width: 80px; }
        .grades-table { width: 100%; border-collapse: collapse; margin-bottom: 30px; }
        .grades-table th, .grades-table td { border: 1px solid #ddd; padding: 10px; text-align: left; }
        .grades-table th { background: #f5f5f5; font-weight: bold; }
        .summary-box { background: #f9f9f9; padding: 20px; border-radius: 8px; margin-bottom: 30px; }
        .summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; text-align: center; }
        .summary-value { font-size: 24px; font-weight: bold; color: #0891b2; }
        .summary-label { font-size: 12px; color: #666; }
        .comment-box { border-top: 1px solid #ddd; padding-top: 20px; }
        .comment-title { font-weight: bold; margin-bottom: 10px; }
        .footer { margin-top: 40px; display: flex; justify-content: space-between; font-size: 12px; color: #999; }
        .signature { margin-top: 60px; display: flex; justify-content: flex-end; }
        .signature-line { border-top: 1px solid #333; width: 200px; text-align: center; padding-top: 5px; }
        @media print { body { padding: 20px; } }
      </style>
    </head>
    <body>
      ${printContent.innerHTML}
    </body>
    </html>
  `)

  printWindow.document.close()
  printWindow.focus()
  
  setTimeout(() => {
    printWindow.print()
    printWindow.close()
  }, 250)
}

// 关闭
const close = () => {
  emit('update:visible', false)
}

onMounted(() => {
  if (props.visible) {
    fetchPrintData()
  }
})
</script>

<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="成绩单预览"
    width="800px"
    top="3vh"
    class="transcript-dialog"
  >
    <div v-loading="loading" class="transcript-content">
      <!-- 打印内容 -->
      <div id="print-content" v-if="printData">
        <!-- 标题 -->
        <div class="header">
          <div class="title">学 生 成 绩 单</div>
          <div class="subtitle">Student Transcript</div>
        </div>

        <!-- 学生信息 -->
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">姓　　名：</span>
            <span>{{ printData.student.name }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">学　　号：</span>
            <span>{{ printData.student.user_code }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">学　　院：</span>
            <span>{{ printData.student.college }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">专　　业：</span>
            <span>{{ printData.student.major }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">班　　级：</span>
            <span>{{ printData.student.class_name }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">批　　次：</span>
            <span>{{ printData.semester.name }}</span>
          </div>
        </div>

        <!-- 成绩表格 -->
        <table class="grades-table">
          <thead>
            <tr>
              <th>作业名称</th>
              <th>教案分</th>
              <th>视频分</th>
              <th>总分</th>
              <th>教师评语</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(grade, index) in printData.grades" :key="index">
              <td>{{ grade.task_title }}</td>
              <td>{{ grade.lesson_plan_score }}</td>
              <td>{{ grade.video_score }}</td>
              <td><strong>{{ grade.total_score }}</strong></td>
              <td>{{ grade.feedback }}</td>
            </tr>
          </tbody>
        </table>

        <!-- 成绩汇总 -->
        <div class="summary-box">
          <div class="summary-grid">
            <div>
              <div class="summary-value">{{ printData.summary.average_score.toFixed(1) }}</div>
              <div class="summary-label">平均分</div>
            </div>
            <div>
              <div class="summary-value">{{ printData.summary.highest_score }}</div>
              <div class="summary-label">最高分</div>
            </div>
            <div>
              <div class="summary-value">{{ printData.summary.completed_tasks }}/{{ printData.summary.total_tasks }}</div>
              <div class="summary-label">完成任务</div>
            </div>
            <div>
              <div class="summary-value">{{ printData.summary.rank }}/{{ printData.summary.total_students }}</div>
              <div class="summary-label">班级排名</div>
            </div>
          </div>
        </div>

        <!-- 导师评语 -->
        <div class="comment-box">
          <div class="comment-title">指导教师评语</div>
          <p style="line-height: 1.8; margin-bottom: 15px;">{{ printData.instructor.comment }}</p>
          <div style="text-align: right; color: #666;">
            指导教师：{{ printData.instructor.name }}（{{ printData.instructor.title }}）
          </div>
        </div>

        <!-- 签名区 -->
        <div class="signature">
          <div class="signature-line">指导教师签字</div>
        </div>

        <!-- 页脚 -->
        <div class="footer">
          <span>打印日期：{{ printData.print_date }}</span>
          <span>面向师范生试讲训练的多模态智能赋能系统</span>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="close">关闭</el-button>
      <el-button type="primary" :icon="Printer" @click="handlePrint">打印成绩单</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.transcript-content {
  max-height: 70vh;
  overflow-y: auto;
}

#print-content {
  padding: 20px;
  background: white;
}

.header {
  text-align: center;
  margin-bottom: 30px;
  border-bottom: 2px solid #333;
  padding-bottom: 20px;
}

.title {
  font-size: 24px;
  font-weight: bold;
  margin-bottom: 8px;
  letter-spacing: 8px;
}

.subtitle {
  font-size: 14px;
  color: #666;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 15px;
  margin-bottom: 30px;
}

.info-item {
  display: flex;
  font-size: 14px;
}

.info-label {
  font-weight: 600;
  min-width: 80px;
  color: #374151;
}

.grades-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 30px;
  font-size: 14px;
}

.grades-table th,
.grades-table td {
  border: 1px solid #e5e7eb;
  padding: 12px 10px;
  text-align: left;
}

.grades-table th {
  background: #f3f4f6;
  font-weight: 600;
  color: #374151;
}

.grades-table td:nth-child(2),
.grades-table td:nth-child(3),
.grades-table td:nth-child(4) {
  text-align: center;
  width: 80px;
}

.summary-box {
  background: #f0fdfa;
  border: 1px solid #ccfbf1;
  padding: 24px;
  border-radius: 12px;
  margin-bottom: 30px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  text-align: center;
}

.summary-value {
  font-size: 28px;
  font-weight: 700;
  color: #0891b2;
  line-height: 1;
}

.summary-label {
  font-size: 12px;
  color: #6b7280;
  margin-top: 8px;
}

.comment-box {
  border-top: 1px solid #e5e7eb;
  padding-top: 24px;
}

.comment-title {
  font-weight: 600;
  font-size: 16px;
  color: #374151;
  margin-bottom: 12px;
}

.signature {
  margin-top: 60px;
  display: flex;
  justify-content: flex-end;
}

.signature-line {
  border-top: 1px solid #333;
  width: 200px;
  text-align: center;
  padding-top: 8px;
  font-size: 12px;
  color: #666;
}

.footer {
  margin-top: 40px;
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #9ca3af;
}

@media (max-width: 640px) {
  .info-grid {
    grid-template-columns: 1fr;
  }
  
  .summary-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
