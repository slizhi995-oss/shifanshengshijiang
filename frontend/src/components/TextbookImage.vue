<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { textbookApi } from '@/api/textbooks'
const props = defineProps<{ assetId: string; alt?: string }>()
const source = ref('')
const failed = ref(false)
let revision = 0
watch(() => props.assetId, async id => {
  const current = ++revision
  if (source.value) URL.revokeObjectURL(source.value)
  source.value = ''; failed.value = false
  try {
    const data = await textbookApi.image(id)
    if (current === revision) source.value = URL.createObjectURL(data)
  } catch { if (current === revision) failed.value = true }
}, { immediate: true })
onBeforeUnmount(() => { revision++; if (source.value) URL.revokeObjectURL(source.value) })
</script>
<template>
  <img v-if="source" :src="source" :alt="alt || '教材图片'" class="textbook-image" />
  <span v-else class="material-status">{{ failed ? '图片暂不可用' : '加载图片…' }}</span>
</template>
<style scoped>
.textbook-image { width: 100%; height: 210px; object-fit: contain; background: #f8fafc; }
.material-status { display: block; padding: 32px 10px; text-align: center; color: #64748b; }
</style>
