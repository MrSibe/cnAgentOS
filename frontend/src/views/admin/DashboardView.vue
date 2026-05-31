<script setup lang="ts">
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import 'echarts-gl'
import 'echarts-wordcloud'
import { onMounted, onUnmounted, ref, nextTick } from 'vue'

import { get } from '@/api/client'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import type { DashboardStats, TrendData, KeywordItem } from '@/types'
import { errorMessage } from '@/utils/display'

const loading = ref(false)
const stats = ref<DashboardStats | null>(null)
const trends = ref<TrendData | null>(null)
const keywords = ref<KeywordItem[]>([])

const trendChartRef = ref<HTMLElement | null>(null)
const distChartRef = ref<HTMLElement | null>(null)
const wordcloudChartRef = ref<HTMLElement | null>(null)
const globeChartRef = ref<HTMLElement | null>(null)

let trendChart: echarts.ECharts | null = null
let distChart: echarts.ECharts | null = null
let wordcloudChart: echarts.ECharts | null = null
let globeChart: echarts.ECharts | null = null
let refreshTimer: ReturnType<typeof setInterval> | null = null

async function load(): Promise<void> {
  loading.value = true
  try {
    const [statsData, trendsData, kwData] = await Promise.all([
      get<DashboardStats>('/api/v1/admin/dashboard/stats'),
      get<TrendData>('/api/v1/admin/dashboard/trends?days=14'),
      get<KeywordItem[]>('/api/v1/admin/dashboard/keywords?limit=50'),
    ])
    stats.value = statsData
    trends.value = trendsData
    keywords.value = kwData
    await nextTick()
    renderCharts()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

function renderCharts(): void {
  renderTrendChart()
  renderDistChart()
  renderWordcloud()
  renderGlobe()
}

function renderTrendChart(): void {
  if (!trendChartRef.value || !trends.value) return
  if (!trendChart) trendChart = echarts.init(trendChartRef.value)

  const dates = trends.value.knowledge_items.map(d => d.date)
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['知识项', '问数', '消息'], textStyle: { fontSize: 12 } },
    grid: { left: 50, right: 20, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: dates, axisLabel: { rotate: 45, fontSize: 10 } },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        name: '知识项', type: 'line', smooth: true,
        data: trends.value.knowledge_items.map(d => d.count),
        itemStyle: { color: '#409EFF' },
      },
      {
        name: '问数', type: 'line', smooth: true,
        data: trends.value.qa_questions.map(d => d.count),
        itemStyle: { color: '#67C23A' },
      },
      {
        name: '消息', type: 'line', smooth: true,
        data: trends.value.chat_messages.map(d => d.count),
        itemStyle: { color: '#E6A23C' },
      },
    ],
  })
}

function renderDistChart(): void {
  if (!distChartRef.value || !stats.value?.knowledge_items) return
  if (!distChart) distChart = echarts.init(distChartRef.value)

  const ki = stats.value.knowledge_items
  const data = Object.entries(ki)
    .filter(([k]) => k !== 'total')
    .map(([name, value]) => ({ name: statusLabel(name), value }))

  distChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [
      {
        type: 'pie',
        radius: ['35%', '60%'],
        center: ['50%', '50%'],
        data,
        label: { show: true, formatter: '{b}\n{d}%', fontSize: 11 },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.2)' } },
      },
    ],
  })
}

function renderWordcloud(): void {
  if (!wordcloudChartRef.value || !keywords.value.length) return
  if (!wordcloudChart) wordcloudChart = echarts.init(wordcloudChartRef.value)

  const maxCount = Math.max(...keywords.value.map(k => k.count))
  wordcloudChart.setOption({
    tooltip: { show: true },
    series: [
      {
        type: 'wordCloud',
        gridSize: 10,
        sizeRange: [12, 50],
        rotationRange: [-30, 30],
        shape: 'circle',
        data: keywords.value.map(k => ({
          name: k.word,
          value: k.count,
          textStyle: {
            color: `hsl(${Math.random() * 360}, 70%, 50%)`,
            fontSize: 12 + (k.count / maxCount) * 38,
          },
        })),
      },
    ],
  })
}

