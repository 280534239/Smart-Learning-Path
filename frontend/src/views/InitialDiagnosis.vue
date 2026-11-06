<script setup>
import {
  Clock,
  DataAnalysis,
  EditPen,
  Loading,
  Moon,
  Promotion,
  Refresh,
  Sunny,
  SwitchButton,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  completeInitialDiagnosis,
  getInitialDiagnosisStatus,
  startInitialDiagnosis,
} from '../api/diagnosis'
import { getKnowledgeGraph } from '../api/knowledge'
import { useLearningContentStore } from '../stores/learningContent'
import { useLearningStore } from '../stores/learning'
import { usePracticeStore } from '../stores/practice'
import { useUserStore } from '../stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const learningStore = useLearningStore()
const learningContentStore = useLearningContentStore()
const practiceStore = usePracticeStore()

const contextLoading = ref(true)
const contextError = ref(false)
const starting = ref(false)
const startError = ref(false)
const stage = ref(0)
const questions = ref([])
const graphNodes = ref([])
const currentIndex = ref(0)
const answer = ref('')
const answerStartedAt = ref(Date.now())
const sessionId = ref(null)
const answers = ref([])
const completing = ref(false)
const completionError = ref(false)
const title = ref('')
const learningGoal = ref('')
const level = ref('基础')

const subject = computed(() => {
  const routeSubject = route.params.subject
  return typeof routeSubject === 'string'
    ? routeSubject
    : learningContentStore.activeSubject
})
const isDark = computed(() => userStore.theme === 'dark')
const currentQuestion = computed(
  () => questions.value[currentIndex.value] || null,
)
const learningGoalPriorities = computed(() => {
  const goal = String(learningGoal.value || '')
  return [
    ...new Set(
      goal
        .split(/[、,，;；>→]+/)
        .map((item) => item.replace(/^\d+[.、\s]*/, '').trim())
        .filter(Boolean),
    ),
  ]
})
const currentCategory = computed(
  () =>
    graphNodes.value.find(
      (node) => node.id === currentQuestion.value?.knowledge_point_id,
    )?.category || title.value,
)
const progressPercentage = computed(() => {
  if (!questions.value.length) return 0
  return Math.round((currentIndex.value / questions.value.length) * 100)
})
const canSubmit = computed(
  () => Boolean(answer.value.trim()) && !starting.value,
)

watch(
  () => currentQuestion.value?.id,
  () => {
    answer.value = ''
    answerStartedAt.value = Date.now()
  },
)

onMounted(loadContext)

async function loadContext() {
  contextLoading.value = true
  contextError.value = false
  learningContentStore.setActiveSubject(subject.value)
  try {
    const status = await getInitialDiagnosisStatus(subject.value)
    title.value = status.title
    learningGoal.value = status.learning_goal || ''
    level.value = status.level || '基础'
    if (!status.required) {
      await router.replace('/knowledge')
      return
    }
    if (status.completed) {
      await router.replace('/learning-path')
    }
  } catch {
    contextError.value = true
  } finally {
    contextLoading.value = false
  }
}

async function beginDiagnosis() {
  starting.value = true
  startError.value = false
  answers.value = []
  try {
    const [graph, diagnosis] = await Promise.all([
      getKnowledgeGraph(subject.value),
      startInitialDiagnosis(subject.value),
    ])
    graphNodes.value = graph.nodes
    sessionId.value = diagnosis.session_id
    title.value = diagnosis.title
    learningGoal.value = diagnosis.learning_goal
    level.value = diagnosis.level
    questions.value = diagnosis.questions
    currentIndex.value = 0
    answerStartedAt.value = Date.now()
    stage.value = 1
  } catch {
    startError.value = true
    ElMessage.error('初始诊断题目生成失败，请稍后重试')
  } finally {
    starting.value = false
  }
}

async function submitCurrentAnswer() {
  if (!canSubmit.value || !currentQuestion.value) return
  const timeSpent = Math.max(
    1,
    Math.round((Date.now() - answerStartedAt.value) / 1000),
  )
  answers.value.push({
    question_id: currentQuestion.value.id,
    answer: answer.value.trim(),
    time_spent: timeSpent,
  })

  if (currentIndex.value < questions.value.length - 1) {
    currentIndex.value += 1
    return
  }
  await completeDiagnosis()
}

async function completeDiagnosis() {
  if (!sessionId.value) return
  stage.value = 2
  completing.value = true
  completionError.value = false
  try {
    await completeInitialDiagnosis(sessionId.value, answers.value)
    ElMessage.success('初始诊断已完成，正在打开个性化学习路径')
    await router.replace('/learning-path')
  } catch {
    completionError.value = true
  } finally {
    completing.value = false
  }
}

