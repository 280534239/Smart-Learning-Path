<script setup>
import {
  CircleCheck,
  CircleClose,
  Clock,
  EditPen,
  Refresh,
  TrendCharts,
} from '@element-plus/icons-vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { getKnowledgeGraph } from '../api/knowledge'
import { useLearningContentStore } from '../stores/learningContent'
import { usePracticeStore } from '../stores/practice'

const DIFFICULTY_OPTIONS = [
  { value: 1, label: '基础' },
  { value: 2, label: '提高' },
  { value: 3, label: '挑战' },
]

const route = useRoute()
const learningContentStore = useLearningContentStore()
const practiceStore = usePracticeStore()

const pointOptions = ref([])
const selectedPoint = ref(
  typeof route.query.kp === 'string' ? route.query.kp : '',
)
const selectedDifficulty = ref(1)
const answer = ref('')
const currentElapsedSeconds = ref(0)
let timer

const currentQuestion = computed(() => practiceStore.currentQuestion)
const selectedPointName = computed(
  () =>
    pointOptions.value.find(
      (item) => item.value === selectedPoint.value,
    )
      ?.label || '',
)
const currentQuestionNumber = computed(
  () => practiceStore.currentIndex + 1,
)
const accuracyPercent = computed(() =>
  Math.round(practiceStore.accuracy * 100),
)
const displayTime = computed(
  () =>
    practiceStore.totalTimeSeconds +
    (currentQuestion.value && !practiceStore.feedback
      ? currentElapsedSeconds.value
      : 0),
)
const canSubmit = computed(
  () =>
    Boolean(answer.value.trim()) &&
    !practiceStore.submitting &&
    !practiceStore.feedback,
)

watch(
  () => practiceStore.currentQuestion?.id,
  () => {
    answer.value = ''
    currentElapsedSeconds.value = 0
  },
)

watch(
  () => learningContentStore.activeSubject,
  async () => {
    await loadPointOptions()
    await startPractice()
  },
)

onMounted(async () => {
  timer = window.setInterval(() => {
    if (currentQuestion.value && !practiceStore.feedback) {
      currentElapsedSeconds.value += 1
    }
  }, 1000)
  await loadPointOptions()
  await startPractice()
})

onBeforeUnmount(() => {
  window.clearInterval(timer)
})

async function startPractice() {
  if (!selectedPoint.value) return
  answer.value = ''
  currentElapsedSeconds.value = 0
  await practiceStore.startPractice({
    knowledgePointId: selectedPoint.value,
    difficulty: selectedDifficulty.value,
    count: 10,
  })
}

async function loadPointOptions() {
  const graph = await getKnowledgeGraph(
    learningContentStore.activeSubject,
  )
  pointOptions.value = graph.nodes.map((node) => ({
    value: node.id,
    label: node.name,
  }))
  const available = new Set(
    pointOptions.value.map((item) => item.value),
  )
  if (!available.has(selectedPoint.value)) {
    selectedPoint.value = pointOptions.value[0]?.value || ''
  }
}

async function submitCurrentAnswer() {
  if (!canSubmit.value || !currentQuestion.value) return

  await practiceStore.submitCurrentAnswer({
    answer: answer.value.trim(),
    timeSpent: Math.max(1, currentElapsedSeconds.value),
  })
}

function nextQuestion() {
  currentElapsedSeconds.value = 0
  practiceStore.nextQuestion()
}

function questionTypeLabel(type) {
  return {
    choice: '选择题',
    fill_blank: '填空题',
    short_answer: '简答题',
  }[type] || '题目'
}

function optionValue(option) {
  return option.trim().slice(0, 1)
}

function formatDuration(seconds) {
  const safeSeconds = Math.max(0, Math.round(Number(seconds) || 0))
  const minutes = Math.floor(safeSeconds / 60)
  const remainingSeconds = safeSeconds % 60
  if (!minutes) return `${remainingSeconds} 秒`
  return `${minutes} 分 ${remainingSeconds} 秒`
}
</script>

