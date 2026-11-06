<script setup>
import {
  Clock,
  DataAnalysis,
  EditPen,
  Promotion,
  Refresh,
  Timer,
  TrendCharts,
} from '@element-plus/icons-vue'
import { use } from 'echarts/core'
import { HeatmapChart, LineChart } from 'echarts/charts'
import {
  CalendarComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import VChart from 'vue-echarts'

import RadarChart from '../components/RadarChart.vue'
import { useLearningContentStore } from '../stores/learningContent'
import { useLearningStore } from '../stores/learning'
import { useUserStore } from '../stores/user'

use([
  HeatmapChart,
  LineChart,
  CalendarComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
])

const router = useRouter()
const userStore = useUserStore()
const learningContentStore = useLearningContentStore()
const learningStore = useLearningStore()
const loadFailed = ref(false)

const radarData = computed(() => {
  return learningStore.categoryMastery
    .slice(0, 8)
    .map((item) => ({
      name: item.name,
      value: Number((item.value || 0).toFixed(4)),
    }))
})

const radarIndicators = computed(() =>
  radarData.value.map((item) => ({ name: item.name, max: 1 })),
)
const radarValues = computed(() =>
  radarData.value.map((item) => item.value),
)
const recommendation = computed(
  () => learningStore.recommendations[0] || null,
)
const recommendationPercent = computed(() =>
  Math.round((recommendation.value?.current_mastery || 0) * 100),
)
const weeklyAccuracyPercent = computed(() =>
  Math.round(learningStore.weeklyAccuracy * 100),
)
const isDark = computed(() => userStore.theme === 'dark')
const dailyActivity = computed(() => learningStore.dailyActivity || [])
const calendarMax = computed(() =>
  Math.max(
    4,
    ...dailyActivity.value.map((item) => item.questions),
  ),
)
const calendarRange = computed(() => {
  if (!dailyActivity.value.length) return null
  return [
    dailyActivity.value[0].date,
    dailyActivity.value[dailyActivity.value.length - 1].date,
  ]
})
const calendarOption = computed(() => ({
  tooltip: {
    formatter: (params) => {
      const [date, questions] = params.value
      const item = dailyActivity.value.find(
        (activity) => activity.date === date,
      )
      return [
        `<strong>${date}</strong>`,
        `做题 ${questions} 道`,
        `学习 ${item?.study_minutes || 0} 分钟`,
      ].join('<br/>')
    },
  },
  visualMap: {
    show: false,
    min: 0,
    max: calendarMax.value,
    inRange: {
      color: isDark.value
        ? ['#263542', '#2b6b9f', '#78a7ff']
        : ['#edf3f8', '#a8c4ff', '#246bfe'],
    },
  },
  calendar: {
    top: 28,
    right: 18,
    bottom: 20,
    left: 28,
    range: calendarRange.value,
    cellSize: ['auto', 24],
    orient: 'horizontal',
    itemStyle: {
      color: isDark.value ? '#202d39' : '#f4f7fa',
      borderColor: isDark.value ? '#17232e' : '#ffffff',
      borderWidth: 2,
    },
    splitLine: {
      show: false,
    },
    dayLabel: {
      color: isDark.value ? '#9db0c2' : '#7b8a99',
      nameMap: ['日', '一', '二', '三', '四', '五', '六'],
      fontSize: 9,
    },
    monthLabel: {
      color: isDark.value ? '#c9d7e3' : '#566575',
      fontSize: 10,
    },
    yearLabel: {
      show: false,
    },
  },
  series: [
    {
      type: 'heatmap',
      coordinateSystem: 'calendar',
      data: dailyActivity.value.map((item) => [
        item.date,
        item.questions,
      ]),
    },
  ],
}))
const trendOption = computed(() => {
  const dates = dailyActivity.value.map((item) =>
    item.date.slice(5).replace('-', '/'),
  )
  const mastery = dailyActivity.value.map((item) =>
    Number((item.mastery * 100).toFixed(1)),
  )
  const accuracy = dailyActivity.value.map((item) =>
    item.questions
      ? Number((item.accuracy * 100).toFixed(1))
      : null,
  )
  const gridColor = isDark.value
    ? 'rgba(255,255,255,0.1)'
    : 'rgba(23,43,58,0.09)'
  const textColor = isDark.value ? '#9db0c2' : '#7b8a99'

  return {
    animationDuration: 450,
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value) =>
        value === null || value === undefined
          ? '无数据'
          : `${value}%`,
    },
    legend: {
      right: 6,
      top: 0,
      textStyle: { color: textColor, fontSize: 10 },
    },
    grid: {
      top: 42,
      right: 18,
      bottom: 26,
      left: 44,
    },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: false,
      axisLine: { lineStyle: { color: gridColor } },
      axisTick: { show: false },
      axisLabel: {
        color: textColor,
        fontSize: 9,
        interval: Math.max(0, Math.floor(dates.length / 6) - 1),
      },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: {
        color: textColor,
        fontSize: 9,
        formatter: '{value}%',
      },
      splitLine: {
        lineStyle: {
          color: gridColor,
          type: 'dashed',
        },
      },
    },
    series: [
      {
        name: '知识掌握度',
        type: 'line',
        data: mastery,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#246BFE', width: 2 },
        itemStyle: { color: '#246BFE' },
        areaStyle: {
          color: 'rgba(36,107,254,0.12)',
        },
      },
      {
        name: '答题正确率',
        type: 'line',
        data: accuracy,
        smooth: true,
        connectNulls: false,
        symbol: 'circle',
        symbolSize: 4,
        lineStyle: { color: '#149A76', width: 2 },
        itemStyle: { color: '#149A76' },
      },
    ],
  }
})

