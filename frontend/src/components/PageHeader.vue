<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>

<template>
  <div class="mb-6">
    <h2 class="text-2xl font-bold text-gray-800">{{ title }}</h2>
    <p v-if="description" class="mt-1 text-gray-500">{{ description }}</p>
    <slot></slot>
  </div>
</template>