<template>
  <section class="practice-page">
    <header class="page-heading">
      <div>
        <p class="page-kicker">FOCUSED PRACTICE</p>
        <h1>在线练习</h1>
        <span>
          {{ learningContentStore.activeTitle }}：选定知识点和难度，
          开始一组专注练习。
        </span>
      </div>
    </header>

    <el-card shadow="never" class="practice-toolbar">
      <div class="toolbar-fields">
        <label>
          <span>知识点</span>
          <el-select
            v-model="selectedPoint"
            placeholder="选择知识点"
            filterable
          >
            <el-option
              v-for="option in pointOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </label>

        <label>
          <span>难度</span>
          <el-radio-group v-model="selectedDifficulty">
            <el-radio-button
              v-for="option in DIFFICULTY_OPTIONS"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </el-radio-button>
          </el-radio-group>
        </label>
      </div>

      <el-button type="primary" :loading="practiceStore.loading" @click="startPractice">
        开始练习
      </el-button>
    </el-card>

    <el-row :gutter="18" class="practice-layout">
      <el-col :xs="24" :md="17" :lg="18">
        <el-card
          shadow="never"
          class="practice-card"
          :class="{
            'is-correct': practiceStore.feedback?.is_correct,
            'is-wrong':
              practiceStore.feedback &&
              !practiceStore.feedback.is_correct,
          }"
        >
          <div v-if="practiceStore.loading" class="question-loading">
            <el-skeleton :rows="8" animated />
          </div>

          <el-empty
            v-else-if="practiceStore.isFinished"
            description="本组练习已完成"
            :image-size="100"
          >
            <div class="finished-summary">
              <span>正确率 {{ accuracyPercent }}%</span>
              <el-button type="primary" :icon="Refresh" @click="startPractice">
                再练一组
              </el-button>
            </div>
          </el-empty>

          <el-empty
            v-else-if="!currentQuestion"
            description="当前难度暂无可用题目"
            :image-size="90"
          />

          <template v-else>
            <div class="question-progress">
              <div>
                <span>{{ selectedPointName }}</span>
                <strong>
                  第 {{ currentQuestionNumber }} /
                  {{ practiceStore.questions.length }} 题
                </strong>
              </div>
              <el-progress
                :percentage="practiceStore.progressPercentage"
                :stroke-width="6"
                :show-text="false"
                color="#246BFE"
              />
            </div>

            <div class="question-header">
              <div class="question-tags">
                <el-tag effect="plain">
                  {{ questionTypeLabel(currentQuestion.type) }}
                </el-tag>
                <el-tag type="info" effect="plain">
                  难度 {{ currentQuestion.difficulty }}
                </el-tag>
              </div>
              <span class="timer">
                <el-icon><Clock /></el-icon>
                {{ formatDuration(displayTime) }}
              </span>
            </div>

            <h2 class="question-text">{{ currentQuestion.question }}</h2>

            <el-radio-group
              v-if="currentQuestion.type === 'choice'"
              v-model="answer"
              class="practice-options"
              :disabled="Boolean(practiceStore.feedback)"
            >
              <el-radio
                v-for="option in currentQuestion.options"
                :key="option"
                :value="optionValue(option)"
                border
              >
                {{ option }}
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
                currentQuestion.type === 'short_answer' ? 5 : undefined
              "
              :placeholder="
                currentQuestion.type === 'short_answer'
                  ? '写下你的理解'
                  : '填写答案'
              "
              maxlength="2000"
              show-word-limit
              :disabled="Boolean(practiceStore.feedback)"
            />

            <div class="question-actions">
              <span>
                <el-icon><EditPen /></el-icon>
                本题用时 {{ formatDuration(currentElapsedSeconds) }}
              </span>
              <el-button
                v-if="!practiceStore.feedback"
                type="primary"
                :loading="practiceStore.submitting"
                :disabled="!canSubmit"
                @click="submitCurrentAnswer"
              >
                提交
              </el-button>
            </div>

            <transition name="feedback-slide">
              <div
                v-if="practiceStore.feedback"
                class="feedback-panel"
                :class="{
                  correct: practiceStore.feedback.is_correct,
                  wrong: !practiceStore.feedback.is_correct,
                }"
              >
                <div class="feedback-heading">
                  <el-icon>
                    <CircleCheck v-if="practiceStore.feedback.is_correct" />
                    <CircleClose v-else />
                  </el-icon>
                  <div>
                    <strong>
                      {{
                        practiceStore.feedback.is_correct
                          ? '回答正确'
                          : '再想一想'
                      }}
                    </strong>
                    <span>
                      {{
                        practiceStore.feedback.is_correct
                          ? '这道题掌握得不错。'
                          : '查看解析，找到可以改进的地方。'
                      }}
                    </span>
                  </div>
                </div>
                <div class="explanation">
                  <span>解析</span>
                  <p>{{ practiceStore.feedback.explanation }}</p>
                </div>
                <div class="feedback-footer">
                  <el-button type="primary" @click="nextQuestion">
                    {{
                      currentQuestionNumber >= practiceStore.questions.length
                        ? '完成练习'
                        : '下一题'
                    }}
                  </el-button>
                </div>
              </div>
            </transition>
          </template>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="7" :lg="6">
        <el-card shadow="never" class="stats-card">
          <template #header>
            <div class="stats-heading">
              <div>
                <h2>本次练习</h2>
                <span>当前答题统计</span>
              </div>
              <el-icon><TrendCharts /></el-icon>
            </div>
          </template>

          <div class="accuracy-ring">
            <el-progress
              type="circle"
              :percentage="accuracyPercent"
              :width="112"
              :stroke-width="9"
              color="#246BFE"
            />
          </div>

          <div class="stats-list">
            <div>
              <span>做题数</span>
              <strong>{{ practiceStore.answeredCount }}</strong>
            </div>
            <div>
              <span>正确数</span>
              <strong>{{ practiceStore.correctCount }}</strong>
            </div>
            <div>
              <span>正确率</span>
              <strong>{{ accuracyPercent }}%</strong>
            </div>
            <div>
              <span>用时</span>
              <strong>{{ formatDuration(displayTime) }}</strong>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </section>