function formatOption(option) {
  return option.trim()
}

function optionValue(option) {
  return option.trim().slice(0, 1)
}

function handleLogout() {
  learningStore.reset()
  learningContentStore.reset()
  practiceStore.reset()
  userStore.logout()
  router.replace({ name: 'Login' })
}
</script>

<template>
  <main class="initial-page">
    <header class="initial-topbar">
      <div class="initial-brand">
        <span class="brand-mark">SLP</span>
        <div>
          <strong>智学路径</strong>
          <small>初始诊断</small>
        </div>
      </div>
      <div class="topbar-actions">
        <el-tooltip
          :content="isDark ? '切换亮色主题' : '切换暗色主题'"
          placement="bottom"
        >
          <button
            class="topbar-icon-button"
            type="button"
            :aria-label="isDark ? '切换亮色主题' : '切换暗色主题'"
            @click="userStore.toggleTheme"
          >
            <el-icon>
              <Sunny v-if="isDark" />
              <Moon v-else />
            </el-icon>
          </button>
        </el-tooltip>
        <el-button text class="logout-button" @click="handleLogout">
          <el-icon><SwitchButton /></el-icon>
          退出
        </el-button>
      </div>
    </header>

    <section class="initial-content">
      <div class="content-heading">
        <div>
          <p class="page-kicker">INITIAL DIAGNOSIS</p>
          <h1>初始诊断</h1>
          <span>
            这是进入「{{ title || '新学习内容' }}」前的必要步骤。
          </span>
        </div>
      </div>

      <div class="stage-track" aria-label="初始诊断流程">
        <span class="is-complete">内容已生成</span>
        <i></i>
        <span :class="{ 'is-active': stage < 2, 'is-complete': stage === 2 }">
          初始诊断
        </span>
        <i></i>
        <span>个性化学习路径</span>
      </div>

      <div v-if="contextLoading" class="initial-panel loading-panel">
        <el-skeleton :rows="7" animated />
      </div>

      <div v-else-if="contextError" class="initial-panel state-panel">
        <el-empty description="初始诊断状态加载失败" :image-size="90">
          <el-button :icon="Refresh" @click="loadContext">
            重新加载
          </el-button>
        </el-empty>
      </div>

      <section v-else-if="stage === 0" class="initial-panel welcome-panel">
        <div class="diagnosis-symbol">
          <el-icon><DataAnalysis /></el-icon>
        </div>
        <h2>{{ title }} 初始诊断</h2>
        <p class="welcome-copy">
          系统会围绕你的学习目标，从不同知识模块随机抽取题目。
          完成诊断后才能进入该学习内容。
        </p>

        <div class="goal-block">
          <div class="goal-priority-copy">
            <span>本次学习目标优先级</span>
            <div class="goal-priority-list">
              <span
                v-for="(goal, index) in learningGoalPriorities"
                :key="goal"
                class="goal-priority-chip"
              >
                <b>{{ index + 1 }}</b>
                {{ goal }}
              </span>
            </div>
          </div>
          <small>起始水平：{{ level }}</small>
        </div>

        <div class="diagnosis-meta">
          <span>
            <el-icon><Clock /></el-icon>
            约 5 至 10 分钟
          </span>
          <span>
            <el-icon><EditPen /></el-icon>
            8 至 10 道随机题
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
          :loading="starting"
          @click="beginDiagnosis"
        >
          开始初始诊断
          <el-icon class="action-icon"><Promotion /></el-icon>
        </el-button>

        <el-alert
          v-if="startError"
          type="error"
          :closable="false"
          show-icon
          title="诊断题目加载失败，请稍后重试"
        />
      </section>

      <section v-else-if="stage === 1 && currentQuestion" class="question-shell">
        <div class="answer-progress">
          <div>
            <span>诊断进度</span>
            <strong>
              第 {{ currentIndex + 1 }} / {{ questions.length }} 题
            </strong>
          </div>
          <el-progress
            :percentage="progressPercentage"
            :stroke-width="8"
            :show-text="false"
            color="var(--app-primary)"
          />
        </div>

        <article class="question-panel">
          <div class="question-meta">
            <el-tag effect="plain">{{ currentCategory }}</el-tag>
            <span>难度 {{ currentQuestion.difficulty }}</span>
          </div>

          <h2>{{ currentQuestion.question }}</h2>

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
              currentQuestion.type === 'short_answer' ? 'textarea' : 'text'
            "
            :rows="currentQuestion.type === 'short_answer' ? 5 : undefined"
            :placeholder="
              currentQuestion.type === 'short_answer'
                ? '写下你的理解'
                : '填写答案'
            "
            maxlength="2000"
            show-word-limit
          />

          <footer class="question-actions">
            <span>本题作答时间将用于分析学习效率</span>
            <el-button
              type="primary"
              :disabled="!canSubmit"
              @click="submitCurrentAnswer"
            >
              {{
                currentIndex === questions.length - 1
                  ? '完成初始诊断'
                  : '下一题'
              }}
            </el-button>
          </footer>
        </article>
      </section>

      <section v-else class="initial-panel completion-panel">
        <div class="completion-symbol">
          <el-icon v-if="completing" class="is-loading"><Loading /></el-icon>
          <el-icon v-else><Refresh /></el-icon>
        </div>
        <h2>
          {{ completing ? '正在生成个性化学习路径' : '诊断结果提交失败' }}
        </h2>
        <p>
          {{
            completing
              ? '系统正在整理诊断结果并安排后续学习顺序。'
              : '本次诊断尚未完成，请重新提交。'
          }}
        </p>
        <el-button
          v-if="completionError"
          type="primary"
          @click="completeDiagnosis"
        >
          重新提交
        </el-button>
      </section>
    </section>
  </main>
