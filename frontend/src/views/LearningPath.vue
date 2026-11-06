<script setup>
import {
  ArrowRight,
  DataAnalysis,
  Promotion,
  Refresh,
} from '@element-plus/icons-vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import {
  analyzeLearning,
  getLearningProgress,
} from '../api/dashboard'
import { getKnowledgeGraph } from '../api/knowledge'
import { useLearningContentStore } from '../stores/learningContent'

const STAGES = ['入门', '基础', '进阶', '精通']
const ESTIMATED_MINUTES = {
  1: 15,
  2: 30,
  3: 45,
  4: 60,
  5: 90,
}
const STATUS_LABELS = {
  completed: '已完成',
  current: '进行中',
  learning: '进行中',
  pending: '待学习',
}

const router = useRouter()
const learningContentStore = useLearningContentStore()

const loading = ref(true)
const loadError = ref(false)
const analysis = ref(null)
const progress = ref(null)
const graph = ref(null)
const expandedId = ref('')

const masteryMap = computed(() => analysis.value?.mastery_map || {})
const learningGoalPriorities = computed(() => {
  const explicit = analysis.value?.goal_priorities
  if (Array.isArray(explicit) && explicit.length) {
    return explicit.filter(Boolean)
  }
  const goal = String(analysis.value?.learning_goal || '')
  return [
    ...new Set(
      goal
        .split(/[、,，;；>→]+/)
        .map((item) => item.replace(/^\d+[.、\s]*/, '').trim())
        .filter(Boolean),
    ),
  ]
})
const graphNodeMap = computed(
  () =>
    new Map(
      (graph.value?.nodes || []).map((node) => [node.id, node]),
    ),
)
const recommendedId = computed(
  () =>
    analysis.value?.recommendations?.[0]?.knowledge_point_id || '',
)
const stageIndex = computed(() => {
  const level = progress.value?.overall_level
  if (level === '精通' || level === '高级' || level === '熟练') return 3
  if (level === '进阶') return 2
  if (level === '基础') return 1
  return 0
})

const timelineItems = computed(() => {
  if (!analysis.value || !graph.value) return []
  const path = analysis.value.learning_path || []
  const completedIds = new Set()
  for (const step of path) {
    const node = graphNodeMap.value.get(step.knowledge_point_id)
    for (const prerequisite of node?.prerequisites || []) {
      if ((masteryMap.value[prerequisite] || 0) >= 0.8) {
        completedIds.add(prerequisite)
      }
    }
  }

  const completedItems = graph.value.nodes
    .filter((node) => completedIds.has(node.id))
    .map((node) => ({
      knowledgePointId: node.id,
      name: node.name,
      category: node.category,
      difficulty: node.difficulty,
      estimatedTime:
        ESTIMATED_MINUTES[node.difficulty] ||
        ESTIMATED_MINUTES[5],
      mastery: masteryMap.value[node.id] || 0,
      status: 'completed',
      isCurrent: false,
    }))

  const pathItems = path.map((step) => {
    const mastery = masteryMap.value[step.knowledge_point_id] || 0
    const isCurrent =
      step.knowledge_point_id === recommendedId.value
    let status = 'pending'
    if (mastery >= 0.8) status = 'completed'
    else if (isCurrent) status = 'current'
    else if (mastery >= 0.3) status = 'learning'
    return {
      knowledgePointId: step.knowledge_point_id,
      name: step.name,
      category:
        graphNodeMap.value.get(step.knowledge_point_id)?.category ||
        graph.value?.title ||
        '学习内容',
      difficulty: step.difficulty,
      estimatedTime: step.estimated_time,
      mastery,
      status,
      isCurrent,
    }
  })
  return [...completedItems, ...pathItems]
})

const primaryRecommendation = computed(
  () => analysis.value?.recommendations?.[0] || null,
)
const reasonText = computed(
  () =>
    primaryRecommendation.value?.reason ||
    '系统会结合前置知识、当前掌握度和最近发展区持续调整学习顺序。',
)

onMounted(loadData)

watch(
  () => learningContentStore.activeSubject,
  () => loadData(),
)

