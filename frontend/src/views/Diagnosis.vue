<script setup>
import {
  Clock,
  DataAnalysis,
  EditPen,
  Promotion,
  Refresh,
  Timer,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import {
  analyzeLearning,
  getLearningProgress,
} from '../api/dashboard'
import {
  getDiagnosisSnapshots,
  recordSmartDiagnosis,
} from '../api/diagnosis'
import { getKnowledgeGraph } from '../api/knowledge'
import {
  getPracticeQuestions,
  submitAnswer,
} from '../api/practice'
import RadarChart from '../components/RadarChart.vue'
import { useLearningContentStore } from '../stores/learningContent'
import { useUserStore } from '../stores/user'

const router = useRouter()
const userStore = useUserStore()
const learningContentStore = useLearningContentStore()

const stage = ref(0)
const questions = ref([])
const currentIndex = ref(0)
const answer = ref('')
const answerStartedAt = ref(Date.now())
const loadingQuestions = ref(false)
const submitting = ref(false)
const loadingResult = ref(false)
const diagnosisError = ref(false)
const resultError = ref(false)
const result = ref(null)
const categoryRows = ref([])
const graphNodes = ref([])
const diagnosisSnapshots = ref([])
const diagnosisCategories = ref([])
const historyLoading = ref(false)
const smartDiagnosisReference = ref('')

const currentQuestion = computed(
  () => questions.value[currentIndex.value] || null,
)
const currentCategory = computed(
  () =>
    graphNodes.value.find(
      (node) => node.id === currentQuestion.value?.knowledge_point_id,
    )?.category ||
    learningContentStore.activeTitle,
)
const activeStep = computed(() => stage.value)
const progressPercentage = computed(() => {
  if (!questions.value.length) return 0
  return Math.round((currentIndex.value / questions.value.length) * 100)
})
const canSubmit = computed(
  () => Boolean(answer.value.trim()) && !submitting.value,
)
const radarIndicators = computed(() =>
  categoryRows.value.map((item) => ({ name: item.name, max: 1 })),
)
const radarValues = computed(() =>
  categoryRows.value.map((item) => item.mastery),
)
const historyIndicators = computed(() =>
  diagnosisCategories.value.map((name) => ({ name, max: 1 })),
)
const historySeries = computed(() =>
  diagnosisSnapshots.value.map((snapshot) => ({
    name: formatSnapshotLabel(snapshot),
    values: diagnosisCategories.value.map(
      (category) => snapshot.category_mastery[category] || 0,
    ),
  })),
)
const overallLevel = computed(() => result.value?.overallLevel || '入门')
const overallPercent = computed(() =>
  Math.round((result.value?.overallMastery || 0) * 100),
)

watch(
  () => currentQuestion.value?.id,
  () => {
    answer.value = ''
    answerStartedAt.value = Date.now()
  },
)

watch(
  () => learningContentStore.activeSubject,
  () => {
    stage.value = 0
    questions.value = []
    currentIndex.value = 0
    result.value = null
    categoryRows.value = []
    diagnosisError.value = false
    resultError.value = false
    graphNodes.value = []
    loadDiagnosisHistory()
  },
)

onMounted(loadDiagnosisHistory)

function shuffle(items) {
  const resultItems = [...items]
  for (let index = resultItems.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1))
    ;[resultItems[index], resultItems[swapIndex]] = [
      resultItems[swapIndex],
      resultItems[index],
    ]
  }
  return resultItems
}

async function loadDiagnosisHistory() {
  historyLoading.value = true
  try {
    const data = await getDiagnosisSnapshots(
      learningContentStore.activeSubject,
    )
    diagnosisCategories.value = data.categories || []
    diagnosisSnapshots.value = data.snapshots || []
  } catch {
    diagnosisCategories.value = []
    diagnosisSnapshots.value = []
  } finally {
    historyLoading.value = false
  }
}

function formatSnapshotLabel(snapshot) {
  const date = new Date(snapshot.created_at)
  const timestamp = Number.isNaN(date.getTime())
    ? ''
    : date.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      })
  return `${snapshot.label}${timestamp ? ` · ${timestamp}` : ''}`
}

