<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, Document, VideoPlay } from '@element-plus/icons-vue'

const props = defineProps<{
  accept?: string
  maxSize?: number // MB
  type?: 'pdf' | 'video' | 'any'
}>()

const emit = defineEmits<{
  (e: 'file-selected', file: File): void
}>()

const selectedFile = ref<File | null>(null)
const isDragging = ref(false)

const acceptTypes = {
  pdf: '.pdf',
  video: '.mp4,.avi,.mov,.wmv',
  any: '*'
}

const maxSizeBytes = (props.maxSize || 500) * 1024 * 1024 // Default 500MB

const handleFileSelect = (e: Event) => {
  const target = e.target as HTMLInputElement
  if (target.files && target.files[0]) {
    validateAndEmit(target.files[0])
  }
}

const handleDrop = (e: DragEvent) => {
  isDragging.value = false
  if (e.dataTransfer?.files[0]) {
    validateAndEmit(e.dataTransfer.files[0])
  }
}

const validateAndEmit = (file: File) => {
  // Check size
  if (file.size > maxSizeBytes) {
    ElMessage.error(`文件大小不能超过 ${props.maxSize || 500}MB`)
    return
  }
  
  // Check type
  if (props.type === 'pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
    ElMessage.error('请上传PDF格式文件')
    return
  }
  
  if (props.type === 'video') {
    const videoExtensions = ['.mp4', '.avi', '.mov', '.wmv']
    const isVideo = videoExtensions.some(ext => file.name.toLowerCase().endsWith(ext))
    if (!isVideo) {
      ElMessage.error('请上传视频格式文件')
      return
    }
  }
  
  selectedFile.value = file
  emit('file-selected', file)
}

const formatFileSize = (bytes: number) => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

const clearFile = () => {
  selectedFile.value = null
}

defineExpose({ clearFile })
</script>

<template>
  <div
    class="border-2 border-dashed rounded-lg p-6 text-center transition-colors cursor-pointer"
    :class="isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-400'"
    @dragenter.prevent="isDragging = true"
    @dragleave.prevent="isDragging = false"
    @dragover.prevent
    @drop.prevent="handleDrop"
    @click="($refs.fileInput as HTMLInputElement).click()"
  >
    <input
      ref="fileInput"
      type="file"
      :accept="acceptTypes[type || 'any']"
      class="hidden"
      @change="handleFileSelect"
    />
    
    <div v-if="!selectedFile" class="space-y-2">
      <el-icon :size="40" class="text-gray-400">
        <UploadFilled />
      </el-icon>
      <p class="text-gray-500">点击或拖拽文件到此处上传</p>
      <p class="text-sm text-gray-400">
        <span v-if="type === 'pdf'">支持 PDF 格式</span>
        <span v-else-if="type === 'video'">支持 MP4/AVI/MOV 格式</span>
        <span v-else>支持所有格式</span>
        ，最大 {{ maxSize || 500 }}MB
      </p>
    </div>
    
    <div v-else class="flex items-center justify-center space-x-3">
      <el-icon :size="32" class="text-blue-500">
        <Document v-if="type === 'pdf'" />
        <VideoPlay v-else-if="type === 'video'" />
        <Document v-else />
      </el-icon>
      <div class="text-left">
        <p class="font-medium text-gray-700">{{ selectedFile.name }}</p>
        <p class="text-sm text-gray-400">{{ formatFileSize(selectedFile.size) }}</p>
      </div>
      <el-button size="small" type="danger" text @click.stop="clearFile">移除</el-button>
    </div>
  </div>
</template>