</template>

<style scoped>
.practice-page {
  display: flex;
  flex-direction: column;
}

.practice-toolbar {
  margin-bottom: 18px;
  border-color: var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
}

.practice-toolbar :deep(.el-card__body) {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
}

.toolbar-fields {
  display: flex;
  flex: 1;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 22px;
}

.toolbar-fields label {
  display: flex;
  min-width: 220px;
  flex-direction: column;
  gap: 7px;
}

.toolbar-fields label > span {
  color: var(--app-muted);
  font-size: 11px;
  font-weight: 650;
}

.toolbar-fields :deep(.el-select) {
  width: 230px;
}

.practice-layout :deep(.el-col) {
  display: flex;
}

.practice-card,
.stats-card {
  width: 100%;
  border-color: var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
}

.practice-card {
  min-height: 620px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.practice-card.is-correct {
  border-color: #149A76;
  box-shadow: 0 0 0 2px rgba(20, 154, 118, 0.08);
}

.practice-card.is-wrong {
  border-color: #D94F59;
  box-shadow: 0 0 0 2px rgba(217, 79, 89, 0.08);
}

.practice-card :deep(.el-card__body) {
  padding: clamp(22px, 3vw, 34px);
}

.question-loading {
  min-height: 480px;
}

.finished-summary {
  display: flex;
  align-items: center;
  flex-direction: column;
  gap: 14px;
}

.finished-summary span {
  color: var(--app-muted);
  font-size: 13px;
}

.question-progress {
  margin-bottom: 22px;
}

.question-progress > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.question-progress span {
  color: var(--app-muted);
  font-size: 11px;
}

.question-progress strong {
  color: var(--app-text);
  font-size: 12px;
}

.question-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.question-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.timer {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--app-muted);
  font-size: 11px;
}