function createDiagnosisReference() {
  return (
    crypto.randomUUID?.() ||
    `smart-${Date.now()}-${Math.random().toString(16).slice(2)}`
  )
}

async function startDiagnosis() {
  loadingQuestions.value = true
  diagnosisError.value = false
  result.value = null
  categoryRows.value = []
  try {
    if (!userStore.profile?.id) {
      await userStore.fetchProfile()
    }

    const subject = learningContentStore.activeSubject
    const graph = await getKnowledgeGraph(subject)
    graphNodes.value = graph.nodes
    const diagnosisPoints = selectDiagnosisPoints(graph.nodes)
    if (!diagnosisPoints.length) {
      diagnosisError.value = true
      ElMessage.error('当前学习内容暂无可用于诊断的知识点')
      return
    }

    const questionsPerPoint = 4
    const minimumQuestions = 8
    const responses = await Promise.allSettled(
      diagnosisPoints.map((pointId) =>
        getPracticeQuestions(pointId, {
          count: questionsPerPoint,
        }),
      ),
    )
    const collected = responses.flatMap((response) =>
      response.status === 'fulfilled'
        ? response.value.questions
        : [],
    )
    if (collected.length < minimumQuestions) {
      diagnosisError.value = true
      ElMessage.error('当前可用诊断题目不足，请稍后重试')
      return
    }

    questions.value = shuffle(collected)
    currentIndex.value = 0
    answerStartedAt.value = Date.now()
    smartDiagnosisReference.value = createDiagnosisReference()
    stage.value = 1
  } catch {
    diagnosisError.value = true
  } finally {
    loadingQuestions.value = false
  }
}

async function handleSubmit() {
  if (!canSubmit.value || !currentQuestion.value) return

  submitting.value = true
  const timeSpent = Math.max(
    1,
    Math.round((Date.now() - answerStartedAt.value) / 1000),
  )
  try {
    await submitAnswer({
      question_id: currentQuestion.value.id,
      answer: answer.value.trim(),
      time_spent: timeSpent,
    })

    if (currentIndex.value < questions.value.length - 1) {
      currentIndex.value += 1
    } else {
      await finishDiagnosis()
    }
  } finally {
    submitting.value = false
  }
}

async function finishDiagnosis() {
  stage.value = 2
  loadingResult.value = true
  resultError.value = false
  try {
    if (smartDiagnosisReference.value) {
      try {
        await recordSmartDiagnosis(
          learningContentStore.activeSubject,
          smartDiagnosisReference.value,
        )
      } catch {
        // 快照失败不阻断本次诊断结果展示。
      }
    }
    const [analysis, progress] = await Promise.all([
      analyzeLearning(learningContentStore.activeSubject),
      getLearningProgress(learningContentStore.activeSubject),
    ])
    await loadDiagnosisHistory()
    categoryRows.value = buildCategoryRows(progress.points)
    result.value = {
      overallLevel: mapOverallLevel(progress.overall_level),
      overallMastery: progress.overall_mastery ?? analysis.overall_mastery,
      answeredCount: questions.value.length,
    }
  } catch {
    resultError.value = true
    ElMessage.error('诊断结果生成失败，请稍后重试')
  } finally {
    loadingResult.value = false
  }
}

function selectDiagnosisPoints(nodes) {
  const targetCount = 3
  const categories = [...new Set(nodes.map((node) => node.category))]
  const selected = []
  for (const category of categories) {
    const candidates = nodes
      .filter((node) => node.category === category)
      .sort((left, right) => left.difficulty - right.difficulty)
    if (candidates.length) {
      selected.push(
        candidates[Math.min(1, candidates.length - 1)].id,
      )
    }
    if (selected.length >= targetCount) break
  }

  for (const node of nodes) {
    if (selected.length >= targetCount) break
    if (!selected.includes(node.id)) selected.push(node.id)
  }
  return selected
}