function formatDuration(minutes) {
  const safeMinutes = Math.max(0, Math.round(Number(minutes) || 0))
  if (safeMinutes < 60) return `${safeMinutes} 分钟`
  const hours = Math.floor(safeMinutes / 60)
  const remaining = safeMinutes % 60
  return remaining
    ? `${hours} 小时 ${remaining} 分钟`
    : `${hours} 小时`
}

function formatActivityTime(value) {
  if (!value) return ''
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function formatActivityDuration(seconds) {
  const safeSeconds = Math.max(0, Math.round(Number(seconds) || 0))
  if (safeSeconds < 60) return `${safeSeconds} 秒`
  return formatDuration(safeSeconds / 60)
}

async function loadDashboard() {
  loadFailed.value = false
  try {
    if (!userStore.profile?.id) {
      await userStore.fetchProfile()
    }
    await learningStore.fetchDashboard(
      learningContentStore.activeSubject,
    )
  } catch {
    loadFailed.value = true
  }
}

onMounted(loadDashboard)

watch(
  () => learningContentStore.activeSubject,
  () => loadDashboard(),
)
</script>

<template>
  <section class="dashboard-page">
    <header class="welcome-panel">
      <div class="welcome-copy">
        <p class="page-kicker">今日学习概览</p>
        <div class="welcome-heading">
          <h1>你好，{{ userStore.displayName }}</h1>
          <span class="welcome-badge">保持节奏</span>
        </div>
        <p class="welcome-description">
          从最适合当前水平的一步开始，完成今天的学习目标。
        </p>
        <div class="current-content">
          <span>当前学习内容</span>
          <strong>{{ learningContentStore.activeTitle }}</strong>
        </div>
      </div>

      <div class="welcome-side">
        <div class="welcome-stats">
          <div class="welcome-stat">
            <span class="stat-symbol blue">
              <el-icon><Clock /></el-icon>
            </span>
            <div>
              <small>连续学习</small>
              <strong>{{ learningStore.studyStreakDays }} 天</strong>
            </div>
          </div>
          <div class="welcome-stat">
            <span class="stat-symbol green">
              <el-icon><Timer /></el-icon>
            </span>
            <div>
              <small>总学习时长</small>
              <strong>{{ formatDuration(learningStore.totalStudyMinutes) }}</strong>
            </div>
          </div>
        </div>
        <button
          class="path-entry"
          type="button"
          @click="router.push('/learning-path')"
        >
          <span>
            <small>今日计划</small>
            <strong>查看个性化学习路径</strong>
          </span>
          <el-icon><Promotion /></el-icon>
        </button>
      </div>
    </header>

    <el-skeleton
      v-if="learningStore.loading"
      class="dashboard-skeleton"
      :rows="10"
      animated
    />

    <div v-else-if="loadFailed" class="surface-panel empty-panel">
      <el-empty description="看板数据加载失败" :image-size="90">
        <el-button :icon="Refresh" @click="loadDashboard">重新加载</el-button>
      </el-empty>
    </div>

    <template v-else>
      <el-row :gutter="18" class="dashboard-row dashboard-main-row">
        <el-col :xs="24" :sm="24" :md="24" :lg="8">
          <el-card shadow="never" class="dashboard-card">
            <template #header>
              <div class="card-heading">
                <div>
                  <h2>知识掌握雷达</h2>
                  <p>{{ radarData.length }} 个核心模块平均掌握度</p>
                </div>
                <span class="heading-number">
                  {{ Math.round(learningStore.overallMastery * 100) }}%
                </span>
              </div>
            </template>
            <RadarChart
              :indicators="radarIndicators"
              :values="radarValues"
              :height="328"
            />
          </el-card>
        </el-col>

        <el-col :xs="24" :sm="24" :md="12" :lg="8">
          <el-card shadow="never" class="dashboard-card recommendation-card">
            <template #header>
              <div class="card-heading">
                <div>
                  <h2>今日推荐学习</h2>
                  <p>AI 为你选择的下一个目标</p>
                </div>
                <el-icon class="heading-icon"><DataAnalysis /></el-icon>
              </div>
            </template>

            <template v-if="recommendation">
              <div class="recommendation-meta">
                <el-tag effect="plain">{{ recommendation.category }}</el-tag>
                <span>难度 {{ recommendation.difficulty }}</span>
              </div>
              <h3>{{ recommendation.name }}</h3>
              <p class="recommendation-description">
                {{ recommendation.description }}
              </p>

              <div class="mastery-label">
                <span>当前掌握度</span>
                <strong>{{ recommendationPercent }}%</strong>
              </div>
              <el-progress
                :percentage="recommendationPercent"
                :stroke-width="8"
                :show-text="false"
                color="#246BFE"
              />

              <div class="recommendation-reason">
                <span>推荐理由</span>
                <p>{{ recommendation.reason }}</p>
              </div>

              <el-button
                type="primary"
                class="start-button"
                @click="router.push('/learning-path')"
              >
                开始学习
                <el-icon class="button-icon"><Promotion /></el-icon>
              </el-button>
            </template>

            <el-empty
              v-else
              description="今天没有新的推荐"
              :image-size="84"
            />
          </el-card>
        </el-col>

        <el-col :xs="24" :sm="24" :md="12" :lg="8">
          <el-card shadow="never" class="dashboard-card weekly-card">
            <template #header>
              <div class="card-heading">
                <div>
                  <h2>学习统计</h2>
                  <p>本周练习与投入</p>
                </div>
                <el-icon class="heading-icon green">
                  <TrendCharts />
                </el-icon>
              </div>
            </template>

            <div class="weekly-stats">
              <article class="weekly-stat">
                <span class="weekly-icon blue">
                  <el-icon><EditPen /></el-icon>
                </span>
                <div>
                  <small>本周做题数量</small>
                  <strong>{{ learningStore.weeklyQuestions }}</strong>
                  <span>道题</span>
                </div>
              </article>
              <article class="weekly-stat">
                <span class="weekly-icon green">
                  <el-icon><TrendCharts /></el-icon>
                </span>
                <div>
                  <small>本周正确率</small>
                  <strong>{{ weeklyAccuracyPercent }}</strong>
                  <span>%</span>
                </div>
              </article>
              <article class="weekly-stat">
                <span class="weekly-icon yellow">
                  <el-icon><Timer /></el-icon>
                </span>
                <div>
                  <small>本周学习时长</small>
                  <strong>{{ formatDuration(learningStore.weeklyStudyMinutes) }}</strong>
                </div>
              </article>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="18" class="dashboard-row dashboard-chart-row">
        <el-col :xs="24" :sm="24" :md="10" :lg="10">
          <el-card shadow="never" class="dashboard-card chart-card">
            <template #header>
              <div class="card-heading">
                <div>
                  <h2>学习日历</h2>
                  <p>过去 30 天每日答题量</p>
                </div>
                <span class="chart-note">近 30 天</span>
              </div>
            </template>
            <v-chart
              v-if="dailyActivity.length"
              class="dashboard-chart calendar-chart"
              :option="calendarOption"
              :update-options="{ notMerge: true }"
              autoresize
            />
            <el-empty
              v-else
              description="暂无学习日历数据"
              :image-size="72"
            />
          </el-card>
        </el-col>

        <el-col :xs="24" :sm="24" :md="14" :lg="14">
          <el-card shadow="never" class="dashboard-card chart-card">
            <template #header>
              <div class="card-heading">
                <div>
                  <h2>30 天学习趋势</h2>
                  <p>知识掌握度与答题正确率变化</p>
                </div>
                <el-icon class="heading-icon green">
                  <TrendCharts />
                </el-icon>
              </div>
            </template>
            <v-chart
              v-if="dailyActivity.length"
              class="dashboard-chart trend-chart"
              :option="trendOption"
              :update-options="{ notMerge: true }"
              autoresize
            />
            <el-empty
              v-else
              description="暂无趋势数据"
              :image-size="72"
            />
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="18" class="dashboard-row dashboard-bottom-row">
        <el-col :xs="24" :sm="24" :md="14" :lg="15">
          <el-card shadow="never" class="dashboard-card">
            <template #header>
              <div class="card-heading">
                <div>
                  <h2>最近学习活动</h2>
                  <p>最近的练习与答题表现</p>
                </div>
                <span class="activity-count">
                  {{ learningStore.recentActivities.length }} 条
                </span>
              </div>
            </template>

            <el-timeline
              v-if="learningStore.recentActivities.length"
              class="activity-timeline"
            >
              <el-timeline-item
                v-for="activity in learningStore.recentActivities"
                :key="activity.id"
                :timestamp="formatActivityTime(activity.created_at)"
                :type="activity.is_correct ? 'success' : 'danger'"
                placement="top"
              >
                <div class="activity-content">
                  <div>
                    <strong>
                      完成「{{ activity.knowledge_point_name }}」练习
                    </strong>
                    <p>用时 {{ formatActivityDuration(activity.time_spent) }}</p>
                  </div>
                  <el-tag
                    :type="activity.is_correct ? 'success' : 'danger'"
                    effect="light"
                    size="small"
                  >
                    {{ activity.is_correct ? '答对' : '答错' }}
                  </el-tag>
                </div>
              </el-timeline-item>
            </el-timeline>
            <el-empty
              v-else
              description="暂无学习活动"
              :image-size="76"
            />
          </el-card>
        </el-col>

        <el-col :xs="24" :sm="24" :md="10" :lg="9">
          <el-card shadow="never" class="dashboard-card weak-card">
            <template #header>
              <div class="card-heading">
                <div>
                  <h2>薄弱知识点提醒</h2>
                  <p>建议优先复习的内容</p>
                </div>
              </div>
            </template>

            <div v-if="learningStore.weakPoints.length" class="weak-list">
              <el-tag
                v-for="point in learningStore.weakPoints"
                :key="point.knowledge_point_id"
                type="danger"
                effect="light"
                class="weak-tag"
              >
                <span>{{ point.name }}</span>
                <strong>{{ Math.round(point.mastery * 100) }}%</strong>
              </el-tag>
            </div>
            <el-empty
              v-else
              description="暂无薄弱知识点"
              :image-size="76"
            />
          </el-card>
        </el-col>
      </el-row>
    </template>
  </section>
</template>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.welcome-panel {
  position: relative;
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  gap: 32px;
  padding: clamp(22px, 3vw, 30px);
  overflow: hidden;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background:
    linear-gradient(
      110deg,
      color-mix(in srgb, var(--app-primary-soft) 82%, var(--app-surface)),
      var(--app-surface) 58%
    );
  box-shadow: var(--app-shadow);
}

.welcome-panel::before {
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: var(--app-primary);
  content: "";
}

.welcome-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  justify-content: center;
}

