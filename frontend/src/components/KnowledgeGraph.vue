<script setup lang="ts">
/**
 * 教案知识图谱组件
 * 使用 ECharts Graph 展示教案结构关系
 */
import { ref, computed, onMounted, watch } from 'vue'
import { use } from 'echarts/core'
import { GraphChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { ElMessage } from 'element-plus'
import { aiApi } from '@/api/ai'

use([GraphChart, TitleComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps<{
  submissionId?: number
  text?: string
}>()

const loading = ref(false)
const graphData = ref<any>(null)

const categoryColors = [
  '#0891b2', // 教学目标 - 靛蓝
  '#f59e0b', // 教学重点 - 琥珀
  '#10b981', // 教学过程 - 翡翠
  '#3b82f6', // 教学方法 - 蓝
  '#ec4899', // 知识点 - 粉
  '#0d9488', // 板书设计 - 紫
]

const chartOption = computed(() => {
  if (!graphData.value) return null
  
  const { nodes, links, categories } = graphData.value
  
  return {
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        if (params.dataType === 'node') {
          return `<div style="font-weight:600;">${params.data.name}</div><div style="color:#888;font-size:12px;">${params.data.category}</div>`
        }
        return `${params.data.source} → ${params.data.target}<br/>${params.data.label || ''}`
      }
    },
    legend: {
      data: categories.map((c: any) => c.name),
      bottom: 10,
      textStyle: { color: '#666', fontSize: 12 },
      icon: 'circle',
      itemWidth: 10,
      itemHeight: 10
    },
    animationDuration: 1500,
    animationEasingUpdate: 'quinticInOut',
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      force: {
        repulsion: 300,
        edgeLength: [80, 200],
        gravity: 0.1
      },
      label: {
        show: true,
        fontSize: 12,
        fontWeight: 'bold',
        color: '#334155'
      },
      edgeLabel: {
        show: true,
        fontSize: 10,
        color: '#94a3b8',
        formatter: (params: any) => params.data.label || ''
      },
      lineStyle: {
        color: '#cbd5e1',
        width: 2,
        curveness: 0.1
      },
      emphasis: {
        focus: 'adjacency',
        lineStyle: { width: 4 }
      },
      categories: categories.map((c: any, i: number) => ({
        name: c.name,
        itemStyle: { color: categoryColors[i % categoryColors.length] }
      })),
      data: nodes.map((n: any) => ({
        ...n,
        symbolSize: Math.max(30, (n.value || 5) * 6),
        category: categories.findIndex((c: any) => c.name === n.category),
        itemStyle: {
          shadowBlur: 10,
          shadowColor: 'rgba(0,0,0,0.1)'
        }
      })),
      links: links.map((l: any) => ({
        ...l,
        lineStyle: { curveness: 0.1 }
      }))
    }]
  }
})

const fetchGraph = async () => {
  loading.value = true
  try {
    const payload: any = {}
    if (props.submissionId) payload.submission_id = props.submissionId
    else if (props.text) payload.text = props.text
    else return

    // ≤4.5s 内返回（超时会自动使用兜底图谱数据）
    const res: any = await aiApi.knowledgeGraph(payload)
    if (res.success) {
      graphData.value = res.data
    }
  } catch (error: any) {
    ElMessage.error(error.message || '知识图谱生成失败')
  } finally {
    loading.value = false
  }
}

watch(() => [props.submissionId, props.text], () => {
  if (props.submissionId || props.text) fetchGraph()
})

onMounted(() => {
  if (props.submissionId || props.text) fetchGraph()
})

defineExpose({ fetchGraph })
</script>

<template>
  <div class="knowledge-graph-container" v-loading="loading" element-loading-text="AI 正在提取知识图谱...">
    <div class="graph-header">
      <div class="graph-title">
        <span class="title-icon">🧬</span>
        <span>教案知识图谱</span>
      </div>
      <el-button size="small" @click="fetchGraph" :loading="loading" text type="primary">
        重新生成
      </el-button>
    </div>
    <div class="graph-chart">
      <v-chart v-if="chartOption" :option="chartOption as any" autoresize />
      <div v-else-if="!loading" class="empty-state">
        <span class="empty-icon">🧬</span>
        <span>点击"重新生成"提取知识图谱</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.knowledge-graph-container {
  background: white;
  border-radius: 16px;
  border: 1px solid #f1f5f9;
  overflow: hidden;
}

.graph-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #f3f4f6;
}

.graph-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  color: #1e293b;
  font-size: 15px;
}

.title-icon {
  font-size: 20px;
}

.graph-chart {
  height: 400px;
  padding: 8px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #94a3b8;
  gap: 12px;
}

.empty-icon {
  font-size: 40px;
  opacity: 0.5;
}
</style>