function buildCategoryRows(points) {
  const categoryNames = [
    ...new Set(points.map((point) => point.category)),
  ].slice(0, 8)
  return categoryNames.map((name) => {
    const categoryPoints = points.filter(
      (point) => point.category === name,
    )
    return {
      name,
      mastery: categoryPoints.length
        ? categoryPoints.reduce(
            (total, point) => total + point.mastery,
            0,
          ) / categoryPoints.length
        : 0,
      count: categoryPoints.length,
    }
  })
}

function mapOverallLevel(level) {
  if (level === '高级' || level === '熟练') return '精通'
  if (level === '进阶') return '进阶'
  if (level === '基础') return '基础'
  return '入门'
}

async function restartDiagnosis() {
  stage.value = 0
  questions.value = []
  currentIndex.value = 0
  result.value = null
  categoryRows.value = []
  smartDiagnosisReference.value = ''
  resultError.value = false
  await nextTick()
  await startDiagnosis()
}

function progressColor(mastery) {
  if (mastery >= 0.8) return '#149A76'
  if (mastery >= 0.3) return '#D9831A'
  return '#D94F59'
}

function formatOption(option) {
  return option.trim()
}

function optionValue(option) {
  return option.trim().slice(0, 1)
}
</script>

<template>
  <section class="diagnosis-page">
    <header class="page-heading">
      <div>
        <p class="page-kicker">SMART DIAGNOSIS</p>
        <h1>智能诊断</h1>
        <span>
          用一组短测快速定位当前
          {{ learningContentStore.activeTitle }} 的学习起点。
        </span>
      </div>
    </header>

    <el-card shadow="never" class="steps-card">
      <el-steps :active="activeStep" finish-status="success" align-center>
        <el-step title="开始诊断" />
        <el-step title="完成答题" />
        <el-step title="查看结果" />
      </el-steps>
    </el-card>

    <el-card
      v-if="historyLoading || diagnosisSnapshots.length"
      shadow="never"
      class="history-radar-card"
    >
      <template #header>
        <div class="history-heading">
          <div>
            <h2>历次诊断学习情况</h2>
            <p>初始诊断与每次智能诊断掌握度对比</p>
          </div>
          <span>{{ diagnosisSnapshots.length }} 次记录</span>
        </div>
      </template>
      <el-skeleton v-if="historyLoading" :rows="6" animated />
      <template v-else>
        <RadarChart
          :indicators="historyIndicators"
          :series-data="historySeries"
          :height="390"
          title="历次诊断"
        />
        <div class="history-records">
          <div
            v-for="snapshot in diagnosisSnapshots"
            :key="snapshot.id"
            class="history-record"
          >
            <span>{{ formatSnapshotLabel(snapshot) }}</span>
            <strong>
              {{ Math.round(snapshot.overall_mastery * 100) }}%
            </strong>
          </div>
        </div>
      </template>
    </el-card>

    <transition name="stage-fade" mode="out-in">
      <div v-if="stage === 0" key="welcome" class="stage-wrap">
        <el-card shadow="never" class="welcome-card">
          <div class="diagnosis-symbol">
            <el-icon><DataAnalysis /></el-icon>
          </div>
          <h2>{{ learningContentStore.activeTitle }} 能力诊断</h2>
          <p class="welcome-description">
            通过 10-15 道题快速定位你的知识薄弱点，AI
            将为你生成专属学习路径
          </p>

          <div class="diagnosis-meta">
            <span>
              <el-icon><Clock /></el-icon>
              约 5-10 分钟
            </span>
            <span>
              <el-icon><EditPen /></el-icon>
              10-15 道题
            </span>
            <span>
              <el-icon><DataAnalysis /></el-icon>
              覆盖核心知识模块
            </span>
          </div>

          <el-button
            type="primary"
            size="large"
            class="primary-action"
            :loading="loadingQuestions"
            @click="startDiagnosis"
          >
            开始诊断
            <el-icon class="action-icon"><Promotion /></el-icon>
          </el-button>

          <el-alert
            v-if="diagnosisError"
            type="error"
            :closable="false"
            show-icon
            title="诊断题目加载失败，请检查网络后重试"
          />
        </el-card>
      </div>

      <div v-else-if="stage === 1" key="answering" class="stage-wrap">
        <div v-if="currentQuestion" class="answer-shell">
          <div class="answer-progress">
            <div class="progress-copy">
              <span>诊断进度</span>
              <strong>
                第 {{ currentIndex + 1 }} / {{ questions.length }} 题
              </strong>
            </div>
            <el-progress
              :percentage="progressPercentage"
              :stroke-width="8"
              :show-text="false"
              color="#246BFE"
            />
          </div>

          <transition name="question-slide" mode="out-in">
            <el-card
              :key="currentQuestion.id"
              shadow="never"
              class="question-card"
            >
              <div class="question-meta">
                <el-tag effect="plain">
                  {{ currentCategory }}
                </el-tag>
                <span>难度 {{ currentQuestion.difficulty }}</span>
              </div>

              <h2 class="question-title">
                {{ currentQuestion.question }}
              </h2>

              <el-radio-group
                v-if="currentQuestion.type === 'choice'"
                v-model="answer"
                class="answer-options"
              >
                <el-radio
                  v-for="option in currentQuestion.options"
                  :key="option"
                  :value="optionValue(option)"
                  border
                >
                  {{ formatOption(option) }}
                </el-radio>
              </el-radio-group>

              <el-input
                v-else
                v-model="answer"
                :type="
                  currentQuestion.type === 'short_answer'
                    ? 'textarea'
                    : 'text'
                "
                :rows="
                  currentQuestion.type === 'short_answer'
                    ? 5
                    : undefined
                "
                :placeholder="
                  currentQuestion.type === 'short_answer'
                    ? '写下你的理解'
                    : '填写答案'
                "
                maxlength="2000"
                show-word-limit
              />

              <div class="answer-actions">
                <span>
                  <el-icon><Timer /></el-icon>
                  系统会记录本题作答时间
                </span>
                <el-button
                  type="primary"
                  :loading="submitting"
                  :disabled="!canSubmit"
                  @click="handleSubmit"
                >
                  {{ currentIndex === questions.length - 1 ? '完成诊断' : '提交答案' }}
                </el-button>
              </div>
            </el-card>
          </transition>
        </div>
      </div>

      <div v-else key="result" class="stage-wrap result-stage">
        <div v-if="loadingResult" class="result-loading">
          <el-skeleton :rows="10" animated />
        </div>

        <template v-else-if="result">
          <el-row :gutter="18">
            <el-col :xs="24" :lg="11">
              <el-card shadow="never" class="result-card">
                <template #header>
                  <div class="result-card-heading">
                    <div>
                      <h2>知识掌握雷达</h2>
                      <p>{{ categoryRows.length }} 个核心模块诊断结果</p>
                    </div>
                    <el-icon><DataAnalysis /></el-icon>
                  </div>
                </template>
                <RadarChart
                  :indicators="radarIndicators"
                  :values="radarValues"
                />
              </el-card>
            </el-col>

            <el-col :xs="24" :lg="13">
              <el-card shadow="never" class="result-card evaluation-card">
                <template #header>
                  <div class="result-card-heading">
                    <div>
                      <h2>总体评价</h2>
                      <p>基于本次诊断答题计算</p>
                    </div>
                  </div>
                </template>

                <div class="evaluation-main">
                  <span class="evaluation-level">{{ overallLevel }}</span>
                  <span class="evaluation-percent">{{ overallPercent }}%</span>
                </div>
                <p class="evaluation-copy">
                  已完成 {{ result.answeredCount }}
                  道诊断题。系统已结合正确率、答题效率和近期表现更新掌握度。
                </p>
                <el-progress
                  :percentage="overallPercent"
                  :stroke-width="9"
                  :show-text="false"
                  color="#246BFE"
                />

                <div class="evaluation-actions">
                  <el-button
                    type="primary"
                    @click="router.push('/learning-path')"
                  >
                    查看我的学习路径
                    <el-icon class="action-icon"><Promotion /></el-icon>
                  </el-button>
                  <el-button :icon="Refresh" @click="restartDiagnosis">
                    重新诊断
                  </el-button>
                </div>
              </el-card>
            </el-col>
          </el-row>

          <el-card shadow="never" class="result-card module-card">
            <template #header>
              <div class="result-card-heading">
                <div>
                  <h2>各模块掌握度</h2>
                  <p>颜色越接近绿色表示掌握越扎实</p>
                </div>
              </div>
            </template>

            <div class="module-list">
              <div
                v-for="item in categoryRows"
                :key="item.name"
                class="module-row"
              >
                <span class="module-name">{{ item.name }}</span>
                <el-progress
                  :percentage="Math.round(item.mastery * 100)"
                  :stroke-width="8"
                  :color="progressColor(item.mastery)"
                />
              </div>
            </div>
          </el-card>
        </template>

        <div v-else-if="resultError" class="surface-panel empty-panel">
          <el-empty description="诊断结果加载失败" :image-size="90">
            <el-button :icon="Refresh" @click="finishDiagnosis">
              重新获取结果
            </el-button>
          </el-empty>
        </div>
      </div>
    </transition>
  </section>
