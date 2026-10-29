<script setup lang="ts">
/**
 * 帮助中心页面
 * 使用指南和常见问题
 */
import { ref, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { 
  QuestionFilled, Document, VideoCamera, ChatDotRound,
  Upload, TrendCharts, User, Setting, Search,
  ArrowRight, StarFilled
} from '@element-plus/icons-vue'

const authStore = useAuthStore()
const searchQuery = ref('')
const activeCategory = ref('getting-started')

// 帮助分类
const categories = [
  { id: 'getting-started', icon: StarFilled, label: '快速入门' },
  { id: 'submission', icon: Upload, label: '作业提交' },
  { id: 'ai-features', icon: ChatDotRound, label: 'AI 功能' },
  { id: 'grades', icon: TrendCharts, label: '成绩查看' },
  { id: 'faq', icon: QuestionFilled, label: '常见问题' }
]

// 帮助内容
const helpContent: Record<string, any[]> = {
  'getting-started': [
    {
      title: '系统简介',
      content: `
        本系统是面向师范生试讲训练的多模态智能赋能平台，综合文本、语音、视频与 AI 分析能力，帮助学生完成试讲训练，并由导师进行专业评估。
        
        **主要功能：**
        - 教案上传与评审
        - 试讲视频提交
        - AI 智能分析反馈
        - 成绩查询与成长画像
        - 师生在线沟通
      `
    },
    {
      title: '登录系统',
      content: `
        1. 打开系统首页
        2. 输入学号/工号
        3. 输入密码（初始密码为学号后6位）
        4. 点击"登录"按钮
        
        **提示：** 首次登录后建议修改密码
      `
    },
    {
      title: '熟悉界面',
      content: `
        登录后，您将看到：
        
        - **左侧菜单** - 导航到各功能模块
        - **顶部栏** - 显示用户信息和通知
        - **主内容区** - 显示当前页面内容
        
        点击左侧菜单项即可切换不同功能。
      `
    }
  ],
  'submission': [
    {
      title: '查看作业任务',
      content: `
        1. 点击左侧菜单"作业列表"
        2. 选择当前批次
        3. 查看所有待完成的作业任务
        4. 注意查看截止日期
        
        **提示：** 逾期作业将无法提交
      `
    },
    {
      title: '上传教案',
      content: `
        1. 在作业列表中点击"提交作业"
        2. 点击"上传教案"区域
        3. 选择 PDF、Word 或图片格式的教案文件
        4. 等待上传完成
        
        **支持格式：** PDF, DOC, DOCX, PNG, JPG
        **大小限制：** 不超过 20MB
      `
    },
    {
      title: '上传试讲视频',
      content: `
        1. 在提交页面点击"上传视频"
        2. 选择录制好的试讲视频
        3. 等待上传完成（可能需要较长时间）
        4. 上传完成后系统会自动进行 AI 分析
        
        **支持格式：** MP4, AVI, MOV, WMV
        **大小限制：** 不超过 500MB
        **建议时长：** 10-15 分钟
      `
    },
    {
      title: '提交作业',
      content: `
        1. 确保教案和视频都已上传
        2. 检查文件是否正确
        3. 点击"提交作业"按钮
        4. 等待导师批改
        
        **注意：** 提交后可以重新提交覆盖
      `
    }
  ],
  'ai-features': [
    {
      title: 'AI 备课助手',
      content: `
        AI 备课助手可以帮助您：
        
        - 生成教案大纲
        - 提供教学建议
        - 设计教学目标
        - 推荐教学资源
        
        **使用方法：**
        1. 进入"AI 备课助手"页面
        2. 输入您的问题或需求
        3. 等待 AI 生成回复
        4. 参考回复完善您的教案
      `
    },
    {
      title: 'AI 教案分析',
      content: `
        提交教案后，系统会自动进行 AI 分析：
        
        - 多维度评分
        - 优点总结
        - 改进建议
        - 详细点评
        
        分析完成后可在"我的提交"中查看结果。
      `
    },
    {
      title: 'AI 视频分析',
      content: `
        上传试讲视频后，AI 会分析：
        
        - 语言表达
        - 肢体语言
        - 时间把控
        - 板书设计
        - 教学逻辑
        
        分析通常需要 3-5 分钟完成。
      `
    }
  ],
  'grades': [
    {
      title: '查看成绩',
      content: `
        1. 点击左侧菜单"我的成绩"
        2. 选择批次查看不同学期成绩
        3. 查看各项作业的评分和评语
        
        成绩包括：
        - 教案分数
        - 视频分数
        - 总评分数
        - 导师评语
      `
    },
    {
      title: '成长画像',
      content: `
        成长画像展示您的能力发展：
        
        - 能力雷达图
        - 成绩趋势
        - 优势维度
        - 改进建议
        
        在"成长画像"页面查看详情。
      `
    }
  ],
  'faq': [
    {
      title: '忘记密码怎么办？',
      content: `
        请联系管理员重置密码。
        
        管理员联系方式通常在系统公告中公布。
      `
    },
    {
      title: '作业提交后可以修改吗？',
      content: `
        可以。在截止日期前，您可以重新提交作业，新提交会覆盖旧的。
        
        **注意：** 导师已开始批改后可能无法覆盖。
      `
    },
    {
      title: 'AI 分析结果准确吗？',
      content: `
        AI 分析仅供参考，最终评分以导师评定为准。
        
        AI 分析的优势：
        - 快速获得反馈
        - 多维度分析
        - 客观一致的标准
        
        建议结合 AI 反馈和导师意见改进。
      `
    },
    {
      title: '视频上传失败怎么办？',
      content: `
        常见原因及解决方法：
        
        1. **文件太大** - 压缩视频或降低分辨率
        2. **格式不支持** - 转换为 MP4 格式
        3. **网络不稳定** - 检查网络连接，重新上传
        4. **浏览器问题** - 尝试用 Chrome 浏览器
        
        如仍有问题，请联系技术支持。
      `
    },
    {
      title: '如何联系导师？',
      content: `
        使用系统内置的"联系导师"功能：
        
        1. 点击左侧菜单"联系导师"
        2. 选择您的导师
        3. 发送消息
        
        导师会在工作时间内回复您的消息。
      `
    }
  ]
}

// 过滤后的内容
const filteredContent = computed(() => {
  const content = helpContent[activeCategory.value] || []
  if (!searchQuery.value) return content
  
  const query = searchQuery.value.toLowerCase()
  return content.filter(item => 
    item.title.toLowerCase().includes(query) ||
    item.content.toLowerCase().includes(query)
  )
})
</script>

<template>
  <div class="help-center">
    <!-- 页面头部 -->
    <div class="help-header">
      <h2 class="help-title">
        <el-icon class="text-cyan-600"><QuestionFilled /></el-icon>
        帮助中心
      </h2>
      <div class="search-box">
        <el-input 
          v-model="searchQuery" 
          placeholder="搜索帮助内容..."
          :prefix-icon="Search"
          clearable
        />
      </div>
    </div>

    <div class="help-body">
      <!-- 分类侧边栏 -->
      <div class="category-sidebar">
        <div 
          v-for="cat in categories" 
          :key="cat.id"
          class="category-item"
          :class="{ 'active': activeCategory === cat.id }"
          @click="activeCategory = cat.id"
        >
          <el-icon><component :is="cat.icon" /></el-icon>
          <span>{{ cat.label }}</span>
          <el-icon class="arrow"><ArrowRight /></el-icon>
        </div>
      </div>

      <!-- 内容区域 -->
      <div class="content-area">
        <el-empty v-if="filteredContent.length === 0" description="没有找到相关内容" />

        <div v-else class="content-list">
          <el-collapse accordion>
            <el-collapse-item 
              v-for="(item, index) in filteredContent" 
              :key="index"
              :title="item.title"
              :name="index"
            >
              <div class="content-body" v-html="formatContent(item.content)"></div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </div>
    </div>

    <!-- 底部提示 -->
    <div class="help-footer">
      <el-card class="contact-card" shadow="never">
        <div class="contact-content">
          <div class="contact-icon"></div>
          <div class="contact-text">
            <h4>还有问题？</h4>
            <p>如果您在帮助中心没有找到答案，可以通过"联系导师"功能向导师咨询。</p>
          </div>
          <el-button type="primary" @click="$router.push('/chat')">
            联系导师
          </el-button>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script lang="ts">
// 格式化内容（Markdown 简单处理）
function formatContent(content: string): string {
  return content
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>')
    .replace(/- (.*?)(?=<br>|<\/p>|$)/g, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)+/g, '<ul>$&</ul>')
}

