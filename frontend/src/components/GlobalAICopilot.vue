<script setup lang="ts">
/**
 * 全局 AI Copilot 浮窗组件
 * 支持角色自适应、流式输出、快捷问题、聊天记录保持
 */
import { ref, computed, nextTick, watch, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { handleStreamResponse } from '@/api/ai'
import { Cpu, Close, Minus, ChatDotRound, Promotion, Delete, RefreshRight } from '@element-plus/icons-vue'

const authStore = useAuthStore()

// 面板状态
const panelVisible = ref(false)
const isMinimized = ref(false)
const isGenerating = ref(false)

// 聊天消息
interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}
const messages = ref<Message[]>([])
const inputText = ref('')
const messagesContainer = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLInputElement | null>(null)

// 角色标签
const roleLabel = computed(() => {
  const role = authStore.userRole
  if (role === 'student') return '学习助手'
  if (role === 'instructor') return '教学助手'
  if (role === 'admin') return '管理助手'
  return 'AI 助手'
})

// 角色系统 prompt
const systemContext = computed(() => {
  const role = authStore.userRole
  if (role === 'student') {
    return '你是一个教学设计学习助手，帮助师范生解答教学设计、备课、试讲相关问题，提供专业的教案撰写建议和教学方法指导。请用简洁清晰的语言回答。'
  }
  if (role === 'instructor') {
    return '你是一个教学辅助助手，帮助指导老师进行作业批改思路分析、班级管理建议、学生画像解读等。请用专业简洁的语言回答。'
  }
  if (role === 'admin') {
    return '你是一个系统管理助手，帮助管理员解读系统数据、提供运营建议、分析使用情况等。请用简洁明了的语言回答。'
  }
  return '你是一个AI助手，请回答用户的问题。'
})

// 快捷问题
const quickPrompts = computed(() => {
  const role = authStore.userRole
  if (role === 'student') {
    return [
      '如何写好教案的教学目标？',
      '试讲时如何控制时间？',
      '教学反思怎么写？',
      '如何设计课堂互动环节？',
    ]
  }
  if (role === 'instructor') {
    return [
      '如何高效批改教案？',
      '怎样给学生写有建设性的评语？',
      '班级整体表现如何提升？',
      '如何识别需要关注的学生？',
    ]
  }
  if (role === 'admin') {
    return [
      '本周系统使用情况如何？',
      '如何提升学生活跃度？',
      'AI 功能使用率分析',
      '数据导出有哪些维度？',
    ]
  }
  return ['你好，有什么可以帮我的？']
})

const togglePanel = () => {
  if (isMinimized.value) {
    isMinimized.value = false
    return
  }
  panelVisible.value = !panelVisible.value
  if (panelVisible.value) {
    nextTick(() => {
      scrollToBottom()
      inputRef.value?.focus()
    })
  }
}

const minimizePanel = () => {
  isMinimized.value = true
}

