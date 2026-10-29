<script setup lang="ts">
/**
 * 数据导出管理页面
 * 现代风格 UI 重构
 */
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/request'
import { Download, Document, DataLine, Files, InfoFilled, Memo, Cpu } from '@element-plus/icons-vue'

const loading = ref(false)
const semesters = ref<any[]>([])
const selectedSemesterId = ref<number | null>(null)
const exportingType = ref<string | null>(null)

// 获取批次列表
const fetchSemesters = async () => {
  try {
    const res: any = await api.get('/semesters')
    semesters.value = res
    const active = res.find((s: any) => s.status === 'active')
    if (active) {
      selectedSemesterId.value = active.id
    } else if (res.length > 0) {
      selectedSemesterId.value = res[0].id
    }
  } catch (error) {
    ElMessage.error('获取批次失败')
  }
}

// 下载 Blob 文件
const downloadBlob = (data: any, filename: string) => {
  const blob = new Blob([data], { type: 'application/octet-stream' })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

// 导出成绩 CSV
const exportGrades = async () => {
  if (!selectedSemesterId.value) {
    ElMessage.warning('请选择批次')
    return
  }
  
  exportingType.value = 'grades'
  try {
    const response = await api.get('/export/grades/csv', {
      params: { semester_id: selectedSemesterId.value },
      responseType: 'blob'
    })
    
    const semester = semesters.value.find(s => s.id === selectedSemesterId.value)
    const filename = `成绩导出_${semester?.name || ''}_${new Date().toISOString().slice(0, 10)}.csv`
    downloadBlob(response, filename)
    ElMessage.success('成绩导出成功')
  } catch (error) {
    ElMessage.error('导出失败')
  } finally {
    exportingType.value = null
  }
}

// 导出提交记录 CSV
const exportSubmissions = async () => {
  if (!selectedSemesterId.value) {
    ElMessage.warning('请选择批次')
    return
  }
  
  exportingType.value = 'submissions'
  try {
    const response = await api.get('/export/submissions/csv', {
      params: { semester_id: selectedSemesterId.value },
      responseType: 'blob'
    })
    
    const semester = semesters.value.find(s => s.id === selectedSemesterId.value)
    const filename = `提交记录_${semester?.name || ''}_${new Date().toISOString().slice(0, 10)}.csv`
    downloadBlob(response, filename)
    ElMessage.success('提交记录导出成功')
  } catch (error) {
    ElMessage.error('导出失败')
  } finally {
    exportingType.value = null
  }
}

// 导出 AI 分析报告
const exportAIReport = async () => {
  if (!selectedSemesterId.value) {
    ElMessage.warning('请选择批次')
    return
  }
  
  exportingType.value = 'ai-report'
  try {
    const response = await api.get('/export/ai-report', {
      params: { semester_id: selectedSemesterId.value },
      responseType: 'blob'
    })
    
    const semester = semesters.value.find(s => s.id === selectedSemesterId.value)
    const filename = `AI分析报告_${semester?.name || ''}_${new Date().toISOString().slice(0, 10)}.md`
    downloadBlob(response, filename)
    ElMessage.success('AI 分析报告导出成功')
  } catch (error) {
    ElMessage.error('导出失败')
  } finally {
    exportingType.value = null
  }
}

// 导出批次汇总
const exportSummary = async () => {
  if (!selectedSemesterId.value) {
    ElMessage.warning('请选择批次')
    return
  }
  
  exportingType.value = 'summary'
  try {
    const response = await api.get(`/export/semester/${selectedSemesterId.value}/summary`, {
      responseType: 'blob'
    })
    
    const semester = semesters.value.find(s => s.id === selectedSemesterId.value)
    const filename = `批次汇总_${semester?.name || ''}_${new Date().toISOString().slice(0, 10)}.json`
    downloadBlob(response, filename)
    ElMessage.success('批次汇总导出成功')
  } catch (error) {
    ElMessage.error('导出失败')
  } finally {
    exportingType.value = null
  }
}

onMounted(fetchSemesters)
</script>

<template>
  <div class="export-page">
    <!-- 头部区域 -->
    <header class="page-header">
      <div class="header-content">
        <div class="title-section">
          <div class="icon-wrap">
            <el-icon><Download /></el-icon>
          </div>
          <div>
            <h1 class="page-title">数据导出中心</h1>
            <p class="page-subtitle">轻松导出学生成绩、提交记录及多维度分析报告</p>
          </div>
        </div>
        
        <div class="action-section">
          <el-select
            v-model="selectedSemesterId"
            placeholder="请选择目标批次"
            class="semester-select"
            size="large"
          >
            <el-option
              v-for="s in semesters"
              :key="s.id"
              :label="s.name"
              :value="s.id"
            >
              <div class="option-item">
                <span>{{ s.name }}</span>
                <el-tag v-if="s.status === 'active'" size="small" type="success" effect="dark" round>进行中</el-tag>
              </div>
            </el-option>
          </el-select>
        </div>
      </div>
    </header>

    <!-- 操作指引 -->
    <section class="guide-section">
      <div class="guide-header">
        <el-icon><Memo /></el-icon>
        <span>操作指引</span>
      </div>
      <div class="guide-steps">
        <div class="step-item">
          <div class="step-num">01</div>
          <div class="step-info">
            <h4>锁定批次</h4>
            <p>在页面右上方选择需要导出的教学批次。</p>
          </div>
        </div>
        <div class="step-divider"></div>
        <div class="step-item">
          <div class="step-num">02</div>
          <div class="step-info">
            <h4>选择格式</h4>
            <p>根据需求选择成绩表(CSV)、记录表(CSV)或汇总包(JSON)。</p>
          </div>
        </div>
        <div class="step-divider"></div>
        <div class="step-item">
          <div class="step-num">03</div>
          <div class="step-info">
            <h4>下载归档</h4>
            <p>点击导出按钮，文件将自动生成并下载至本地。</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 导出选项卡片区 -->
    <section class="cards-section">
      <!-- 成绩导出 -->
      <div class="export-card grade-card">
        <div class="card-bg-decoration"></div>
        <div class="card-body">
          <div class="icon-box variant-success">
            <el-icon><DataLine /></el-icon>
          </div>
          <h3 class="card-title">成绩数据导出</h3>
          <p class="card-desc">获取结构化的学生成绩单，支持 Excel 直接分析。</p>
          
          <ul class="feature-list">
            <li><el-icon><InfoFilled /></el-icon> 包含完整学生身份信息</li>
            <li><el-icon><InfoFilled /></el-icon> 自动计算总分与加权分</li>
            <li><el-icon><InfoFilled /></el-icon> UTF-8 编码，兼容 CSV</li>
          </ul>
        </div>
        <div class="card-footer">
          <el-button 
            class="export-btn btn-success"
            :loading="exportingType === 'grades'"
            @click="exportGrades"
            round
          >
            <el-icon><Download /></el-icon>
            {{ exportingType === 'grades' ? '生成中...' : '立即导出 CSV' }}
          </el-button>
        </div>
      </div>

      <!-- 提交记录导出 -->
      <div class="export-card submission-card">
        <div class="card-bg-decoration"></div>
        <div class="card-body">
          <div class="icon-box variant-primary">
            <el-icon><Document /></el-icon>
          </div>
          <h3 class="card-title">提交记录明细</h3>
          <p class="card-desc">导出所有作业的历史提交详情，用于存档或追溯。</p>
          
          <ul class="feature-list">
            <li><el-icon><InfoFilled /></el-icon> 包含文件路径与版本号</li>
            <li><el-icon><InfoFilled /></el-icon> 记录提交与评阅时间戳</li>
            <li><el-icon><InfoFilled /></el-icon> 包含教师评语与分数</li>
          </ul>
        </div>
        <div class="card-footer">
          <el-button 
            class="export-btn btn-primary"
            :loading="exportingType === 'submissions'"
            @click="exportSubmissions"
            round
          >
            <el-icon><Download /></el-icon>
            {{ exportingType === 'submissions' ? '生成中...' : '立即导出 CSV' }}
          </el-button>
        </div>
      </div>

      <!-- AI 分析报告导出 -->
      <div class="export-card ai-report-card">
        <div class="card-bg-decoration"></div>
        <div class="card-body">
          <div class="icon-box variant-ai">
            <el-icon><Cpu /></el-icon>
          </div>
          <h3 class="card-title">AI 智能分析报告</h3>
          <p class="card-desc">AI 自动分析批次数据，生成包含洞察和建议的报告。</p>
          
          <ul class="feature-list">
            <li><el-icon><InfoFilled /></el-icon> AI 自动生成数据分析</li>
            <li><el-icon><InfoFilled /></el-icon> 包含成绩分布与趋势</li>
            <li><el-icon><InfoFilled /></el-icon> Markdown 格式，易于阅读</li>
          </ul>
        </div>
        <div class="card-footer">
          <el-button 
            class="export-btn btn-ai"
            :loading="exportingType === 'ai-report'"
            @click="exportAIReport"
            round
          >
            <el-icon><Cpu /></el-icon>
            {{ exportingType === 'ai-report' ? 'AI 生成中...' : 'AI 生成报告' }}
          </el-button>
        </div>
      </div>

      <!-- 批次汇总导出 -->
      <div class="export-card summary-card">
        <div class="card-bg-decoration"></div>
        <div class="card-body">
          <div class="icon-box variant-purple">
            <el-icon><Files /></el-icon>
          </div>
          <h3 class="card-title">批次全量汇总</h3>
          <p class="card-desc">生成包含所有统计维度的 JSON 数据包。</p>
          
          <ul class="feature-list">
            <li><el-icon><InfoFilled /></el-icon> 批次基础元数据</li>
            <li><el-icon><InfoFilled /></el-icon> 任务完成度统计</li>
            <li><el-icon><InfoFilled /></el-icon> 成绩分布与异常记录</li>
          </ul>
        </div>
        <div class="card-footer">
          <el-button 
            class="export-btn btn-purple"
            :loading="exportingType === 'summary'"
            @click="exportSummary"
            round
          >
            <el-icon><Download /></el-icon>
            {{ exportingType === 'summary' ? '生成中...' : '立即导出 JSON' }}
          </el-button>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.export-page {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  padding: 1rem;
  max-width: 1600px;
  margin: 0 auto;
}

/* Header Styles */
.page-header {
  background: white;
  padding: 1.5rem 2rem;
  border-radius: 12px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1.5rem;
}

.title-section {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.icon-wrap {
  width: 48px;
  height: 48px;
  background: #0891b2;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 24px;
  box-shadow: 0 4px 10px rgba(8, 145, 178, 0.3);
}

.page-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: #1f2937;
  margin: 0;
  line-height: 1.2;
}

.page-subtitle {
  color: #6b7280;
  font-size: 0.875rem;
  margin: 0.25rem 0 0 0;
}

.semester-select {
  width: 240px;
}

.option-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

/* Cards Section */
.cards-section {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 2rem;
}

@media (max-width: 1024px) {
  .cards-section {
    grid-template-columns: 1fr;
  }
}

.export-card {
  background: white;
  border-radius: 16px;
  padding: 2rem;
  position: relative;
  overflow: hidden;
  transition: all 0.3s ease;
  border: 1px solid #f3f4f6;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.export-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
}

.card-bg-decoration {
  position: absolute;
  top: -50px;
  right: -50px;
  width: 150px;
  height: 150px;
  border-radius: 50%;
  opacity: 0.05;
  pointer-events: none;
}

.grade-card .card-bg-decoration { background: #10b981; }
.submission-card .card-bg-decoration { background: #3b82f6; }
.ai-report-card .card-bg-decoration { background: #0891b2; }
.summary-card .card-bg-decoration { background: #0d9488; }

.card-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.icon-box {
  width: 64px;
  height: 64px;
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  margin-bottom: 1.5rem;
  transition: transform 0.3s ease;
}

.export-card:hover .icon-box {
  transform: scale(1.1) rotate(5deg);
}

.variant-success { background: rgba(16, 185, 129, 0.1); color: #10b981; }
.variant-primary { background: rgba(59, 130, 246, 0.1); color: #3b82f6; }
.variant-ai { background: rgba(8, 145, 178, 0.1); color: #0891b2; }
.variant-purple { background: rgba(13, 148, 136, 0.1); color: #0d9488; }

.card-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: #111827;
  margin: 0 0 0.5rem 0;
}

.card-desc {
  color: #6b7280;
  font-size: 0.875rem;
  margin: 0 0 1.5rem 0;
  line-height: 1.5;
}

.feature-list {
  list-style: none;
  padding: 0;
  margin: 0 auto 2rem auto;
  text-align: left;
  width: 100%;
}

.feature-list li {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: #4b5563;
  font-size: 0.875rem;
  margin-bottom: 0.75rem;
  padding: 0.5rem;
  border-radius: 8px;
  background: #f9fafb;
}

.feature-list li .el-icon {
  color: #9ca3af;
}

.card-footer {
  margin-top: auto;
  width: 100%;
}

.export-btn {
  width: 100%;
  height: 48px;
  font-weight: 600;
  border: none;
  transition: all 0.3s;
}

.btn-success {
  background: #10b981;
  color: white;
  box-shadow: 0 4px 6px rgba(16, 185, 129, 0.3);
}
.btn-success:hover { background: #059669; box-shadow: 0 6px 8px rgba(16, 185, 129, 0.4); }

.btn-primary {
  background: #3b82f6;
  color: white;
  box-shadow: 0 4px 6px rgba(59, 130, 246, 0.3);
}
.btn-primary:hover { background: #2563eb; box-shadow: 0 6px 8px rgba(59, 130, 246, 0.4); }

.btn-ai {
  background: #0891b2;
  color: white;
  box-shadow: 0 4px 6px rgba(8, 145, 178, 0.3);
}
.btn-ai:hover { background: #0e7490; box-shadow: 0 6px 8px rgba(8, 145, 178, 0.4); }

.btn-purple {
  background: #0d9488;
  color: white;
  box-shadow: 0 4px 6px rgba(13, 148, 136, 0.3);
}
.btn-purple:hover { background: #0891b2; box-shadow: 0 6px 8px rgba(13, 148, 136, 0.4); }

/* Guide Section */
.guide-section {
  background: white;
  border-radius: 12px;
  padding: 1.5rem 2rem;
  border: 1px dashed #e5e7eb;
}

.guide-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
  color: #374151;
  margin-bottom: 1.5rem;
  font-size: 1.125rem;
}

.guide-header .el-icon {
  color: #6b7280;
}

.guide-steps {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

@media (max-width: 768px) {
  .guide-steps {
    flex-direction: column;
    gap: 1.5rem;
    align-items: flex-start;
  }
  .step-divider {
    display: none;
  }
}

.step-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex: 1;
}

.step-num {
  width: 36px;
  height: 36px;
  background: #f3f4f6;
  color: #6b7280;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-family: monospace;
  font-size: 1rem;
}

.step-info h4 {
  margin: 0;
  font-size: 0.95rem;
  color: #1f2937;
}

.step-info p {
  margin: 0.25rem 0 0 0;
  font-size: 0.8rem;
  color: #6b7280;
}

.step-divider {
  width: 1px;
  height: 40px;
  background: #e5e7eb;
  margin: 0 2rem;
}
</style>