export default {
  methods: { formatContent }
}
</script>

<style scoped>
.help-center {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.help-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

.help-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: #1f2937;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
}

.search-box {
  width: 300px;
}

.help-body {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 1.5rem;
  min-height: 500px;
}

.category-sidebar {
  background: white;
  border-radius: 1rem;
  padding: 0.75rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  height: fit-content;
}

.category-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.875rem 1rem;
  border-radius: 0.75rem;
  cursor: pointer;
  color: #6b7280;
  transition: all 0.2s;
}

.category-item:hover {
  background: #f3f4f6;
  color: #374151;
}

.category-item.active {
  background: #eef2ff;
  color: #4f46e5;
  font-weight: 700;
}

.category-item .arrow {
  margin-left: auto;
  opacity: 0;
  transition: opacity 0.2s;
}

.category-item:hover .arrow,
.category-item.active .arrow {
  opacity: 1;
}

.content-area {
  background: white;
  border-radius: 1rem;
  padding: 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.content-list :deep(.el-collapse) {
  border: none;
}

.content-list :deep(.el-collapse-item__header) {
  font-size: 1rem;
  font-weight: 600;
  color: #374151;
  padding: 1rem 0;
  border-bottom: 1px solid #e5e7eb;
}

.content-list :deep(.el-collapse-item__content) {
  padding: 1rem 0;
}

.content-body {
  font-size: 0.9375rem;
  line-height: 1.75;
  color: #4b5563;
}

.content-body :deep(strong) {
  color: #1f2937;
}

.content-body :deep(ul) {
  margin: 0.5rem 0;
  padding-left: 1.25rem;
}

.content-body :deep(li) {
  margin: 0.25rem 0;
}

.help-footer {
  margin-top: 1rem;
}

.contact-card {
  border-radius: 1rem;
  border: 2px dashed #c7d2fe;
  background: #f0fdfa;
}

.contact-content {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.contact-icon {
  font-size: 2.5rem;
}

.contact-text {
  flex: 1;
}

.contact-text h4 {
  font-size: 1rem;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 0.25rem 0;
}

.contact-text p {
  font-size: 0.875rem;
  color: #6b7280;
  margin: 0;
}

@media (max-width: 768px) {
  .help-body {
    grid-template-columns: 1fr;
  }
  
  .category-sidebar {
    display: flex;
    overflow-x: auto;
    gap: 0.5rem;
    padding: 0.5rem;
  }
  
  .category-item {
    flex-shrink: 0;
    padding: 0.5rem 1rem;
  }
  
  .category-item .arrow {
    display: none;
  }
  
  .search-box {
    width: 100%;
  }
  
  .contact-content {
    flex-direction: column;
    text-align: center;
  }
}
</style>