</template>

<style scoped>
.diagnosis-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.steps-card {
  border-color: var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
}

.steps-card :deep(.el-card__body) {
  padding: 20px;
}

.history-radar-card {
  border-color: var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
}

.history-radar-card :deep(.el-card__body) {
  padding: 18px 22px 20px;
}

.history-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.history-heading h2 {
  margin: 0;
  color: var(--app-text);
  font-size: 17px;
}

.history-heading p {
  margin: 4px 0 0;
  color: var(--app-muted);
  font-size: 12px;
}

.history-heading > span {
  padding: 4px 9px;
  border: 1px solid var(--app-border);
  border-radius: 6px;
  color: var(--app-muted);
  background: var(--app-surface-muted);
  font-size: 11px;
  white-space: nowrap;
}

.history-records {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-top: 14px;
  border-top: 1px solid var(--app-border);
}

.history-record {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 9px;
  border-radius: 6px;
  color: var(--app-text-soft);
  background: var(--app-surface-muted);
  font-size: 11px;
}

.history-record strong {
  color: var(--app-primary);
}

.stage-wrap {
  min-height: 440px;
}

.welcome-card {
  max-width: 860px;
  margin: 0 auto;
  border-color: var(--app-border);
  border-radius: 8px;
  text-align: center;
  background: var(--app-surface);
}

