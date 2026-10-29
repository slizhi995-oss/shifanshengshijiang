<script setup lang="ts">
import { ref, onMounted, computed, nextTick, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatDotRound, Promotion, Search, ArrowDown, ArrowRight, Close } from '@element-plus/icons-vue'
import api from '@/utils/request'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

// 生成默认头像URL
const getAvatarUrl = (userCode: string) => {
  const seed = userCode || 'default'
  return `https://api.dicebear.com/7.x/notionists/svg?seed=${seed}&backgroundColor=b6e3f4,c0aede,d1d4f9`
}

// Tab切换：message(消息) 或 contact(联系人)
const activeTab = ref<'message' | 'contact'>('message')

// 批次列表和选择
const semesters = ref<any[]>([])
const selectedSemesterId = ref<number | null>(null)

// 联系人列表
const allContacts = ref<any[]>([]) // 所有联系人
const recentChats = ref<any[]>([]) // 最近聊天的人
const loading = ref(false)
const silentLoading = ref(false)

// 搜索关键词
const searchKeyword = ref('')

// 当前选中的联系人
const selectedContact = ref<any>(null)

// 聊天记录
const messages = ref<any[]>([])
const messagesLoading = ref(false)

// 发送消息
const messageInput = ref('')
const sending = ref(false)

// 消息容器引用
const messagesContainer = ref<HTMLElement | null>(null)

// 定时器
let refreshTimer: any = null

// 当前显示的联系人列表
const displayContacts = computed(() => {
  let list = activeTab.value === 'message' ? recentChats.value : allContacts.value
  
  if (!searchKeyword.value.trim()) {
    return list
  }
  
  const keyword = searchKeyword.value.toLowerCase()
  return list.filter(contact => {
    return (
      contact.user_name?.toLowerCase().includes(keyword) ||
      contact.user_code?.toLowerCase().includes(keyword) ||
      contact.semester_name?.toLowerCase().includes(keyword) ||
      contact.college?.toLowerCase().includes(keyword) ||
      contact.major?.toLowerCase().includes(keyword) ||
      contact.class_name?.toLowerCase().includes(keyword)
    )
  })
})

// 总未读数
const totalUnread = computed(() => {
  return recentChats.value.reduce((sum, contact) => sum + (contact.unread_count || 0), 0)
})

// 切换Tab
const switchTab = async (tab: 'message' | 'contact') => {
  activeTab.value = tab
  searchKeyword.value = ''
  if (tab === 'contact') {
    if (!selectedSemesterId.value && semesters.value.length > 0) {
      // 默认选择第一个活跃批次
      const active = semesters.value.find(s => s.status === 'active')
      selectedSemesterId.value = active?.id || semesters.value[0]?.id
    }
    if (selectedSemesterId.value) {
      await fetchContactsBySemester()
    }
  }
}

// 切换批次
const handleSemesterChange = async () => {
  if (selectedSemesterId.value) {
    await fetchContactsBySemester()
  }
}

// 获取批次列表
const fetchSemesters = async () => {
  try {
    const res: any = await api.get('/semesters')
    semesters.value = res
  } catch (error) {}
}

