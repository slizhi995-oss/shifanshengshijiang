<script setup lang="ts">
defineProps<{
  message?: string
  icon?: string
}>()
</script>

<template>
  <div class="flex flex-col items-center justify-center py-12 text-gray-400">
    <el-icon :size="48" class="mb-4">
      <component :is="icon || 'Document'" />
    </el-icon>
    <p>{{ message || '暂无数据' }}</p>
    <slot></slot>
  </div>
</template>