</template>

<style scoped>
.initial-page {
  min-height: 100vh;
  color: var(--app-text);
  background:
    linear-gradient(180deg, #f7fafc 0%, var(--app-bg) 48%, #eef5f7 100%);
}

:global(html.dark) .initial-page {
  background:
    linear-gradient(180deg, #111e27 0%, var(--app-bg) 48%, #0d2025 100%);
}

.initial-topbar {
  display: flex;
  height: 72px;
  align-items: center;
  justify-content: space-between;
  padding: 0 clamp(18px, 4vw, 48px);
  border-bottom: 1px solid var(--app-border);
  background: color-mix(in srgb, var(--app-surface) 92%, transparent);
  backdrop-filter: blur(16px);
}

.initial-brand,
.topbar-actions {
  display: flex;
  align-items: center;
}

.initial-brand {
  gap: 12px;
}

.initial-brand > div {
  display: flex;
  flex-direction: column;
}

.initial-brand strong {
  font-size: 16px;
  line-height: 1.3;
}

.initial-brand small {
  color: var(--app-muted);
  font-size: 10px;
}

.brand-mark {
  display: grid;
  width: 40px;
  height: 40px;
  place-items: center;
  border-radius: 8px;
  color: #fff;
  background: linear-gradient(145deg, #5687ff, #1557df);
  box-shadow: 0 7px 18px rgba(36, 107, 254, 0.22);
  font-size: 11px;
  font-weight: 800;
}

.topbar-actions {
  gap: 7px;
}

.topbar-icon-button {
  display: grid;
  width: 36px;
  height: 36px;
  place-items: center;
  border: 0;
  border-radius: 8px;
  color: var(--app-muted);
  background: transparent;
  cursor: pointer;
}

.topbar-icon-button:hover {
  color: var(--app-text);
  background: var(--app-surface-muted);
}

.logout-button {
  gap: 5px;
  color: var(--app-muted);
}

.initial-content {
  width: min(980px, calc(100% - 32px));
  margin: 0 auto;
  padding: 34px 0 56px;
}

.content-heading h1 {
  margin: 0;
  color: var(--app-text);
  font-size: clamp(28px, 4vw, 38px);
  line-height: 1.2;
}

.content-heading > div > span {
  display: block;
  margin-top: 9px;
  color: var(--app-text-soft);
  font-size: 14px;
  line-height: 1.6;
}

.stage-track {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 24px 0 18px;
  color: var(--app-muted);
  font-size: 12px;
  font-weight: 650;
}

.stage-track i {
  height: 1px;
  flex: 1;
  background: var(--app-border-strong);
}

.stage-track span {
  white-space: nowrap;
}

.stage-track .is-active {
  color: var(--app-primary);
}

.stage-track .is-complete {
  color: var(--app-success);
}

.initial-panel,
.question-panel {
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
  box-shadow: var(--app-shadow-raised);
}

.welcome-panel {
  padding: clamp(32px, 6vw, 62px);
  text-align: center;
}

.diagnosis-symbol,
.completion-symbol {
  display: grid;
  width: 58px;
  height: 58px;
  margin: 0 auto 18px;
  place-items: center;
  border-radius: 8px;
  color: var(--app-primary);
  background: var(--app-primary-soft);
  font-size: 28px;
}

.welcome-panel h2,
.completion-panel h2 {
  margin: 0;
  color: var(--app-text);
  font-size: clamp(24px, 3vw, 32px);
  line-height: 1.3;
}

.welcome-copy {
  max-width: 610px;
  margin: 14px auto 0;
  color: var(--app-muted);
  font-size: 14px;
  line-height: 1.8;
}

.goal-block {
  display: flex;
  max-width: 640px;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin: 24px auto 0;
  padding: 15px 18px;
  border: 1px solid color-mix(in srgb, var(--app-primary) 22%, var(--app-border));
  border-radius: 8px;
  background: var(--app-primary-soft);
  text-align: left;
}

.goal-block > div {
  display: grid;
  gap: 5px;
}

.goal-block span,
.goal-block small {
  color: var(--app-muted);
  font-size: 11px;
}

.goal-block strong {
  color: var(--app-text);
  font-size: 14px;
  line-height: 1.6;
}

.goal-priority-copy {
  flex: 1;
}

.goal-priority-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.goal-block .goal-priority-chip {
  display: inline-flex;
  min-height: 27px;
  align-items: center;
  gap: 5px;
  padding: 3px 8px 3px 4px;
  border: 1px solid color-mix(in srgb, var(--app-primary) 22%, var(--app-border));
  border-radius: 6px;
  color: var(--app-text-soft);
  background: var(--app-surface);
  font-size: 11px;
  font-weight: 650;
}

.goal-priority-chip b {
  display: grid;
  width: 18px;
  height: 18px;
  place-items: center;
  border-radius: 4px;
  color: #fff;
  background: var(--app-primary);
  font-size: 9px;
}

.diagnosis-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  margin: 24px 0;
}

.diagnosis-meta span {
  display: inline-flex;
  min-height: 34px;
  align-items: center;
  gap: 6px;
  padding: 0 12px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  color: var(--app-muted);
  background: var(--app-surface-muted);
  font-size: 11px;
}

.primary-action {
  min-width: 200px;
  height: 46px;
}

.action-icon {
  margin-left: 6px;
}

.welcome-panel .el-alert {
  max-width: 540px;
  margin: 18px auto 0;
}

.loading-panel {
  min-height: 420px;
  padding: 30px;
}

.state-panel,
.completion-panel {
  display: grid;
  min-height: 420px;
  place-items: center;
  align-content: center;
  padding: 36px;
  text-align: center;
}

.completion-panel p {
  max-width: 520px;
  margin: 12px auto 22px;
  color: var(--app-muted);
  line-height: 1.7;
}

.question-shell {
  display: grid;
  gap: 16px;
}

.answer-progress {
  padding: 0 4px;
}

.answer-progress > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 10px;
}

.answer-progress span {
  color: var(--app-muted);
  font-size: 12px;
}

.answer-progress strong {
  color: var(--app-text);
  font-size: 13px;
}

.question-panel {
  padding: clamp(24px, 4vw, 40px);
}

.question-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.question-meta > span {
  color: var(--app-muted);
  font-size: 11px;
}

.question-panel h2 {
  margin: 24px 0;
  color: var(--app-text);
  font-size: clamp(19px, 2.6vw, 25px);
  line-height: 1.55;
}

.answer-options {
  display: grid;
  gap: 10px;
}

.answer-options :deep(.el-radio) {
  width: 100%;
  height: auto;
  min-height: 46px;
  margin-right: 0;
  padding: 11px 15px;
  white-space: normal;
}

.answer-options :deep(.el-radio__label) {
  line-height: 1.6;
}

.question-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-top: 26px;
  padding-top: 18px;
  border-top: 1px solid var(--app-border);
}

.question-actions > span {
  color: var(--app-muted);
  font-size: 11px;
}

@media (max-width: 640px) {
  .initial-topbar {
    height: 64px;
    padding: 0 14px;
  }

  .initial-brand small,
  .logout-button {
    display: none;
  }

  .initial-content {
    width: calc(100% - 28px);
    padding: 24px 0 36px;
  }

  .stage-track {
    gap: 7px;
    font-size: 10px;
  }

  .welcome-panel {
    padding: 30px 18px;
  }

  .goal-block {
    align-items: flex-start;
    flex-direction: column;
  }

  .diagnosis-meta {
    display: grid;
  }

  .diagnosis-meta span {
    justify-content: center;
  }

  .question-panel {
    padding: 22px 18px;
  }

  .question-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .question-actions .el-button {
    width: 100%;
  }
}
</style>
