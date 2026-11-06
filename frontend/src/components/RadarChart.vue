<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { RadarChart as EChartsRadar } from 'echarts/charts'
import { LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

import { useUserStore } from '../stores/user'

use([EChartsRadar, LegendComponent, TooltipComponent, CanvasRenderer])

const props = defineProps({
  indicators: {
    type: Array,
    default: () => [],
  },
  values: {
    type: Array,
    default: () => [],
  },
  seriesData: {
    type: Array,
    default: () => [],
  },
  title: {
    type: String,
    default: '知识掌握度',
  },
  height: {
    type: Number,
    default: 320,
  },
})

const userStore = useUserStore()
const isDark = computed(() => userStore.theme === 'dark')
const SERIES_COLORS = [
  '#246BFE',
  '#D9831A',
  '#149A76',
  '#8B5CF6',
  '#D94F59',
  '#0891B2',
]
const chartSeries = computed(() => {
  if (props.seriesData.length) {
    return props.seriesData.map((item, index) => ({
      name: item.name,
      values: item.values || [],
      color: item.color || SERIES_COLORS[index % SERIES_COLORS.length],
    }))
  }
  return [
    {
      name: props.title,
      values: props.values,
      color: SERIES_COLORS[0],
    },
  ]
})
const hasData = computed(
  () =>
    props.indicators.length > 0 &&
    chartSeries.value.some((item) => item.values.length > 0),
)

const chartOption = computed(() => {
  const gridColor = isDark.value
    ? 'rgba(255, 255, 255, 0.14)'
    : 'rgba(23, 43, 58, 0.12)'

  return {
    animationDuration: 500,
    aria: {
      enabled: true,
      decal: { show: false },
    },
    tooltip: {
      trigger: 'item',
      backgroundColor: isDark.value ? '#1b2a36' : '#ffffff',
      borderColor: isDark.value ? '#354857' : '#e1e8ef',
      textStyle: {
        color: isDark.value ? '#edf3f8' : '#172b3a',
      },
      valueFormatter: (value) =>
        `${Math.round(Number(value || 0) * 100)}%`,
    },
    radar: {
      center: ['50%', '52%'],
      radius: '64%',
      splitNumber: 4,
      indicator: props.indicators.map((item) => ({
        name: item.name,
        max: item.max ?? 1,
      })),
      axisName: {
        color: isDark.value ? '#c9d7e3' : '#566575',
        fontSize: 12,
      },
      splitLine: { lineStyle: { color: gridColor } },
      splitArea: {
        areaStyle: {
          color: isDark.value
            ? ['rgba(120,167,255,0.03)', 'rgba(120,167,255,0.08)']
            : ['rgba(36,107,254,0.02)', 'rgba(36,107,254,0.06)'],
        },
      },
      axisLine: { lineStyle: { color: gridColor } },
    },
    legend: {
      show: chartSeries.value.length > 1,
      type: 'scroll',
      bottom: 0,
      left: 'center',
      itemWidth: 14,
      itemHeight: 8,
      textStyle: {
        color: isDark.value ? '#c9d7e3' : '#566575',
        fontSize: 11,
      },
    },
    series: chartSeries.value.map((item, index) => ({
      type: 'radar',
      name: item.name,
      symbol: 'circle',
      symbolSize: index === chartSeries.value.length - 1 ? 5 : 3,
      lineStyle: {
        color: item.color,
        width: index === chartSeries.value.length - 1 ? 2.4 : 1.5,
      },
      itemStyle: {
        color: item.color,
        borderColor: isDark.value ? '#17232e' : '#ffffff',
        borderWidth: 2,
      },
      areaStyle: {
        opacity:
          index === chartSeries.value.length - 1 ? 0.16 : 0.035,
        color: item.color,
      },
      data: [
        {
          value: item.values,
          name: item.name,
        },
      ],
    })),
  }
})
</script>

<template>
  <v-chart
    v-if="hasData"
    class="radar-chart"
    :style="{ height: `${height}px` }"
    :option="chartOption"
    :update-options="{ notMerge: true }"
    autoresize
  />
  <el-empty v-else description="暂无能力数据" :image-size="72" />
</template>

<style scoped>
.radar-chart {
  width: 100%;
  min-height: 260px;
}
</style>