// 获取所有联系人（用于消息Tab）
const fetchAllContacts = async (silent = false) => {
  if (!silent) loading.value = true
  
  try {
    const res: any = await api.get('/chat/contacts')
    
    // 获取有消息的联系人
    const hasMessageContacts = res.filter((c: any) => c.last_message || c.unread_count > 0)
    
    // 使用Map合并：保留当前消息列表中的所有联系人，用新数据更新
    const mergedMap = new Map()
    
    // 1. 先添加当前消息列表中的所有联系人（保留临时添加的）
    recentChats.value.forEach((c: any) => {
      mergedMap.set(c.user_id, c)
    })
    
    // 2. 用后端返回的数据更新/添加联系人
    hasMessageContacts.forEach((c: any) => {
      // 如果已存在，更新数据；如果不存在，添加新的
      mergedMap.set(c.user_id, c)
    })
    
    // 3. 确保当前选中的联系人在列表中
    if (selectedContact.value && !mergedMap.has(selectedContact.value.user_id)) {
      const currentContact = res.find((c: any) => c.user_id === selectedContact.value.user_id)
      if (currentContact) {
        mergedMap.set(currentContact.user_id, currentContact)
      }
    }
    
    // 4. 不清理临时联系人，全部保留（让用户主动删除）
    const cleanedList: any[] = Array.from(mergedMap.values())
    
    // 5. 排序：完全按消息时间倒序，最新消息在最前
    cleanedList.sort((a, b) => {
      const timeA = a.last_message_time ? new Date(a.last_message_time).getTime() : 0
      const timeB = b.last_message_time ? new Date(b.last_message_time).getTime() : 0
      return timeB - timeA
    })
    
    recentChats.value = cleanedList
    
    // 如果有选中的联系人，更新其信息
    if (selectedContact.value) {
      const updated = res.find((c: any) => c.user_id === selectedContact.value.user_id)
      if (updated) {
        selectedContact.value = updated
      }
    }
  } finally {
    loading.value = false
  }
}

// 根据批次获取联系人（用于联系人Tab）
const fetchContactsBySemester = async () => {
  if (!selectedSemesterId.value) return
  
  loading.value = true
  try {
    const res: any = await api.get('/chat/contacts')
    // 过滤指定批次的联系人
    allContacts.value = res.filter((c: any) => c.semester_id === selectedSemesterId.value)
  } finally {
    loading.value = false
  }
}

// 选择联系人
const selectContact = async (contact: any) => {
  selectedContact.value = contact
  
  // 如果是从联系人Tab点击的，自动跳转到消息Tab
  if (activeTab.value === 'contact') {
    activeTab.value = 'message'
    
    // 确保该联系人在消息列表中（不置顶，按时间排序）
    const exists = recentChats.value.find(c => c.user_id === contact.user_id)
    if (!exists) {
      recentChats.value.push(contact)
      // 重新排序：按消息时间倒序
      recentChats.value.sort((a, b) => {
        const timeA = a.last_message_time ? new Date(a.last_message_time).getTime() : 0
        const timeB = b.last_message_time ? new Date(b.last_message_time).getTime() : 0
        return timeB - timeA
      })
    }
  }
  
  await fetchMessages()
}