.welcome-heading {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.welcome-heading h1 {
  margin: 0;
  color: var(--app-text);
  font-size: clamp(26px, 2.8vw, 36px);
  font-weight: 760;
  letter-spacing: 0;
  line-height: 1.2;
}

.welcome-badge {
  display: inline-flex;
  min-height: 25px;
  align-items: center;
  padding: 0 9px;
  border: 1px solid color-mix(in srgb, var(--app-success) 30%, transparent);
  border-radius: 999px;
  color: var(--app-success);
  background: color-mix(in srgb, var(--app-success) 8%, transparent);
  font-size: 11px;
  font-weight: 700;
}

.welcome-description {
  margin: 10px 0 0;
  color: var(--app-text-soft);
  font-size: 14px;
  line-height: 1.6;
}

.current-content {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-top: 20px;
  color: var(--app-muted);
  font-size: 12px;
}

.current-content strong {
  overflow: hidden;
  color: var(--app-text);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.current-content strong::before {
  display: inline-block;
  width: 6px;
  height: 6px;
  margin-right: 8px;
  border-radius: 50%;
  background: var(--app-primary);
  content: "";
  vertical-align: 1px;
}

.welcome-side {
  display: flex;
  width: min(420px, 46%);
  flex: none;
  flex-direction: column;
  gap: 10px;
}

.welcome-stats {
  display: flex;
  align-items: stretch;
  gap: 10px;
}

.welcome-stat {
  display: flex;
  min-width: 0;
  flex: 1;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: color-mix(in srgb, var(--app-surface) 86%, transparent);
}

.stat-symbol,
.weekly-icon {
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 8px;
}

.stat-symbol {
  width: 36px;
  height: 36px;
  font-size: 17px;
}

.weekly-icon {
  width: 42px;
  height: 42px;
  font-size: 20px;
}

.blue { color: var(--app-primary); background: var(--app-primary-soft); }
.green {
  color: var(--app-success);
  background: color-mix(in srgb, var(--app-success) 10%, transparent);
}
.yellow {
  color: var(--app-warning);
  background: color-mix(in srgb, var(--app-warning) 10%, transparent);
}

.welcome-stat > div {
  display: flex;
  flex-direction: column;
}

.welcome-stat small {
  color: var(--app-muted);
  font-size: 11px;
}

.welcome-stat strong {
  margin-top: 3px;
  color: var(--app-text);
  font-size: 15px;
  line-height: 1.3;
}

.path-entry {
  display: flex;
  min-height: 48px;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 8px 14px;
  border: 1px solid color-mix(in srgb, var(--app-primary) 20%, var(--app-border));
  border-radius: 8px;
  color: var(--app-text);
  text-align: left;
  background: var(--app-surface);
  cursor: pointer;
  transition:
    border-color 0.16s ease,
    background 0.16s ease;
}

.path-entry:hover {
  border-color: var(--app-primary);
  background: var(--app-primary-soft);
}

.path-entry > span {
  display: flex;
  min-width: 0;
  flex-direction: column;
}

.path-entry small {
  color: var(--app-muted);
  font-size: 10px;
  font-weight: 650;
}

.path-entry strong {
  margin-top: 2px;
  overflow: hidden;
  color: var(--app-text);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.path-entry > .el-icon {
  flex: none;
  color: var(--app-primary);
  font-size: 17px;
}

.dashboard-skeleton {
  min-height: 500px;
  padding: 24px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
  box-shadow: var(--app-shadow);
}

.dashboard-row {
  width: 100%;
}

.dashboard-row + .dashboard-row {
  margin-top: 2px;
}

.dashboard-row :deep(.el-col) {
  display: flex;
}

.dashboard-card {
  width: 100%;
  height: 100%;
  overflow: hidden;
  border-color: var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
  box-shadow: var(--app-shadow);
  transition:
    border-color 0.16s ease,
    box-shadow 0.16s ease;
}

.dashboard-card:hover {
  border-color: color-mix(in srgb, var(--app-primary) 18%, var(--app-border));
  box-shadow: var(--app-shadow-raised);
}

.dashboard-card :deep(.el-card__header) {
  padding: 17px 20px 14px;
  border-color: var(--app-border);
}

.dashboard-card :deep(.el-card__body) {
  height: calc(100% - 72px);
  padding: 18px 20px 20px;
}

.card-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.card-heading h2 {
  margin: 0;
  color: var(--app-text);
  font-size: 16px;
  font-weight: 720;
  line-height: 1.4;
}

.card-heading p {
  margin: 4px 0 0;
  color: var(--app-muted);
  font-size: 12px;
}

.heading-number {
  min-width: 58px;
  padding: 5px 9px;
  border-radius: 8px;
  color: var(--app-primary);
  background: var(--app-primary-soft);
  font-size: 19px;
  font-weight: 760;
  line-height: 1.25;
  text-align: center;
}

.heading-icon {
  color: var(--app-primary);
  font-size: 22px;
}

.heading-icon.green {
  color: var(--app-success);
  background: transparent;
}

.chart-note {
  padding: 3px 8px;
  border: 1px solid var(--app-border);
  border-radius: 999px;
  color: var(--app-muted);
  background: var(--app-surface-muted);
  font-size: 11px;
}

.chart-card :deep(.el-card__body) {
  min-height: 300px;
}

.dashboard-chart {
  width: 100%;
  height: 300px;
}

.calendar-chart {
  min-height: 280px;
}

.trend-chart {
  min-height: 300px;
}

.recommendation-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
}

.recommendation-card {
  position: relative;
}

.recommendation-card::before {
  position: absolute;
  top: 0;
  right: 20px;
  left: 20px;
  height: 2px;
  border-radius: 0 0 2px 2px;
  background: var(--app-primary);
  content: "";
}

.recommendation-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.recommendation-meta > span {
  color: var(--app-muted);
  font-size: 12px;
}

.recommendation-card h3 {
  margin: 16px 0 0;
  color: var(--app-text);
  font-size: 24px;
  line-height: 1.35;
}

.recommendation-description {
  min-height: 44px;
  margin: 8px 0 18px;
  color: var(--app-text-soft);
  font-size: 13px;
  line-height: 1.65;
}

.mastery-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  color: var(--app-muted);
  font-size: 12px;
}

.mastery-label strong {
  color: var(--app-primary);
  font-size: 14px;
}

.recommendation-reason {
  margin: 18px 0;
  padding: 12px 14px;
  border: 1px solid color-mix(in srgb, var(--app-success) 20%, var(--app-border));
  border-left: 3px solid var(--app-success);
  border-radius: 0 8px 8px 0;
  background: color-mix(in srgb, var(--app-success) 5%, var(--app-surface));
}

.recommendation-reason span {
  color: var(--app-success);
  font-size: 10px;
  font-weight: 700;
}

.recommendation-reason p {
  margin: 5px 0 0;
  color: var(--app-text-soft);
  font-size: 12px;
  line-height: 1.55;
}

.start-button {
  width: 100%;
  height: 42px;
  margin-top: auto;
}

.button-icon {
  margin-left: 6px;
}

.weekly-stats {
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.weekly-stat {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 68px;
  padding: 11px 12px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface-muted);
}

.weekly-stat > div {
  display: grid;
  grid-template-columns: auto auto 1fr;
  align-items: baseline;
  column-gap: 3px;
  min-width: 0;
}

.weekly-stat small {
  display: block;
  grid-column: 1 / -1;
  color: var(--app-muted);
  font-size: 11px;
}

.weekly-stat strong {
  color: var(--app-text);
  font-size: 24px;
  line-height: 1.2;
}

.weekly-stat span:last-child {
  color: var(--app-muted);
  font-size: 11px;
}

.activity-count {
  color: var(--app-muted);
  font-size: 12px;
}

.activity-timeline {
  padding-left: 4px;
}

.activity-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 1px 0 8px;
}