.welcome-card :deep(.el-card__body) {
  padding: clamp(36px, 6vw, 64px);
}

.diagnosis-symbol {
  display: grid;
  width: 62px;
  height: 62px;
  margin: 0 auto 20px;
  place-items: center;
  border-radius: 8px;
  color: #246BFE;
  background: rgba(36, 107, 254, 0.1);
  font-size: 30px;
}

.welcome-card h2 {
  margin: 0;
  color: var(--app-text);
  font-size: clamp(25px, 3vw, 34px);
}

.welcome-description {
  max-width: 620px;
  margin: 16px auto 0;
  color: var(--app-muted);
  font-size: 14px;
  line-height: 1.8;
}

.diagnosis-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  margin: 28px 0;
}

.diagnosis-meta span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  color: var(--app-muted);
  background: var(--app-surface-muted);
  font-size: 11px;
}

.primary-action {
  min-width: 190px;
  height: 46px;
}

.action-icon {
  margin-left: 6px;
}

.welcome-card .el-alert {
  max-width: 520px;
  margin: 20px auto 0;
}

.answer-shell {
  max-width: 900px;
  margin: 0 auto;
}

.answer-progress {
  margin-bottom: 18px;
}

.progress-copy {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 9px;
}

.progress-copy span {
  color: var(--app-muted);
  font-size: 12px;
}

.progress-copy strong {
  color: var(--app-text);
  font-size: 13px;
}