.question-text {
  margin: 24px 0;
  color: var(--app-text);
  font-size: clamp(18px, 2.2vw, 24px);
  line-height: 1.7;
  white-space: pre-wrap;
}

.practice-options {
  display: flex;
  align-items: stretch;
  flex-direction: column;
  gap: 10px;
}

.practice-options :deep(.el-radio) {
  width: 100%;
  height: auto;
  min-height: 46px;
  margin-right: 0;
  padding: 10px 14px;
}

.practice-options :deep(.el-radio__label) {
  white-space: normal;
  line-height: 1.6;
}

.question-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-top: 24px;
  padding-top: 18px;
  border-top: 1px solid var(--app-border);
}

.question-actions > span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--app-muted);
  font-size: 11px;
}

.question-actions .el-button {
  min-width: 112px;
}

.feedback-panel {
  margin-top: 22px;
  padding: 18px;
  border: 1px solid;
  border-radius: 8px;
}

.feedback-panel.correct {
  border-color: rgba(20, 154, 118, 0.42);
  background: rgba(20, 154, 118, 0.06);
}

.feedback-panel.wrong {
  border-color: rgba(217, 79, 89, 0.42);
  background: rgba(217, 79, 89, 0.05);
}

.feedback-heading {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.feedback-heading > .el-icon {
  margin-top: 2px;
  font-size: 22px;
}

.feedback-panel.correct .feedback-heading > .el-icon {
  color: #149A76;
}

.feedback-panel.wrong .feedback-heading > .el-icon {
  color: #D94F59;
}

.feedback-heading > div {
  display: flex;
  flex-direction: column;
}

.feedback-heading strong {
  color: var(--app-text);
  font-size: 15px;
}

.feedback-heading span {
  margin-top: 3px;
  color: var(--app-muted);
  font-size: 11px;
}

.explanation {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--app-border);
}

.explanation > span {
  color: #246BFE;
  font-size: 10px;
  font-weight: 750;
}

.explanation p {
  margin: 6px 0 0;
  color: var(--app-muted);
  font-size: 12px;
  line-height: 1.7;
}

.feedback-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.stats-card {
  position: sticky;
  top: 92px;
  align-self: flex-start;
  min-height: 380px;
}

.stats-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.stats-heading h2 {
  margin: 0;
  color: var(--app-text);
  font-size: 15px;
}

.stats-heading span {
  display: block;
  margin-top: 4px;
  color: var(--app-muted);
  font-size: 10px;
}

.stats-heading > .el-icon {
  color: #246BFE;
  font-size: 20px;
}

.accuracy-ring {
  display: grid;
  padding: 22px 0;
  place-items: center;
}

.stats-list {
  display: flex;
  flex-direction: column;
}

.stats-list > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 42px;
  border-top: 1px solid var(--app-border);
}

.stats-list span {
  color: var(--app-muted);
  font-size: 11px;
}

.stats-list strong {
  color: var(--app-text);
  font-size: 14px;
}

.feedback-slide-enter-active,
.feedback-slide-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.feedback-slide-enter-from,
.feedback-slide-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

@media (max-width: 992px) {
  .practice-toolbar :deep(.el-card__body) {
    align-items: stretch;
    flex-direction: column;
  }

  .practice-toolbar :deep(.el-button) {
    width: 100%;
  }

  .practice-layout :deep(.el-col) {
    margin-bottom: 16px;
  }

  .stats-card {
    position: static;
  }
}

@media (max-width: 640px) {
  .toolbar-fields {
    align-items: stretch;
    flex-direction: column;
  }

  .toolbar-fields label,
  .toolbar-fields :deep(.el-select) {
    width: 100%;
  }

  .toolbar-fields :deep(.el-radio-group) {
    display: flex;
  }

  .toolbar-fields :deep(.el-radio-button) {
    flex: 1;
  }

  .toolbar-fields :deep(.el-radio-button__inner) {
    width: 100%;
    padding: 8px 6px;
  }

  .question-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .question-actions .el-button {
    width: 100%;
  }

  .practice-card {
    min-height: 540px;
  }
}
</style>
