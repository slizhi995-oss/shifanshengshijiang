<script setup lang="ts">
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Promotion, ChatDotSquare } from '@element-plus/icons-vue'
import api from '@/utils/request'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const messages = ref<any[]>([])
const contacts = ref<any[]>([])
const selectedContact = ref<any>(null)
const loading = ref(false)
const messageInput = ref('')
const messagesContainer = ref<HTMLElement | null>(null)

// 生成默认头像URL
const getAvatarUrl = (userCode: string) => {
  const seed = userCode || 'default'
  return `https://api.dicebear.com/7.x/notionists/svg?seed=${seed}&backgroundColor=b6e3f4,c0aede,d1d4f9`
}

const fetchContacts = async () => {
  try {
    const res: any = await api.get('/messages/contacts')
    contacts.value = res
    if (res.length > 0 && !selectedContact.value) {
      selectedContact.value = res[0]
      fetchMessages()
    }
  } catch (error) {}
}

const fetchMessages = async () => {
  if (!selectedContact.value) return
  loading.value = true
  try {
    const res: any = await api.get(`/messages/conversation/${selectedContact.value.id}`)
    messages.value = res
    await nextTick()
    scrollToBottom()
  } finally {
    loading.value = false
  }
}

const sendMessage = async () => {
  if (!messageInput.value.trim() || !selectedContact.value) return
  
  try {
    await api.post('/messages', {
      receiver_id: selectedContact.value.id,
      content: messageInput.value.trim()
    })
    messageInput.value = ''
    fetchMessages()
  } catch (error) {}
}

const selectContact = (contact: any) => {
  selectedContact.value = contact
  fetchMessages()
}

const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const formatTime = (time: string) => {
  const date = new Date(time)
  return date.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

onMounted(fetchContacts)
</script>

<template>
  <div class="messages-page">
    <div class="msg-page-header">
      <div>
        <h2 class="msg-page-title">
          <el-icon class="msg-title-icon"><ChatDotSquare /></el-icon>
          消息留言
        </h2>
        <p class="msg-page-desc">与导师沟通交流，获取指导建议</p>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-4 gap-4 h-[600px]">
      <!-- Contacts List -->
      <el-card class="lg:col-span-1">
        <template #header>
          <span class="font-bold">联系人</span>
        </template>
        <div v-if="contacts.length === 0" class="text-center py-8 text-gray-400">
          暂无联系人
        </div>
        <div v-else class="space-y-2">
          <div v-for="contact in contacts" :key="contact.id"
               :class="['p-3 rounded cursor-pointer flex items-center', 
                        selectedContact?.id === contact.id ? 'bg-blue-50 border-blue-300 border' : 'hover:bg-gray-50 border border-transparent']"
               @click="selectContact(contact)">
            <el-avatar :size="40" :src="getAvatarUrl(contact.user_code)" class="mr-3 border-2 border-white shadow-sm bg-cyan-50" />
            <div>
              <div class="font-medium">{{ contact.name }}</div>
              <div class="text-xs text-gray-400">{{ contact.role === 'instructor' ? '指导老师' : '学生' }}</div>
            </div>
          </div>
        </div>
      </el-card>

      <!-- Chat Area -->
      <el-card class="lg:col-span-3 flex flex-col">
        <template #header>
          <span class="font-bold">{{ selectedContact?.name || '请选择联系人' }}</span>
        </template>

        <div v-if="!selectedContact" class="flex-1 flex items-center justify-center text-gray-400">
          请从左侧选择联系人开始聊天
        </div>
        
        <template v-else>
          <!-- Messages -->
          <div ref="messagesContainer" class="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50 min-h-[400px]">
            <div v-for="msg in messages" :key="msg.id"
                 :class="['flex', msg.sender_id === authStore.user?.id ? 'justify-end' : 'justify-start']">
              <div :class="['max-w-[70%] p-3 rounded-lg', 
                           msg.sender_id === authStore.user?.id ? 'bg-blue-500 text-white' : 'bg-white border']">
                <div class="text-sm">{{ msg.content }}</div>
                <div :class="['text-xs mt-1', msg.sender_id === authStore.user?.id ? 'text-blue-100' : 'text-gray-400']">
                  {{ formatTime(msg.created_at) }}
                </div>
              </div>
            </div>
          </div>

          <!-- Input -->
          <div class="border-t p-4 flex gap-2">
            <el-input 
              v-model="messageInput" 
              placeholder="输入消息..." 
              @keyup.enter="sendMessage"
            />
            <el-button type="primary" :icon="Promotion" @click="sendMessage">发送</el-button>
          </div>
        </template>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.messages-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.msg-page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

.msg-page-title {
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
}

.msg-title-icon { color: #0891b2; }

.msg-page-desc {
  font-size: 13px;
  color: #94a3b8;
  margin: 4px 0 0;
}
</style>