.question-card {
  border-color: var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
}

.question-card :deep(.el-card__body) {
  padding: clamp(24px, 4vw, 40px);
}

.question-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.question-meta > span {
  color: var(--app-muted);
  font-size: 11px;
}

.question-title {
  margin: 24px 0;
  color: var(--app-text);
  font-size: clamp(18px, 2.2vw, 23px);
  line-height: 1.7;
  white-space: pre-wrap;
}

.answer-options {
  display: flex;
  align-items: stretch;
  flex-direction: column;
  gap: 11px;
}

.answer-options :deep(.el-radio) {
  width: 100%;
  height: auto;
  min-height: 48px;
  margin-right: 0;
  padding: 11px 14px;
}

.answer-options :deep(.el-radio__label) {
  line-height: 1.6;
  white-space: normal;
}

.answer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid var(--app-border);
}

.answer-actions > span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--app-muted);
  font-size: 11px;
}

.answer-actions .el-button {
  min-width: 130px;
  height: 42px;
}

.result-stage {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.result-loading {
  min-height: 420px;
  padding: 24px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
}

.result-card {
  height: 100%;
  border-color: var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
}

.result-card :deep(.el-card__header) {
  border-color: var(--app-border);
}

.result-card-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.result-card-heading h2 {
  margin: 0;
  color: var(--app-text);
  font-size: 16px;
}

.result-card-heading p {
  margin: 4px 0 0;
  color: var(--app-muted);
  font-size: 11px;
}

.result-card-heading > .el-icon {
  color: #246BFE;
  font-size: 22px;
}

.evaluation-card :deep(.el-card__body) {
  display: flex;
  min-height: 330px;
  flex-direction: column;
  justify-content: center;
}

.evaluation-main {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
}

.evaluation-level {
  color: var(--app-text);
  font-size: clamp(36px, 5vw, 58px);
  font-weight: 800;
  line-height: 1;
}

.evaluation-percent {
  color: #246BFE;
  font-size: 28px;
  font-weight: 800;
}

.evaluation-copy {
  margin: 18px 0;
  color: var(--app-muted);
  font-size: 13px;
  line-height: 1.7;
}

.evaluation-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 26px;
}

.module-card {
  margin-top: 0;
}

.module-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px 28px;
}

.module-row {
  display: grid;
  grid-template-columns: 82px minmax(0, 1fr);
  align-items: center;
  gap: 12px;
}

.module-name {
  color: var(--app-text);
  font-size: 12px;
  font-weight: 650;
}

.module-row :deep(.el-progress__text) {
  min-width: 38px;
  color: var(--app-muted);
  font-size: 11px !important;
}

.stage-fade-enter-active,
.stage-fade-leave-active {
  transition: opacity 0.2s ease;
}

.stage-fade-enter-from,
.stage-fade-leave-to {
  opacity: 0;
}

.question-slide-enter-active,
.question-slide-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.question-slide-enter-from {
  opacity: 0;
  transform: translateX(22px);
}

.question-slide-leave-to {
  opacity: 0;
  transform: translateX(-22px);
}

@media (max-width: 980px) {
  .result-stage :deep(.el-col) {
    margin-bottom: 18px;
  }

  .module-list {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .steps-card :deep(.el-step__title) {
    font-size: 11px;
  }

  .steps-card :deep(.el-card__body) {
    padding: 14px 8px;
  }

  .history-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 8px;
  }

  .history-radar-card :deep(.el-card__body) {
    padding: 16px 14px 18px;
  }

  .diagnosis-meta {
    align-items: stretch;
    flex-direction: column;
  }

  .diagnosis-meta span {
    justify-content: center;
  }

  .primary-action {
    width: 100%;
  }

  .answer-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .answer-actions .el-button {
    width: 100%;
  }

  .evaluation-actions {
    flex-direction: column;
  }

  .evaluation-actions .el-button {
    width: 100%;
    margin-left: 0;
  }

  .module-row {
    grid-template-columns: 72px minmax(0, 1fr);
  }
}
</style>
