<script setup>
import {
  ArrowRight,
  CircleCheck,
  MagicStick,
  Moon,
  Reading,
  Sunny,
  SwitchButton,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import LearningContentForm from '../components/LearningContentForm.vue'
import { useLearningContentStore } from '../stores/learningContent'
import { useLearningStore } from '../stores/learning'
import { usePracticeStore } from '../stores/practice'
import { useUserStore } from '../stores/user'

const router = useRouter()
const userStore = useUserStore()
const learningStore = useLearningStore()
const learningContentStore = useLearningContentStore()
const practiceStore = usePracticeStore()

const checking = ref(true)
const checkFailed = ref(false)
const isDark = computed(() => userStore.theme === 'dark')

onMounted(checkContent)

async function checkContent() {
  checking.value = true
  checkFailed.value = false
  try {
    await learningContentStore.fetchSubjects({ force: true })
    if (learningContentStore.subjects.length) {
      await router.replace({ name: 'Dashboard' })
    }
  } catch {
    checkFailed.value = true
  } finally {
    checking.value = false
  }
}

async function createLearningContent(payload) {
  try {
    const graph = await learningContentStore.generateSubject(payload)
    ElMessage.success(`已生成「${graph.title}」，请先完成初始诊断`)
    await router.replace({
      name: 'InitialDiagnosis',
      params: { subject: graph.subject },
    })
  } catch {
    // 请求层已展示具体错误。
  }
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
  <main class="onboarding-page">
    <header class="onboarding-topbar">
      <div class="onboarding-brand">
        <span class="brand-mark">SLP</span>
        <div>
          <strong>智学路径</strong>
          <small>创建学习空间</small>
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

    <section class="onboarding-content">
      <div class="onboarding-heading">
        <p class="page-kicker">START YOUR LEARNING SPACE</p>
        <h1>先创建一份学习内容</h1>
        <p>
          学习图谱、诊断、练习和学习路径都会围绕你创建的内容生成。
        </p>
      </div>

      <div class="stage-track" aria-label="首次使用流程">
        <span class="is-active">
          <el-icon><Reading /></el-icon>
          创建学习内容
        </span>
        <i></i>
        <span>完成初始诊断</span>
        <i></i>
        <span>开始个性化学习</span>
      </div>

      <section class="onboarding-panel">
        <div v-if="checking" class="checking-state">
          <el-skeleton :rows="6" animated />
        </div>

        <div v-else-if="checkFailed" class="error-state">
          <el-empty
            description="无法读取学习内容状态"
            :image-size="90"
          >
            <el-button @click="checkContent">重新加载</el-button>
          </el-empty>
        </div>

        <template v-else>
          <div class="panel-heading">
            <span class="panel-symbol">
              <el-icon><MagicStick /></el-icon>
            </span>
            <div>
              <h2>告诉我你想学什么</h2>
              <p>生成完成后，还需要先完成初始诊断才能进入学习空间。</p>
            </div>
          </div>

          <LearningContentForm
            :loading="learningContentStore.generating"
            submit-label="生成并开始诊断"
            @submit="createLearningContent"
          />
        </template>
      </section>

      <div class="next-step-note">
        <el-icon><CircleCheck /></el-icon>
        <span>系统会为每份学习内容单独保存图谱、练习和答疑记录。</span>
        <el-icon><ArrowRight /></el-icon>
      </div>
    </section>
  </main>
</template>

<style scoped>
.onboarding-page {
  min-height: 100vh;
  color: var(--app-text);
  background:
    linear-gradient(180deg, #f7fafc 0%, var(--app-bg) 48%, #eef5f7 100%);
}

:global(html.dark) .onboarding-page {
  background:
    linear-gradient(180deg, #111e27 0%, var(--app-bg) 48%, #0d2025 100%);
}

.onboarding-topbar {
  display: flex;
  height: 72px;
  align-items: center;
  justify-content: space-between;
  padding: 0 clamp(18px, 4vw, 48px);
  border-bottom: 1px solid var(--app-border);
  background: color-mix(in srgb, var(--app-surface) 92%, transparent);
  backdrop-filter: blur(16px);
}

.onboarding-brand,
.topbar-actions {
  display: flex;
  align-items: center;
}

.onboarding-brand {
  gap: 12px;
}

.onboarding-brand > div {
  display: flex;
  flex-direction: column;
}

.onboarding-brand strong {
  font-size: 16px;
  line-height: 1.3;
}

.onboarding-brand small {
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

.onboarding-content {
  width: min(960px, calc(100% - 32px));
  margin: 0 auto;
  padding: clamp(34px, 6vw, 64px) 0 56px;
}

.onboarding-heading {
  max-width: 720px;
}

.onboarding-heading h1 {
  margin: 0;
  color: var(--app-text);
  font-size: clamp(30px, 4.5vw, 44px);
  line-height: 1.2;
}

.onboarding-heading > p:last-child {
  margin: 12px 0 0;
  color: var(--app-text-soft);
  font-size: 14px;
  line-height: 1.7;
}

.stage-track {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 26px 0 18px;
  color: var(--app-muted);
  font-size: 12px;
  font-weight: 650;
}

.stage-track span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.stage-track i {
  height: 1px;
  flex: 1;
  background: var(--app-border-strong);
}

.stage-track .is-active {
  color: var(--app-primary);
}

.onboarding-panel {
  padding: clamp(24px, 4vw, 38px);
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
  box-shadow: var(--app-shadow-raised);
}

.checking-state,
.error-state {
  min-height: 360px;
}

.error-state {
  display: grid;
  place-items: center;
}

.panel-heading {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--app-border);
}

.panel-symbol {
  display: grid;
  width: 44px;
  height: 44px;
  flex: 0 0 44px;
  place-items: center;
  border-radius: 8px;
  color: var(--app-primary);
  background: var(--app-primary-soft);
  font-size: 21px;
}

.panel-heading h2 {
  margin: 0;
  color: var(--app-text);
  font-size: 20px;
  line-height: 1.4;
}

.panel-heading p {
  margin: 5px 0 0;
  color: var(--app-muted);
  font-size: 12px;
  line-height: 1.6;
}

.next-step-note {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  color: var(--app-muted);
  background: color-mix(in srgb, var(--app-surface) 76%, transparent);
  font-size: 12px;
}

.next-step-note .el-icon:first-child {
  color: var(--app-success);
}

.next-step-note .el-icon:last-child {
  margin-left: auto;
}

@media (max-width: 640px) {
  .onboarding-topbar {
    height: 64px;
    padding: 0 14px;
  }

  .onboarding-brand small,
  .logout-button {
    display: none;
  }

  .onboarding-content {
    width: calc(100% - 28px);
    padding: 30px 0 40px;
  }

  .stage-track {
    gap: 7px;
    overflow-x: auto;
    font-size: 10px;
    scrollbar-width: none;
  }

  .stage-track::-webkit-scrollbar {
    display: none;
  }

  .onboarding-panel {
    padding: 22px 16px;
  }

  .next-step-note {
    align-items: flex-start;
    line-height: 1.55;
  }

  .next-step-note .el-icon:last-child {
    display: none;
  }
}
</style>
