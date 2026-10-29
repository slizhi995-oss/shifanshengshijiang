<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  status: string
  type?: 'submission' | 'semester' | 'task'
}>()

const statusConfig = computed(() => {
  if (props.type === 'submission') {
    switch (props.status) {
      case 'pending': return { type: 'warning', text: '待批改' }
      case 'approved': return { type: 'success', text: '已通过' }
      case 'rejected': return { type: 'danger', text: '已驳回' }
      default: return { type: 'info', text: props.status }
    }
  }
  if (props.type === 'semester') {
    switch (props.status) {
      case 'draft': return { type: 'info', text: '草稿' }
      case 'active': return { type: 'success', text: '进行中' }
      case 'completed': return { type: 'warning', text: '已结束' }
      default: return { type: 'info', text: props.status }
    }
  }
  if (props.type === 'task') {
    switch (props.status) {
      case 'draft': return { type: 'info', text: '草稿' }
      case 'published': return { type: 'success', text: '已发布' }
      default: return { type: 'info', text: props.status }
    }
  }
  return { type: 'info', text: props.status }
})
</script>

<template>
  <el-tag :type="statusConfig.type as any" size="small">
    {{ statusConfig.text }}
  </el-tag>
</template>