async function loadData() {
  loading.value = true
  loadError.value = false
  expandedId.value = ''
  try {
    const subject = learningContentStore.activeSubject
    const [graphData, analysisData, progressData] = await Promise.all([
      getKnowledgeGraph(subject),
      analyzeLearning(subject),
      getLearningProgress(subject),
    ])
    graph.value = graphData
    analysis.value = analysisData
    progress.value = progressData
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

function toggleNode(node) {
  expandedId.value =
    expandedId.value === node.knowledgePointId
      ? ''
      : node.knowledgePointId
}

function nodeDetail(node) {
  return graphNodeMap.value.get(node.knowledgePointId)
}

function statusLabel(status) {
  return STATUS_LABELS[status] || '待学习'
}

function statusDot(status) {
  if (status === 'completed') return '✓'
  if (status === 'current' || status === 'learning') return '●'
  return '○'
}

function timelineType(status) {
  if (status === 'completed') return 'success'
  if (status === 'current') return 'primary'
  if (status === 'learning') return 'warning'
  return 'info'
}

function masteryPercent(knowledgePointId) {
  return Math.round((masteryMap.value[knowledgePointId] || 0) * 100)
}

function startLearning(node) {
  router.push({
    path: '/knowledge',
    query: { kp: node.knowledgePointId },
  })
}

function startPractice(node) {
  router.push({
    path: '/practice',
    query: { kp: node.knowledgePointId },
  })
}
</script>

<template>
  <section class="learning-path-page">
    <header class="page-heading">
      <div>
        <p class="page-kicker">ADAPTIVE LEARNING PATH</p>
        <h1>学习路径</h1>
        <span>
          {{ learningContentStore.activeTitle }}：按照知识依赖与当前掌握度，
          逐步完成你的个性化计划。
        </span>
      </div>
      <el-button
        :icon="Refresh"
        :loading="loading"
        @click="loadData"
      >
        刷新学习路径
      </el-button>
    </header>

    <div v-if="loading" class="path-loading">
      <el-skeleton :rows="11" animated />
    </div>

    <div v-else-if="loadError" class="surface-panel empty-panel">
      <el-empty description="学习路径加载失败" :image-size="92">
        <el-button :icon="Refresh" @click="loadData">重新加载</el-button>
      </el-empty>
    </div>

    <template v-else>
      <section
        v-if="analysis?.learning_goal"
        class="path-context"
        aria-label="个性化路径依据"
      >
        <div class="path-goal-heading">
          <span>本次学习目标优先级</span>
          <div class="path-goal-priorities">
            <span
              v-for="(goal, index) in learningGoalPriorities"
              :key="goal"
              class="path-goal-priority"
            >
              <b>{{ index + 1 }}</b>
              {{ goal }}
            </span>
          </div>
        </div>
        <p v-if="analysis.path_summary">
          {{ analysis.path_summary }}
        </p>
      </section>

      <el-card shadow="never" class="stage-card">
        <div class="stage-heading">
          <div>
            <span>当前学习阶段</span>
            <strong>{{ STAGES[stageIndex] }}</strong>
          </div>
          <div class="stage-progress">
            综合掌握度
            <b>{{ Math.round((progress?.overall_mastery || 0) * 100) }}%</b>
          </div>
        </div>
        <el-steps :active="stageIndex" finish-status="success" align-center>
          <el-step
            v-for="stage in STAGES"
            :key="stage"
            :title="stage"
          />
        </el-steps>
      </el-card>

      <section class="timeline-section">
        <header class="timeline-heading">
          <div>
            <h2>个性化学习路径</h2>
            <span>{{ timelineItems.length }} 个路径节点</span>
          </div>
          <div class="status-legend">
            <span><i class="done">✓</i>已完成</span>
            <span><i class="active">●</i>进行中</span>
            <span><i class="pending">○</i>待学习</span>
          </div>
        </header>

        <el-timeline v-if="timelineItems.length" class="path-timeline">
          <el-timeline-item
            v-for="node in timelineItems"
            :key="`${node.status}-${node.knowledgePointId}`"
            :type="timelineType(node.status)"
            :hollow="node.status === 'pending'"
            size="large"
          >
            <template #dot>
              <span
                class="timeline-dot"
                :class="node.status"
              >
                {{ statusDot(node.status) }}
              </span>
            </template>

            <el-card
              shadow="never"
              class="path-node-card"
              :class="{
                current: node.isCurrent,
                completed: node.status === 'completed',
              }"
              @click="toggleNode(node)"
            >
              <header class="node-heading">
                <div>
                  <div class="node-tags">
                    <el-tag size="small" effect="plain">
                      {{ node.category }}
                    </el-tag>
                    <el-tag
                      size="small"
                      :type="
                        node.status === 'completed'
                          ? 'success'
                          : node.status === 'current'
                            ? 'primary'
                            : 'info'
                      "
                      effect="light"
                    >
                      {{ statusLabel(node.status) }}
                    </el-tag>
                  </div>
                  <h3>{{ node.name }}</h3>
                </div>
                <div class="node-meta">
                  <span>{{ node.estimatedTime }} 分钟</span>
                  <strong>{{ masteryPercent(node.knowledgePointId) }}%</strong>
                </div>
              </header>

              <el-progress
                :percentage="masteryPercent(node.knowledgePointId)"
                :stroke-width="7"
                :show-text="false"
                :color="
                  node.status === 'completed'
                    ? '#149A76'
                    : node.isCurrent
                      ? '#246BFE'
                      : '#D9831A'
                "
              />

              <transition name="detail-expand">
                <div
                  v-if="expandedId === node.knowledgePointId"
                  class="node-detail"
                  @click.stop
                >
                  <p>
                    {{
                      nodeDetail(node)?.description ||
                      '该知识点正在等待进一步学习。'
                    }}
                  </p>
                  <div
                    v-if="nodeDetail(node)?.resources?.length"
                    class="resource-links"
                  >
                    <a
                      v-for="resource in nodeDetail(node).resources"
                      :key="resource.url"
                      :href="resource.url"
                      target="_blank"
                      rel="noreferrer"
                    >
                      {{ resource.title }}
                    </a>
                  </div>
                  <div class="node-actions">
                    <el-button
                      :icon="DataAnalysis"
                      @click="startLearning(node)"
                    >
                      开始学习
                    </el-button>
                    <el-button
                      type="primary"
                      :icon="Promotion"
                      @click="startPractice(node)"
                    >
                      开始练习
                    </el-button>
                  </div>
                </div>
              </transition>
            </el-card>
          </el-timeline-item>
        </el-timeline>

        <el-empty
          v-else
          description="当前知识图谱已全部掌握"
          :image-size="92"
        />
      </section>

      <el-card shadow="never" class="reason-card">
        <div class="reason-icon">
          <el-icon><DataAnalysis /></el-icon>
        </div>
        <div class="reason-copy">
          <span>为什么推荐这条路径</span>
          <h2>{{ primaryRecommendation?.name || '持续巩固学习成果' }}</h2>
          <p>{{ reasonText }}</p>
        </div>
        <el-button
          type="primary"
          plain
          :loading="loading"
          @click="loadData"
        >
          重新生成路径
          <el-icon class="button-icon"><ArrowRight /></el-icon>
        </el-button>
      </el-card>
    </template>
  </section>
</template>

<style scoped>
.learning-path-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.path-loading {
  min-height: 500px;
  padding: 24px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
}

.stage-card {
  border-color: var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
}

.path-context {
  display: grid;
  gap: 10px;
  margin-bottom: 16px;
  padding: 16px 18px;
  border: 1px solid color-mix(in srgb, var(--app-primary) 22%, var(--app-border));
  border-left: 3px solid var(--app-primary);
  border-radius: 8px;
  background:
    linear-gradient(100deg, var(--app-primary-soft), transparent 68%),
    var(--app-surface);
}

.path-context > div {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 14px;
}

.path-context span {
  color: var(--app-primary-strong);
  font-size: 11px;
  font-weight: 750;
}

.path-context strong {
  color: var(--app-text);
  font-size: 14px;
  line-height: 1.6;
}

.path-goal-heading {
  align-items: flex-start;
}

.path-goal-priorities {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-wrap: wrap;
  gap: 7px;
}

.path-goal-priority {
  display: inline-flex;
  min-height: 28px;
  align-items: center;
  gap: 6px;
  padding: 4px 9px 4px 5px;
  border: 1px solid color-mix(in srgb, var(--app-primary) 24%, var(--app-border));
  border-radius: 6px;
  color: var(--app-text-soft);
  background: var(--app-surface);
  font-size: 11px;
  font-weight: 650;
  line-height: 1.4;
}

.path-goal-priority b {
  display: grid;
  width: 19px;
  height: 19px;
  flex: 0 0 19px;
  place-items: center;
  border-radius: 4px;
  color: #fff;
  background: var(--app-primary);
  font-size: 10px;
}

.path-context p {
  margin: 0;
  color: var(--app-text-soft);
  font-size: 12px;
  line-height: 1.7;
}

.stage-card :deep(.el-card__body) {
  padding: 20px clamp(18px, 3vw, 34px) 18px;
}

.stage-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 24px;
}