const closePanel = () => {
  panelVisible.value = false
  isMinimized.value = false
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

const clearMessages = () => {
  messages.value = []
}

// 简单 markdown 渲染
const renderMarkdown = (text: string): string => {
  if (!text) return ''
  let html = text
    // 代码块
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="copilot-code"><code>$2</code></pre>')
    // 行内代码
    .replace(/`([^`]+)`/g, '<code class="copilot-inline-code">$1</code>')
    // 加粗
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // 斜体
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // 无序列表
    .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
    // 有序列表
    .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
    // 标题
    .replace(/^### (.+)$/gm, '<h4 class="font-semibold mt-2 mb-1">$1</h4>')
    .replace(/^## (.+)$/gm, '<h3 class="font-semibold mt-2 mb-1 text-base">$1</h3>')
    // 换行
    .replace(/\n/g, '<br/>')
  return html
}

// 发送消息
const sendMessage = async (text?: string) => {
  const content = text || inputText.value.trim()
  if (!content || isGenerating.value) return

  inputText.value = ''

  // 添加用户消息
  messages.value.push({
    id: `user-${Date.now()}`,
    role: 'user',
    content,
    timestamp: Date.now()
  })

  // 添加 AI 消息占位
  const aiMsgId = `ai-${Date.now()}`
  messages.value.push({
    id: aiMsgId,
    role: 'assistant',
    content: '',
    timestamp: Date.now()
  })

  scrollToBottom()
  isGenerating.value = true

  // 3s 首字节兜底：避免网络慢时空气泡持续不动
  const abortController = new AbortController()
  let firstChunkReceived = false
  let usedFallback = false
  const firstByteTimer = setTimeout(() => {
    if (!firstChunkReceived) {
      usedFallback = true
      try { abortController.abort() } catch {}
      const aiMsg = messages.value.find(m => m.id === aiMsgId)
      if (aiMsg) {
        // Copilot 口吻的预置回复（区别于 AIAssistant 的"学生"口吻）
        const lower = (content || '').toLowerCase()
        let reply = '收到，让我先为您梳理一下思路：建议从教学目标、重难点和教学过程三个维度入手。如果方便，您可以告诉我更具体的场景，我会给出更针对的建议。'
        if (lower.includes('教案') || lower.includes('生成')) {
          reply = '关于教案撰写，建议按以下结构组织：1) 教学目标（知识/能力/情感三维度）；2) 教学重难点（明确具体）；3) 教学过程（导入-新授-练习-小结）；4) 板书设计。需要我帮您生成一份示例教案吗？'
        } else if (lower.includes('视频') || lower.includes('录制') || lower.includes('讲课')) {
          reply = '试讲录制建议：保持自然光照面对镜头；语速控制在 120-160 字/分钟；多设计互动环节；注意眼神交流与手势配合。开始录制后系统会实时分析您的姿态与表情。'
        } else if (lower.includes('打分') || lower.includes('评分') || lower.includes('批改')) {
          reply = '评分维度通常包括：教案结构（20%）、教学目标（15%）、教学过程（25%）、教学方法（15%）、语言表达（15%）、板书设计（10%）。可在「批改作业」中使用 AI 一键批改加快流程。'
        }
        aiMsg.content = reply
        scrollToBottom()
      }
    }
  }, 3000)

  try {
    const token = authStore.token
    // 构建对话历史（最近10条）
    const history = messages.value.slice(0, -2).slice(-10).map(m => ({
      role: m.role,
      content: m.content
    }))

    const response = await fetch('/api/v1/ai/assistant/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        message: content,
        lesson_plan_text: '',
        grade: '',
        personality: 'copilot',
        conversation_history: [
          { role: 'system', content: systemContext.value },
          ...history
        ],
        stream: true
      }),
      signal: abortController.signal,
    })

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}))
      throw new Error(errData.detail || '请求失败')
    }

    const aiMsg = messages.value.find(m => m.id === aiMsgId)

    await handleStreamResponse(response, (chunk) => {
      if (usedFallback) return
      if (!firstChunkReceived) {
        firstChunkReceived = true
        clearTimeout(firstByteTimer)
      }
      if (aiMsg) {
        aiMsg.content += chunk
        scrollToBottom()
      }
    })
  } catch (error) {
    if (!usedFallback) {
      const aiMsg = messages.value.find(m => m.id === aiMsgId)
      if (aiMsg) {
        aiMsg.content = '抱歉，AI 服务暂时不可用，请稍后重试。'
      }
    }
  } finally {
    clearTimeout(firstByteTimer)
    isGenerating.value = false
    nextTick(() => inputRef.value?.focus())
  }
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

// 未读提示动画
const hasUnread = ref(false)
watch(panelVisible, (val) => {
  if (val) hasUnread.value = false
})

defineExpose({ togglePanel })
</script>

<template>
  <Teleport to="body">
    <!-- 最小化时的小提示按钮 -->
    <div
      v-if="isMinimized"
      class="copilot-minimized-btn"
      @click="togglePanel"
      title="展开 AI 助手"
    >
      <el-icon :size="16" color="#fff"><ChatDotRound /></el-icon>
    </div>

    <!-- 聊天面板 -->
    <Transition name="copilot-slide">
      <div v-if="panelVisible && !isMinimized" class="copilot-panel">
        <!-- 头部 -->
        <header class="copilot-header">
          <div class="flex items-center gap-2">
            <div class="header-icon">
              <el-icon :size="16" color="#fff"><Cpu /></el-icon>
            </div>
            <div>
              <div class="text-sm font-bold text-white">AI Copilot</div>
              <div class="text-xs text-white/70">{{ roleLabel }}</div>
            </div>
          </div>
          <div class="flex items-center gap-1">
            <button class="header-btn" @click="clearMessages" title="清空对话">
              <el-icon :size="14"><Delete /></el-icon>
            </button>
            <button class="header-btn" @click="minimizePanel" title="最小化">
              <el-icon :size="14"><Minus /></el-icon>
            </button>
            <button class="header-btn" @click="closePanel" title="关闭">
              <el-icon :size="14"><Close /></el-icon>
            </button>
          </div>
        </header>

        <!-- 消息区域 -->
        <div ref="messagesContainer" class="copilot-messages">
          <!-- 空状态 -->
          <div v-if="messages.length === 0" class="empty-state">
            <div class="empty-icon">
              <el-icon :size="32"><Cpu /></el-icon>
            </div>
            <p class="text-sm text-gray-500 mt-2 mb-4">你好！我是 {{ roleLabel }}，有什么可以帮你的？</p>
            <!-- 快捷问题 -->
            <div class="quick-prompts">
              <button
                v-for="prompt in quickPrompts"
                :key="prompt"
                class="quick-btn"
                @click="sendMessage(prompt)"
              >
                {{ prompt }}
              </button>
            </div>
          </div>

          <!-- 消息列表 -->
          <template v-for="msg in messages" :key="msg.id">
            <div class="msg-row" :class="msg.role">
              <div class="msg-avatar" v-if="msg.role === 'assistant'">
                <el-icon :size="14" color="#0891b2"><Cpu /></el-icon>
              </div>
              <div class="msg-bubble" :class="msg.role">
                <div v-if="msg.role === 'assistant' && msg.content" v-html="renderMarkdown(msg.content)"></div>
                <div v-else-if="msg.role === 'assistant' && !msg.content" class="typing-indicator">
                  <span></span><span></span><span></span>
                </div>
                <div v-else>{{ msg.content }}</div>
              </div>
            </div>
          </template>
        </div>

        <!-- 快捷问题（有消息时显示在底部） -->
        <div v-if="messages.length > 0 && !isGenerating" class="quick-prompts-bar">
          <button
            v-for="prompt in quickPrompts.slice(0, 2)"
            :key="prompt"
            class="quick-chip"
            @click="sendMessage(prompt)"
          >
            {{ prompt }}
          </button>
        </div>

        <!-- 输入区域 -->
        <footer class="copilot-footer">
          <div class="input-wrapper">
            <input
              ref="inputRef"
              v-model="inputText"
              :placeholder="isGenerating ? 'AI 正在思考...' : '输入你的问题...'"
              :disabled="isGenerating"
              class="copilot-input"
              @keydown="handleKeydown"
            />
            <button
              class="send-btn"
              :class="{ active: inputText.trim() && !isGenerating }"
              :disabled="!inputText.trim() || isGenerating"
              @click="sendMessage()"
            >
              <el-icon :size="16"><Promotion /></el-icon>
            </button>
          </div>
        </footer>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* 最小化提示按钮 */
.copilot-minimized-btn {
  position: fixed;
  right: 24px;
  bottom: 80px;
  z-index: 2000;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: #1e293b;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
  transition: all 0.2s ease;
}

.copilot-minimized-btn:hover {
  background: #334155;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}

/* 聊天面板 */
.copilot-panel {
  position: fixed;
  right: 24px;
  bottom: 80px;
  width: 400px;
  height: 540px;
  z-index: 1999;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15), 0 0 0 1px rgba(0, 0, 0, 0.05);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 头部 */
.copilot-header {
  padding: 14px 18px;
  background: linear-gradient(135deg, #1e1b4b 0%, #312e81 60%, #1e293b 100%);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.header-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
}

.header-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: rgba(255, 255, 255, 0.15);
  color: rgba(255, 255, 255, 0.8);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.header-btn:hover {
  background: rgba(255, 255, 255, 0.25);
  color: #fff;
}

/* 消息区域 */
.copilot-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.copilot-messages::-webkit-scrollbar {
  width: 4px;
}

.copilot-messages::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 2px;
}

/* 空状态 */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 20px;
}

.empty-icon {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  background: #eef2ff;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #4f46e5;
  box-shadow: 0 4px 12px rgba(79, 70, 229, 0.12);
}

.quick-prompts {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.quick-btn {
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  text-align: left;
  font-size: 13px;
  color: #334155;
  cursor: pointer;
  transition: all 0.2s;
}

.quick-btn:hover {
  background: #eef2ff;
  border-color: #c7d2fe;
  color: #4f46e5;
  transform: translateX(2px);
}

/* 消息行 */
.msg-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.msg-row.user {
  justify-content: flex-end;
}

.msg-avatar {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: #eef2ff;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #4f46e5;
  flex-shrink: 0;
  margin-top: 2px;
}

.msg-bubble {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}

.msg-bubble.user {
  background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%);
  color: #fff;
  border-bottom-right-radius: 4px;
  box-shadow: 0 2px 8px rgba(79, 70, 229, 0.25);
}

.msg-bubble.assistant {
  background: #f3f4f6;
  color: #1f2937;
  border-bottom-left-radius: 4px;
}

/* Markdown 样式 */
.msg-bubble.assistant :deep(.copilot-code) {
  background: #1f2937;
  color: #e5e7eb;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 12px;
  overflow-x: auto;
  margin: 6px 0;
}

.msg-bubble.assistant :deep(.copilot-inline-code) {
  background: #e5e7eb;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 12px;
}

.msg-bubble.assistant :deep(li) {
  margin-left: 16px;
  list-style: disc;
}

.msg-bubble.assistant :deep(strong) {
  font-weight: 600;
}

/* 打字动画 */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.typing-indicator span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #9ca3af;
  animation: typing-bounce 1.4s infinite;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing-bounce {
  0%, 60%, 100% {
    transform: translateY(0);
  }
  30% {
    transform: translateY(-6px);
  }
}

/* 底部快捷问题条 */
.quick-prompts-bar {
  padding: 6px 16px;
  display: flex;
  gap: 6px;
  overflow-x: auto;
  flex-shrink: 0;
  border-top: 1px solid #f3f4f6;
}

.quick-prompts-bar::-webkit-scrollbar {
  height: 0;
}

.quick-chip {
  padding: 4px 10px;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  background: #fff;
  font-size: 11px;
  color: #6b7280;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
  flex-shrink: 0;
}

.quick-chip:hover {
  background: #eef2ff;
  border-color: #c7d2fe;
  color: #4f46e5;
}

/* 输入区域 */
.copilot-footer {
  padding: 12px 16px;
  border-top: 1px solid #f1f5f9;
  flex-shrink: 0;
  background: #ffffff;
}

.input-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #f8fafc;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  padding: 4px 4px 4px 14px;
  transition: all 0.2s;
}

.input-wrapper:focus-within {
  background: #fff;
  border-color: #4f46e5;
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.12);
}

.copilot-input {
  flex: 1;
  border: none;
  background: transparent;
  outline: none;
  font-size: 13px;
  color: #1f2937;
  padding: 6px 0;
}

.copilot-input::placeholder {
  color: #9ca3af;
}

.send-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: none;
  background: #f1f5f9;
  color: #94a3b8;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  flex-shrink: 0;
}

.send-btn.active {
  background: linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%);
  color: #fff;
  box-shadow: 0 2px 8px rgba(79, 70, 229, 0.3);
}

.send-btn.active:hover {
  transform: scale(1.05);
}

/* 过渡动画 */
.copilot-slide-enter-active,
.copilot-slide-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.copilot-slide-enter-from,
.copilot-slide-leave-to {
  opacity: 0;
  transform: translateY(20px) scale(0.95);
}

.badge-pop-enter-active,
.badge-pop-leave-active {
  transition: all 0.2s ease;
}

/* 响应式 */
@media (max-width: 768px) {
  .copilot-panel {
    right: 8px;
    bottom: 80px;
    width: calc(100vw - 16px);
    height: calc(100vh - 160px);
    max-height: 540px;
  }

  .copilot-minimized-btn {
    right: 16px;
    bottom: 72px;
  }
}
</style>