function renderGlobe(): void {
  if (!globeChartRef.value) return
  if (!globeChart) globeChart = echarts.init(globeChartRef.value)

  // Generate sample data points for the globe scatter
  const cities = [
    { name: '北京', lng: 116.4, lat: 39.9 },
    { name: '上海', lng: 121.5, lat: 31.2 },
    { name: '广州', lng: 113.3, lat: 23.1 },
    { name: '深圳', lng: 114.1, lat: 22.5 },
    { name: '成都', lng: 104.1, lat: 30.6 },
    { name: '杭州', lng: 120.2, lat: 30.3 },
    { name: '武汉', lng: 114.3, lat: 30.6 },
    { name: '西安', lng: 108.9, lat: 34.3 },
    { name: '重庆', lng: 106.5, lat: 29.6 },
    { name: '南京', lng: 118.8, lat: 32.1 },
  ]
  const scatterData = cities.map(c => ({
    value: [c.lng, c.lat, Math.floor(Math.random() * 50) + 10],
    name: c.name,
  }))

  globeChart.setOption({
    globe: {
      baseTexture: undefined, // will use default earth texture
      heightTexture: undefined,
      displacementScale: 0.04,
      shading: 'realistic',
      realisticMaterial: {
        roughness: 0.5,
        metalness: 0.1,
      },
      postEffect: {
        enable: true,
        bloom: { enable: true, intensity: 0.1 },
      },
      light: {
        main: { intensity: 1.5 },
        ambient: { intensity: 0.3 },
      },
      viewControl: {
        autoRotate: true,
        autoRotateSpeed: 5,
        distance: 200,
      },
    },
    series: [
      {
        type: 'scatter3D',
        coordinateSystem: 'globe',
        data: scatterData,
        symbolSize: (val: number[]) => Math.max(8, val[2] || 10),
        itemStyle: {
          color: '#409EFF',
          opacity: 0.8,
        },
        label: {
          show: true,
          formatter: (p: { name: string }) => p.name,
          color: '#fff',
          fontSize: 10,
        },
      },
    ],
  })
}

function statusLabel(s: string): string {
  const labels: Record<string, string> = {
    available: '可用',
    excluded: '排除',
    archived: '归档',
    active: '活跃',
    disabled: '停用',
    succeeded: '成功',
    failed: '失败',
    pending: '等待',
    running: '运行中',
    partial_failed: '部分失败',
  }
  return labels[s] || s
}

onMounted(() => {
  load()
  refreshTimer = setInterval(load, 30000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
  ;[trendChart, distChart, wordcloudChart, globeChart].forEach(chart => chart?.dispose())
})
</script>

<template>
  <AdminPageHeader title="数智大屏" description="系统核心指标与数据可视化" />

  <!-- KPI Cards -->
  <el-row :gutter="16" style="margin-bottom: 16px" v-if="stats">
    <el-col :xs="12" :sm="6">
      <el-card shadow="hover">
        <div style="text-align: center">
          <div style="font-size: 28px; font-weight: bold; color: #409EFF">{{ stats.knowledge_items.total || 0 }}</div>
          <div style="color: #999; font-size: 13px">知识项</div>
        </div>
      </el-card>
    </el-col>
    <el-col :xs="12" :sm="6">
      <el-card shadow="hover">
        <div style="text-align: center">
          <div style="font-size: 28px; font-weight: bold; color: #67C23A">{{ stats.collection_tasks.total || 0 }}</div>
          <div style="color: #999; font-size: 13px">采集任务</div>
        </div>
      </el-card>
    </el-col>
    <el-col :xs="12" :sm="6">
      <el-card shadow="hover">
        <div style="text-align: center">
          <div style="font-size: 28px; font-weight: bold; color: #E6A23C">{{ stats.qa_sessions.total || 0 }}</div>
          <div style="color: #999; font-size: 13px">问数会话</div>
        </div>
      </el-card>
    </el-col>
    <el-col :xs="12" :sm="6">
      <el-card shadow="hover">
        <div style="text-align: center">
          <div style="font-size: 28px; font-weight: bold; color: #F56C6C">{{ stats.users.active_today || 0 }}<span style="font-size:14px;color:#999">/{{ stats.users.total || 0 }}</span></div>
          <div style="color: #999; font-size: 13px">活跃用户/总数</div>
        </div>
      </el-card>
    </el-col>
  </el-row>

  <el-row :gutter="16" style="margin-bottom: 16px">
    <!-- Trend Chart -->
    <el-col :xs="24" :sm="12" style="margin-bottom: 16px">
      <el-card>
        <template #header><span>趋势图 (14日)</span></template>
        <div ref="trendChartRef" style="width: 100%; height: 300px"></div>
      </el-card>
    </el-col>
    <!-- Distribution Pie -->
    <el-col :xs="24" :sm="12" style="margin-bottom: 16px">
      <el-card>
        <template #header><span>知识项状态分布</span></template>
        <div ref="distChartRef" style="width: 100%; height: 300px"></div>
      </el-card>
    </el-col>
  </el-row>

  <el-row :gutter="16" style="margin-bottom: 16px">
    <!-- Word Cloud -->
    <el-col :xs="24" :sm="12" style="margin-bottom: 16px">
      <el-card>
        <template #header><span>词云</span></template>
        <div v-if="!keywords.length && !loading" style="text-align:center;padding:40px;color:#999">暂无关键词数据</div>
        <div ref="wordcloudChartRef" style="width: 100%; height: 350px"></div>
      </el-card>
    </el-col>
    <!-- 3D Earth -->
    <el-col :xs="24" :sm="12" style="margin-bottom: 16px">
      <el-card>
        <template #header><span>3D 数据分布</span></template>
        <div ref="globeChartRef" style="width: 100%; height: 400px"></div>
      </el-card>
    </el-col>
  </el-row>

  <!-- Loading overlay -->
  <div v-if="loading" v-loading="loading" style="min-height: 100px"></div>
</template>

<style scoped>
.el-card {
  border-radius: 8px;
}
</style>