.stage-heading > div:first-child {
  display: flex;
  flex-direction: column;
}

.stage-heading span {
  color: var(--app-muted);
  font-size: 10px;
}

.stage-heading strong {
  margin-top: 4px;
  color: var(--app-text);
  font-size: 28px;
  line-height: 1.2;
}

.stage-progress {
  color: var(--app-muted);
  font-size: 11px;
}

.stage-progress b {
  margin-left: 6px;
  color: #246BFE;
  font-size: 18px;
}

.timeline-section {
  padding: 20px clamp(16px, 3vw, 30px) 8px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
}

.timeline-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 22px;
}

.timeline-heading h2 {
  margin: 0;
  color: var(--app-text);
  font-size: 17px;
}

.timeline-heading > div:first-child > span {
  display: block;
  margin-top: 4px;
  color: var(--app-muted);
  font-size: 10px;
}

.status-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.status-legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--app-muted);
  font-size: 10px;
}

.status-legend i {
  font-style: normal;
}

.status-legend .done { color: #149A76; }
.status-legend .active { color: #246BFE; }
.status-legend .pending { color: #909399; }

.path-timeline {
  padding-left: 10px;
}

.path-timeline :deep(.el-timeline-item) {
  padding-bottom: 16px;
}

.timeline-dot {
  display: grid;
  width: 24px;
  height: 24px;
  place-items: center;
  border: 2px solid;
  border-radius: 50%;
  background: var(--app-surface);
  font-size: 10px;
  font-weight: 800;
}

.timeline-dot.completed {
  border-color: #149A76;
  color: #149A76;
  background: rgba(20, 154, 118, 0.1);
}

.timeline-dot.current {
  border-color: #246BFE;
  color: #fff;
  background: #246BFE;
  box-shadow: 0 0 0 5px rgba(36, 107, 254, 0.1);
}

.timeline-dot.learning {
  border-color: #D9831A;
  color: #D9831A;
}

.timeline-dot.pending {
  border-color: #c0c4cc;
  color: #909399;
}

.path-node-card {
  border-color: var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
  cursor: pointer;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.path-node-card:hover {
  border-color: rgba(36, 107, 254, 0.55);
}

.path-node-card.current {
  border-color: #246BFE;
  box-shadow: 0 0 0 2px rgba(36, 107, 254, 0.08);
}

.path-node-card.completed {
  border-color: rgba(20, 154, 118, 0.35);
}

.path-node-card :deep(.el-card__body) {
  padding: 16px 18px;
}

.node-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.node-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.node-heading h3 {
  margin: 8px 0 0;
  color: var(--app-text);
  font-size: 15px;
}

.node-meta {
  display: flex;
  flex: none;
  align-items: flex-end;
  flex-direction: column;
  gap: 5px;
}

.node-meta span {
  color: var(--app-muted);
  font-size: 10px;
}

.node-meta strong {
  color: #246BFE;
  font-size: 17px;
}

.node-detail {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--app-border);
}

.node-detail > p {
  margin: 0;
  color: var(--app-muted);
  font-size: 12px;
  line-height: 1.7;
}

.resource-links {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 12px;
}

.resource-links a {
  color: #246BFE;
  font-size: 11px;
  text-decoration: none;
}

.resource-links a:hover {
  text-decoration: underline;
}

.node-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.reason-card {
  border-color: rgba(36, 107, 254, 0.25);
  border-radius: 8px;
  background: rgba(36, 107, 254, 0.04);
}

.reason-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  gap: 18px;
}

.reason-icon {
  display: grid;
  width: 46px;
  height: 46px;
  flex: 0 0 46px;
  place-items: center;
  border-radius: 8px;
  color: #246BFE;
  background: rgba(36, 107, 254, 0.1);
  font-size: 22px;
}

.reason-copy {
  min-width: 0;
  flex: 1;
}

.reason-copy > span {
  color: #246BFE;
  font-size: 9px;
  font-weight: 750;
}

.reason-copy h2 {
  margin: 4px 0 0;
  color: var(--app-text);
  font-size: 16px;
}

.reason-copy p {
  margin: 6px 0 0;
  color: var(--app-muted);
  font-size: 12px;
  line-height: 1.65;
}

.button-icon {
  margin-left: 5px;
}

.detail-expand-enter-active,
.detail-expand-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.detail-expand-enter-from,
.detail-expand-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

@media (max-width: 800px) {
  .stage-heading,
  .timeline-heading,
  .reason-card :deep(.el-card__body) {
    align-items: flex-start;
    flex-direction: column;
  }

  .timeline-heading {
    gap: 12px;
  }

  .reason-card .el-button {
    width: 100%;
  }

  .stage-card :deep(.el-step__title) {
    font-size: 11px;
  }
}

@media (max-width: 560px) {
  .timeline-section {
    padding-right: 12px;
    padding-left: 12px;
  }

  .node-heading {
    flex-direction: column;
  }

  .node-meta {
    width: 100%;
    align-items: center;
    flex-direction: row;
    justify-content: space-between;
  }

  .node-actions {
    flex-direction: column;
  }

  .node-actions .el-button {
    width: 100%;
    margin-left: 0;
  }
}
</style>