// 从消息列表删除联系人（不删除聊天记录）
const removeFromRecentChats = async (contact: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要将"${contact.user_name}"从消息列表移除吗？聊天记录不会被删除，您可以从联系人列表重新找到TA。`,
      '移除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    recentChats.value = recentChats.value.filter(c => c.user_id !== contact.user_id)
    
    // 如果删除的是当前选中的，清空选中
    if (selectedContact.value?.user_id === contact.user_id) {
      selectedContact.value = null
      messages.value = []
    }
    
    ElMessage.success('已从消息列表移除')
  } catch {
    // 用户取消
  }
}

// 获取聊天记录
const fetchMessages = async (silent = false) => {
  if (!selectedContact.value) return
  
  if (!silent) {
    messagesLoading.value = true
  }
  
  try {
    const res: any = await api.get(`/chat/conversations/${selectedContact.value.user_id}`, {
      params: { page: 1, page_size: 100 }
    })
    
    const oldLength = messages.value.length
    messages.value = res.messages
    
    // 只在新消息到达或首次加载时滚动
    if (!silent || messages.value.length > oldLength) {
      await nextTick()
      scrollToBottom()
    }
    
    // 静默刷新联系人列表（更新未读数）
    if (!silent) {
      await fetchAllContacts(true)
    }
  } finally {
    messagesLoading.value = false
  }
}

// 发送消息
const sendMessage = async () => {
  if (!messageInput.value.trim() || !selectedContact.value || sending.value) return
  
  const content = messageInput.value.trim()
  messageInput.value = '' // 立即清空输入框
  
  sending.value = true
  try {
    const res: any = await api.post('/chat/send', {
      receiver_id: selectedContact.value.user_id,
      content: content,
      semester_id: selectedContact.value.semester_id
    })
    
    // 添加到消息列表
    messages.value.push(res)
    
    // 滚动到底部
    await nextTick()
    scrollToBottom()
    
    // 更新当前联系人的消息信息并重新排序
    if (selectedContact.value) {
      const updatedContact = {
        ...selectedContact.value,
        last_message: content,
        last_message_time: new Date().toISOString()
      }
      
      // 在列表中找到并更新
      const index = recentChats.value.findIndex(c => c.user_id === selectedContact.value.user_id)
      if (index !== -1) {
        recentChats.value[index] = updatedContact
      } else {
        recentChats.value.push(updatedContact)
      }
      
      // 按消息时间重新排序
      recentChats.value.sort((a, b) => {
        const timeA = a.last_message_time ? new Date(a.last_message_time).getTime() : 0
        const timeB = b.last_message_time ? new Date(b.last_message_time).getTime() : 0
        return timeB - timeA
      })
      
      selectedContact.value = updatedContact
    }
    
    // 静默刷新联系人列表（更新未读数等）
    await fetchAllContacts(true)
  } catch (error) {
    // 发送失败，恢复输入
    messageInput.value = content
  } finally {
    sending.value = false
  }
}

// 滚动到底部
const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// 格式化时间
const formatTime = (dateStr: string) => {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  
  // 1分钟内
  if (diff < 60 * 1000) {
    return '刚刚'
  }
  
  // 1小时内
  if (diff < 60 * 60 * 1000) {
    return `${Math.floor(diff / (60 * 1000))}分钟前`
  }
  
  // 今天
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  
  // 昨天
  const yesterday = new Date(now)
  yesterday.setDate(yesterday.getDate() - 1)
  if (date.toDateString() === yesterday.toDateString()) {
    return '昨天 ' + date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  
  // 其他
  return date.toLocaleString('zh-CN', { 
    month: '2-digit', 
    day: '2-digit', 
    hour: '2-digit', 
    minute: '2-digit' 
  })
}

// 定时刷新（静默模式，不显示loading）
const startAutoRefresh = () => {
  refreshTimer = setInterval(() => {
    // 总是静默刷新消息列表（更新未读数等）
    fetchAllContacts(true)
    
    // 如果有选中的联系人，静默刷新聊天记录
    if (selectedContact.value) {
      fetchMessages(true)
    }
  }, 5000)
}

// 停止刷新
const stopAutoRefresh = () => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

// Enter发送消息
const handleKeyDown = (event: Event | KeyboardEvent) => {
  if (event instanceof KeyboardEvent && event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    sendMessage()
  }
}

onMounted(async () => {
  await fetchSemesters()
  await fetchAllContacts()
  startAutoRefresh()
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<template>
  <div class="h-full flex flex-col bg-gray-50">
    <div class="mb-4 px-6 pt-4">
      <h2 class="text-2xl font-bold text-gray-800">师生联系</h2>
    </div>
    
    <div class="flex-1 flex gap-4 overflow-hidden px-6 pb-6">
      <!-- 左侧：消息/联系人列表 -->
      <el-card class="w-80 flex flex-col border-none shadow-lg rounded-xl" body-style="flex: 1; display: flex; flex-direction: column; overflow: hidden; padding: 0;">
        <!-- Tab切换 -->
        <div class="border-b bg-white">
          <div class="flex">
            <div 
              class="flex-1 py-4 px-4 cursor-pointer text-center relative transition-all duration-300"
              :class="activeTab === 'message' ? 'text-blue-600 font-bold bg-blue-50/50' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-700'"
              @click="switchTab('message')"
            >
              <span class="text-sm">消息</span>
              <el-badge 
                v-if="totalUnread > 0" 
                :value="totalUnread" 
                :max="99"
                class="ml-2 transform scale-90"
                type="danger"
              />
              <div v-if="activeTab === 'message'" class="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600 mx-8 rounded-t-full"></div>
            </div>
            <div 
              class="flex-1 py-4 px-4 cursor-pointer text-center relative transition-all duration-300"
              :class="activeTab === 'contact' ? 'text-blue-600 font-bold bg-blue-50/50' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-700'"
              @click="switchTab('contact')"
            >
              <span class="text-sm">联系人</span>
              <div v-if="activeTab === 'contact'" class="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600 mx-8 rounded-t-full"></div>
            </div>
          </div>
        </div>
        
        <!-- 内容区 -->
        <div class="flex-1 flex flex-col overflow-hidden bg-white">
          <!-- 搜索和筛选区 -->
          <div class="p-4 space-y-3 bg-white z-10">
            <!-- 联系人Tab：批次选择器 -->
            <div v-if="activeTab === 'contact'">
              <el-select
                v-model="selectedSemesterId"
                placeholder="选择批次"
                @change="handleSemesterChange"
                class="w-full"
                size="default"
              >
                <template #prefix>
                  <el-icon><Files /></el-icon>
                </template>
                <el-option
                  v-for="s in semesters"
                  :key="s.id"
                  :label="s.name"
                  :value="s.id"
                >
                  <span class="flex items-center justify-between w-full">
                    <span>{{ s.name }}</span>
                    <el-tag v-if="s.status === 'active'" size="small" type="success" effect="plain" round>进行中</el-tag>
                  </span>
                </el-option>
              </el-select>
            </div>
            
            <!-- 搜索框 -->
            <div class="relative">
              <el-input
                v-model="searchKeyword"
                :prefix-icon="Search"
                :placeholder="activeTab === 'message' ? '搜索消息记录' : '搜索联系人'"
                clearable
                class="custom-input"
              />
            </div>
          </div>
          
          <!-- 列表区域 -->
          <div v-loading="loading" class="flex-1 overflow-y-auto custom-scrollbar">
            <!-- 空状态 -->
            <div v-if="displayContacts.length === 0" class="flex flex-col items-center justify-center h-64 text-gray-400">
              <el-icon :size="48" class="mb-2 opacity-20"><User /></el-icon>
              <p class="text-xs">
                <template v-if="activeTab === 'message'">
                  {{ searchKeyword ? '无匹配结果' : '暂无消息记录' }}
                </template>
                <template v-else>
                  {{ searchKeyword ? '无匹配结果' : selectedSemesterId ? '该批次暂无联系人' : '请选择批次' }}
                </template>
              </p>
            </div>
            
            <!-- 联系人列表 -->
            <div v-else class="divide-y divide-gray-50">
              <div
                v-for="contact in displayContacts"
                :key="contact.user_id"
                class="p-3 cursor-pointer hover:bg-blue-50/50 transition-all duration-200 relative group mx-2 my-1 rounded-lg border border-transparent hover:border-blue-100"
                :class="{ 
                  'bg-blue-50 border-blue-200 shadow-sm': selectedContact?.user_id === contact.user_id
                }"
                @click="selectContact(contact)"
              >
                <!-- 删除按钮（仅消息Tab显示） -->
                <div 
                  v-if="activeTab === 'message'"
                  class="absolute right-2 top-2 opacity-0 group-hover:opacity-100 transition-all duration-200 z-10"
                >
                  <div 
                    class="w-6 h-6 flex items-center justify-center rounded-full bg-gray-200 hover:bg-red-500 hover:text-white text-gray-500 cursor-pointer shadow-sm"
                    @click.stop="removeFromRecentChats(contact)"
                    title="从消息列表移除"
                  >
                    <el-icon :size="12"><Close /></el-icon>
                  </div>
                </div>
                
                <div class="flex items-start gap-3">
                  <!-- 头像 -->
                  <div class="relative">
                    <el-avatar 
                      :size="44" 
                      :src="getAvatarUrl(contact.user_code)"
                      class="border-2 border-white shadow-sm transition-transform group-hover:scale-105 bg-cyan-50"
                    />
                    <span 
                      v-if="activeTab === 'message' && contact.unread_count > 0"
                      class="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white shadow-sm border-2 border-white"
                    >
                      {{ contact.unread_count > 99 ? '99+' : contact.unread_count }}
                    </span>
                  </div>
                  
                  <!-- 联系人信息 -->
                  <div class="flex-1 min-w-0 pt-0.5">
                    <div class="flex items-center justify-between mb-1">
                      <div class="flex items-center gap-2">
                        <span class="font-bold text-gray-800 text-sm truncate">{{ contact.user_name }}</span>
                        <span 
                          class="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
                          :class="contact.role === 'instructor' ? 'bg-blue-100 text-blue-600' : 'bg-green-100 text-green-600'"
                        >
                          {{ contact.role === 'instructor' ? '老师' : '学生' }}
                        </span>
                      </div>
                      <div v-if="contact.last_message_time" class="text-[10px] text-gray-400 font-medium tabular-nums">
                        {{ formatTime(contact.last_message_time) }}
                      </div>
                    </div>
                    
                    <div class="text-[10px] text-gray-400 mb-1 truncate">
                      {{ contact.user_code }}
                      <template v-if="contact.college"> · {{ contact.college }}</template>
                    </div>
                    
                    <div 
                      v-if="contact.last_message" 
                      class="text-xs text-gray-500 truncate pr-6"
                      :class="{ 'font-medium text-gray-800': contact.unread_count > 0 }"
                    >
                      {{ contact.last_message }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </el-card>
      
      <!-- 右侧：聊天窗口 -->
      <el-card class="flex-1 flex flex-col border-none shadow-lg rounded-xl" body-style="flex: 1; display: flex; flex-direction: column; overflow: hidden; padding: 0;">
        <template #header>
          <div class="flex items-center justify-between py-1">
            <div v-if="selectedContact" class="flex items-center gap-3">
              <div class="relative">
                <el-avatar 
                  :size="40" 
                  :src="getAvatarUrl(selectedContact.user_code)"
                  class="border-2 border-white shadow-sm bg-cyan-50"
                />
                <span class="absolute bottom-0 right-0 block h-2.5 w-2.5 rounded-full bg-green-500 ring-2 ring-white"></span>
              </div>
              <div>
                <div class="flex items-center gap-2">
                  <span class="font-bold text-gray-800">{{ selectedContact.user_name }}</span>
                  <span 
                    class="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
                    :class="selectedContact.role === 'instructor' ? 'bg-blue-100 text-blue-600' : 'bg-green-100 text-green-600'"
                  >
                    {{ selectedContact.role === 'instructor' ? '指导老师' : '学生' }}
                  </span>
                </div>
                <div class="text-xs text-gray-500 mt-0.5 flex items-center gap-1">
                  <span>{{ selectedContact.user_code }}</span>
                  <span v-if="selectedContact.semester_name" class="text-gray-300">|</span>
                  <span v-if="selectedContact.semester_name">{{ selectedContact.semester_name }}</span>
                </div>
              </div>
            </div>
            <div v-else class="text-gray-400 text-sm font-medium">未选择联系人</div>
            
            <div v-if="selectedContact">
              <el-button circle text size="small">
                <el-icon><MoreFilled /></el-icon>
              </el-button>
            </div>
          </div>
        </template>
        
        <div v-if="!selectedContact" class="flex-1 flex flex-col items-center justify-center text-gray-300 bg-gray-50/50">
          <div class="w-32 h-32 bg-gray-100 rounded-full flex items-center justify-center mb-6 shadow-inner">
            <el-icon :size="64" class="opacity-50"><ChatDotRound /></el-icon>
          </div>
          <div class="text-lg font-medium text-gray-400">选择一个联系人开始聊天</div>
          <div class="text-sm text-gray-400 mt-2">点击左侧列表选择联系人</div>
        </div>
        
        <div v-else class="flex-1 flex flex-col overflow-hidden bg-[#f8fafc]">
          <!-- 消息列表 -->
          <div 
            ref="messagesContainer"
            v-loading="messagesLoading" 
            class="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar"
          >
            <div v-if="messages.length === 0" class="flex flex-col items-center justify-center py-12 text-gray-400">
              <div class="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-3">
                <el-icon :size="32"><ChatLineRound /></el-icon>
              </div>
              <span class="text-sm">暂无消息记录，打个招呼吧</span>
            </div>
            
            <div
              v-for="(msg, index) in messages"
              :key="msg.id"
              class="flex flex-col gap-1"
            >
              <!-- 时间分割线 -->
              <div 
                v-if="index === 0 || new Date(msg.created_at).getTime() - new Date(messages[index-1].created_at).getTime() > 300000" 
                class="flex justify-center my-4"
              >
                <span class="text-[10px] bg-gray-200 text-gray-500 px-2 py-1 rounded-full shadow-sm">
                  {{ formatTime(msg.created_at) }}
                </span>
              </div>

              <div 
                class="flex gap-3 max-w-[85%]"
                :class="msg.sender_id === authStore.user?.id ? 'self-end flex-row-reverse' : 'self-start'"
              >
                <!-- 头像 -->
                <div class="flex-shrink-0 mt-1">
                  <el-avatar 
                    :size="36" 
                    :src="getAvatarUrl(msg.sender_id === authStore.user?.id ? authStore.user?.user_code : selectedContact.user_code)"
                    class="shadow-sm border border-white bg-cyan-50"
                  />
                </div>
                
                <!-- 消息内容 -->
                <div class="flex flex-col" :class="msg.sender_id === authStore.user?.id ? 'items-end' : 'items-start'">
                  <!-- 消息气泡 -->
                  <div
                    class="px-4 py-2.5 rounded-2xl shadow-sm text-sm leading-relaxed relative group transition-all duration-200"
                    :class="msg.sender_id === authStore.user?.id 
                      ? 'bg-blue-600 text-white rounded-tr-none hover:bg-blue-700' 
                      : 'bg-white text-gray-800 rounded-tl-none border border-gray-100 hover:bg-gray-50'"
                  >
                    <div class="whitespace-pre-wrap break-words">{{ msg.content }}</div>
                  </div>
                  
                  <!-- 状态 -->
                  <div 
                    v-if="msg.sender_id === authStore.user?.id" 
                    class="text-[10px] mt-1 px-1 flex items-center gap-1 opacity-60 transition-opacity"
                  >
                    <span :class="msg.is_read ? 'text-blue-500' : 'text-gray-400'">
                      {{ msg.is_read ? '已读' : '送达' }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          <!-- 输入框 -->
          <div class="bg-white border-t border-gray-100 p-4 shadow-[0_-4px_20px_-5px_rgba(0,0,0,0.05)] z-10">
            <div class="relative">
              <el-input
                v-model="messageInput"
                type="textarea"
                :rows="3"
                placeholder="输入消息..."
                :disabled="sending"
                @keydown="handleKeyDown"
                class="custom-textarea"
                resize="none"
              />
              <div class="absolute bottom-2 right-2 flex items-center gap-3">
                <span class="text-[10px] text-gray-400 bg-gray-50 px-2 py-1 rounded border border-gray-100">
                  Enter 发送
                </span>
                <el-button
                  type="primary"
                  :icon="Promotion"
                  :loading="sending"
                  :disabled="!messageInput.trim()"
                  @click="sendMessage"
                  circle
                  class="shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-200"
                />
              </div>
            </div>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
/* 自定义滚动条 */
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #e2e8f0;
  border-radius: 3px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #cbd5e1;
}

/* 消息气泡动画 */
.flex.gap-3 {
  animation: slideIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* 输入框样式 */
:deep(.custom-textarea .el-textarea__inner) {
  border: none;
  background-color: #f8fafc;
  padding: 12px;
  padding-bottom: 40px;
  border-radius: 12px;
  transition: all 0.2s;
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.05);
}

:deep(.custom-textarea .el-textarea__inner:focus) {
  background-color: #fff;
  box-shadow: inset 0 0 0 2px #3b82f6, 0 4px 12px rgba(59, 130, 246, 0.1);
}

:deep(.el-card) {
  transition: all 0.3s ease;
}
</style>