.activity-content > div {
  min-width: 0;
}

.activity-content strong {
  display: block;
  overflow: hidden;
  color: var(--app-text);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.activity-content p {
  margin: 4px 0 0;
  color: var(--app-muted);
  font-size: 12px;
}

.weak-list {
  display: flex;
  align-content: flex-start;
  flex-wrap: wrap;
  gap: 10px;
}

.weak-tag {
  height: 36px;
  padding: 0 11px;
}

.weak-tag strong {
  margin-left: 8px;
}

@media (max-width: 1180px) {
  .welcome-panel {
    align-items: flex-start;
    flex-direction: column;
  }

  .welcome-side {
    width: 100%;
    flex-direction: row;
    align-items: stretch;
  }

  .welcome-stats {
    flex: 1;
  }

  .welcome-stat {
    flex: 1;
  }

  .path-entry {
    width: min(320px, 36%);
    flex: none;
  }

  .dashboard-row :deep(.el-col) {
    margin-bottom: 16px;
  }
}

@media (max-width: 640px) {
  .dashboard-page {
    gap: 12px;
  }

  .welcome-panel {
    gap: 18px;
    padding: 20px 18px;
  }

  .welcome-heading h1 {
    font-size: 26px;
  }

  .welcome-side {
    flex-direction: column;
  }

  .welcome-stats {
    flex-direction: column;
  }

  .welcome-stat {
    width: 100%;
  }

  .path-entry {
    width: 100%;
  }

  .dashboard-card :deep(.el-card__header) {
    padding: 16px;
  }

  .dashboard-card :deep(.el-card__body) {
    padding: 16px;
  }

  .recommendation-card h3 {
    font-size: 21px;
  }

  .activity-content {
    align-items: flex-start;
  }

  .activity-content strong {
    white-space: normal;
  }
}
</style>
