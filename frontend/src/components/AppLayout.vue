<script setup>
import {
  ArrowDown,
  ChatDotRound,
  Collection,
  Cpu,
  DataAnalysis,
  Delete,
  EditPen,
  Expand,
  Fold,
  Loading,
  MagicStick,
  Menu,
  Moon,
  Position,
  Reading,
  Share,
  Sunny,
  SwitchButton,
  User,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { getInitialDiagnosisStatus } from '../api/diagnosis'
import LearningContentForm from './LearningContentForm.vue'
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

const learningMenuItems = [
  { path: '/dashboard', label: '学习看板', icon: DataAnalysis },
  { path: '/diagnosis', label: '智能诊断', icon: Cpu },
  { path: '/knowledge', label: '知识图谱', icon: Share },
  { path: '/learning-path', label: '学习路径', icon: Position },
  { path: '/practice', label: '在线练习', icon: EditPen },
]

const utilityMenuItems = [
  { path: '/chat', label: 'AI答疑', icon: ChatDotRound, badge: 'AI' },
  { path: '/error-book', label: '错题本', icon: Collection },
  { path: '/user-center', label: '用户中心', icon: User },
]
const navigationItems = [...learningMenuItems, ...utilityMenuItems]

const collapsed = ref(
  localStorage.getItem('slp_sidebar_collapsed') === 'true',
)
const mobileViewport = ref(false)
const mobileOpen = ref(false)
const generatorVisible = ref(false)
let mediaQuery

const isDark = computed(() => userStore.theme === 'dark')
const currentPageItem = computed(
  () =>
    navigationItems.find((item) => item.path === route.path) ||
    navigationItems[0],
)
const currentPageIcon = computed(
  () => currentPageItem.value?.icon || DataAnalysis,
)
const sidebarWidth = computed(() => {
  if (mobileViewport.value) return '268px'
  return collapsed.value ? '80px' : '268px'
})
const menuCollapsed = computed(
  () => collapsed.value && !mobileViewport.value,
)
const mainStyle = computed(() => ({
  marginLeft: mobileViewport.value ? '0' : sidebarWidth.value,
}))

watch(
  [mobileOpen, mobileViewport],
  ([isOpen, isMobile]) => {
    document.body.classList.toggle(
      'sidebar-mobile-open',
      isOpen && isMobile,
    )
  },
  { immediate: true },
)

watch(
  () => route.fullPath,
  () => {
    if (
      learningContentStore.initialized &&
      !route.meta.allowPendingDiagnosis
    ) {
      ensureInitialDiagnosis(learningContentStore.activeSubject)
    }
  },
)

function toggleSidebar() {
  if (mobileViewport.value) {
    mobileOpen.value = !mobileOpen.value
    return
  }
  collapsed.value = !collapsed.value
  localStorage.setItem(
    'slp_sidebar_collapsed',
    String(collapsed.value),
  )
}

function handleViewportChange(event) {
  mobileViewport.value = event.matches
  if (!event.matches) mobileOpen.value = false
}

function closeMobileMenu() {
  if (mobileViewport.value) mobileOpen.value = false
}

function handleLogout() {
  learningStore.reset()
  learningContentStore.reset()
  practiceStore.reset()
  userStore.logout()
  router.replace({ name: 'Login' })
}

function handleUserCommand(command) {
  if (command === 'logout') {
    handleLogout()
    return
  }
  router.push({
    name: 'UserCenter',
    query: { tab: command },
  })
}

async function handleSubjectChange(subject) {
  learningContentStore.setActiveSubject(subject)
  if (!route.meta.allowPendingDiagnosis) {
    await ensureInitialDiagnosis(subject)
  }
}

function openGenerator() {
  generatorVisible.value = true
}

async function createLearningContent(payload) {
  try {
    const graph = await learningContentStore.generateSubject(payload)
    generatorVisible.value = false
    ElMessage.success(`已生成「${graph.title}」，请先完成初始诊断`)
    await router.push({
      name: 'InitialDiagnosis',
      params: { subject: graph.subject },
    })
  } catch {
    // 请求层已展示具体错误。
  }
}

async function ensureInitialDiagnosis(subject) {
  const content = learningContentStore.subjects.find(
    (item) => item.subject === subject,
  )
  if (!content) {
    await router.replace({ name: 'Onboarding' })
    return false
  }

  try {
    const status = await getInitialDiagnosisStatus(subject)
    if (status.completed) return true
    ElMessage.warning('完成初始诊断后才能进入该学习内容')
    await router.replace({
      name: 'InitialDiagnosis',
      params: { subject },
    })
    return false
  } catch {
    ElMessage.error('无法确认初始诊断状态，请稍后重试')
    return false
  }
}

async function deleteLearningContent() {
  const content = learningContentStore.activeContent
  if (!content) {
    ElMessage.warning('请先创建学习内容')
    return
  }

  try {
    await ElMessageBox.confirm(
      `删除「${content.title}」后，将永久删除该学习内容的知识图谱、生成题库、练习与答题记录、错题、学习路径、诊断记录以及 AI 对话数据。此操作无法恢复。`,
      '确认删除学习内容',
      {
        type: 'warning',
        confirmButtonText: '永久删除',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--danger',
        closeOnClickModal: false,
      },
    )
  } catch {
    return
  }

  try {
    await learningContentStore.deleteSubject(content.subject)
    ElMessage.success(`已删除「${content.title}」及其全部关联数据`)
    if (!learningContentStore.subjects.length) {
      await router.replace({ name: 'Onboarding' })
    }
  } catch {
    // 请求层已展示具体错误。
  }
}

onMounted(() => {
  mediaQuery = window.matchMedia('(max-width: 900px)')
  mobileViewport.value = mediaQuery.matches
  mediaQuery.addEventListener('change', handleViewportChange)
  userStore.fetchProfile().catch(() => {})
  learningContentStore
    .fetchSubjects()
    .then(() => {
      if (!route.meta.allowPendingDiagnosis) {
        return ensureInitialDiagnosis(
          learningContentStore.activeSubject,
        )
      }
      return true
    })
    .catch(() => {})
})

onBeforeUnmount(() => {
  document.body.classList.remove('sidebar-mobile-open')
  mediaQuery?.removeEventListener('change', handleViewportChange)
})
</script>

<template>
  <div class="app-shell">
    <div
      v-if="mobileViewport && mobileOpen"
      class="sidebar-mask"
      @click="mobileOpen = false"
    ></div>

    <aside
      class="app-sidebar"
      :class="{
        'is-collapsed': menuCollapsed,
        'is-mobile-open': mobileOpen,
      }"
      :style="{ width: sidebarWidth }"
    >
      <button class="brand-button" type="button" @click="router.push('/dashboard')">
        <span class="brand-mark">SLP</span>
        <span v-if="!menuCollapsed" class="brand-copy">
          <strong>智学路径</strong>
          <small>SMART LEARNING PATH</small>
        </span>
      </button>

      <nav class="sidebar-nav" aria-label="主导航">
        <section class="sidebar-group">
          <div v-if="!menuCollapsed" class="sidebar-section-heading">
            <span>学习中心</span>
            <small>LEARNING</small>
          </div>
          <el-menu
            :default-active="route.path"
            :collapse="menuCollapsed"
            :collapse-transition="false"
            router
            class="sidebar-menu"
            @select="closeMobileMenu"
          >
            <el-menu-item
              v-for="item in learningMenuItems"
              :key="item.path"
              :index="item.path"
            >
              <el-icon><component :is="item.icon" /></el-icon>
              <template #title>
                <span class="menu-title">{{ item.label }}</span>
              </template>
            </el-menu-item>
          </el-menu>
        </section>

        <section class="sidebar-group">
          <div v-if="!menuCollapsed" class="sidebar-section-heading">
            <span>辅助工具</span>
            <small>TOOLS</small>
          </div>
          <el-menu
            :default-active="route.path"
            :collapse="menuCollapsed"
            :collapse-transition="false"
            router
            class="sidebar-menu"
            @select="closeMobileMenu"
          >
            <el-menu-item
              v-for="item in utilityMenuItems"
              :key="item.path"
              :index="item.path"
            >
              <el-icon><component :is="item.icon" /></el-icon>
              <template #title>
                <span class="menu-title">
                  {{ item.label }}
                  <small v-if="item.badge" class="menu-badge">
                    {{ item.badge }}
                  </small>
                </span>
              </template>
            </el-menu-item>
          </el-menu>
        </section>
      </nav>

      <button
        v-if="!mobileViewport"
        class="collapse-button"
        type="button"
        :aria-label="collapsed ? '展开侧边栏' : '收起侧边栏'"
        @click="toggleSidebar"
      >
        <el-icon>
          <Expand v-if="collapsed" />
          <Fold v-else />
        </el-icon>
      </button>
    </aside>

    <div class="app-main" :style="mainStyle">
      <header class="app-header">
        <div class="header-leading">
          <button
            class="icon-button mobile-menu-button"
            type="button"
            aria-label="打开导航"
            @click="toggleSidebar"
          >
            <el-icon><Menu /></el-icon>
          </button>
          <div class="header-title">
            <span class="header-context">智学路径 · 学习空间</span>
            <div class="header-page">
              <span class="header-page-mark">
                <el-icon><component :is="currentPageIcon" /></el-icon>
              </span>
              <strong>{{ route.meta.title }}</strong>
            </div>
          </div>
        </div>

        <div class="content-switcher" aria-label="学习内容切换">
          <span class="content-switcher-label">
            <el-icon><Reading /></el-icon>
            学习内容
          </span>
          <el-select
            :model-value="learningContentStore.activeSubject"
            :loading="learningContentStore.loading"
            class="content-select"
            filterable
            @change="handleSubjectChange"
          >
            <el-option
              v-for="item in learningContentStore.subjects"
              :key="item.subject"
              :label="item.title"
              :value="item.subject"
            >
              <div class="content-option">
                <span>{{ item.title }}</span>
                <small>AI 生成</small>
              </div>
            </el-option>
          </el-select>
          <el-tooltip content="生成新的学习内容" placement="bottom">
            <button
              class="icon-button generate-button"
              type="button"
              aria-label="生成新的学习内容"
              @click="openGenerator"
            >
              <el-icon><MagicStick /></el-icon>
            </button>
          </el-tooltip>
          <el-tooltip content="删除当前学习内容" placement="bottom">
            <span class="icon-button-wrap">
              <button
                class="icon-button delete-button"
                type="button"
                :disabled="
                  !learningContentStore.activeContent ||
                  learningContentStore.deleting
                "
                aria-label="删除当前学习内容"
                @click="deleteLearningContent"
              >
                <el-icon
                  v-if="learningContentStore.deleting"
                  class="is-loading"
                >
                  <Loading />
                </el-icon>
                <el-icon v-else><Delete /></el-icon>
              </button>
            </span>
          </el-tooltip>
        </div>

        <div class="header-actions">
          <el-tooltip
            :content="isDark ? '切换亮色主题' : '切换暗色主题'"
            placement="bottom"
          >
            <button
              class="icon-button header-action-button"
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

          <span class="header-divider" aria-hidden="true"></span>

          <el-dropdown
            trigger="click"
            placement="bottom-end"
            @command="handleUserCommand"
          >
            <button class="user-summary" type="button">
              <el-avatar
                :size="32"
                :src="userStore.profile?.avatar_url"
                class="user-avatar"
              >
                {{ userStore.avatarText }}
              </el-avatar>
              <span class="user-name">{{ userStore.displayName }}</span>
              <i class="user-presence" aria-label="在线"></i>
              <el-icon class="user-menu-arrow"><ArrowDown /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">
                  个人资料
                </el-dropdown-item>
                <el-dropdown-item command="learning">
                  学习档案
                </el-dropdown-item>
                <el-dropdown-item command="settings">
                  偏好设置
                </el-dropdown-item>
                <el-dropdown-item command="security">
                  账号安全
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <main class="page-content">
        <router-view v-slot="{ Component }">
          <transition name="page-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>

    <el-dialog
      v-model="generatorVisible"
      title="生成新的学习内容"
      width="min(560px, calc(100vw - 32px))"
      destroy-on-close
      :close-on-click-modal="!learningContentStore.generating"
      :close-on-press-escape="!learningContentStore.generating"
      :show-close="!learningContentStore.generating"
    >
      <LearningContentForm
        :loading="learningContentStore.generating"
        cancel-label="取消"
        @submit="createLearningContent"
        @cancel="generatorVisible = false"
      />
    </el-dialog>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  background: var(--app-bg);
}

.app-sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 30;
  display: flex;
  min-height: 100vh;
  flex-direction: column;
  padding: 18px 14px 14px;
  overflow: hidden;
  color: #f7fbff;
  background:
    linear-gradient(180deg, #0a202c 0%, #102f3c 48%, #09232d 100%);
  box-shadow: 12px 0 36px rgba(10, 32, 43, 0.14);
  transition:
    width 0.01s cubic-bezier(0.2, 0.75, 0.25, 1),
    transform 0.01s cubic-bezier(0.2, 0.75, 0.25, 1);
}

.app-sidebar::before {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(
    circle at 1px 1px,
    rgba(191, 220, 235, 0.09) 1px,
    transparent 0
  );
  background-size: 18px 18px;
  mask-image: linear-gradient(
    to bottom,
    rgba(0, 0, 0, 0.9),
    transparent 72%
  );
  content: "";
  pointer-events: none;
}

.app-sidebar::after {
  position: absolute;
  inset: 0 0 0 auto;
  width: 1px;
  background: linear-gradient(
    to bottom,
    rgba(122, 165, 255, 0.38),
    rgba(103, 198, 176, 0.1) 48%,
    rgba(244, 184, 96, 0.26)
  );
  content: "";
  pointer-events: none;
}

.app-sidebar > * {
  position: relative;
  z-index: 1;
}

.brand-button {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 60px;
  padding: 2px 5px 16px;
  border: 0;
  color: inherit;
  text-align: left;
  background: transparent;
  cursor: pointer;
}

.brand-button::after {
  position: absolute;
  right: 4px;
  bottom: 0;
  left: 4px;
  height: 1px;
  background: linear-gradient(
    90deg,
    rgba(126, 168, 255, 0.38),
    rgba(255, 255, 255, 0.08) 52%,
    transparent
  );
  content: "";
}

.brand-mark {
  position: relative;
  display: grid;
  width: 44px;
  height: 44px;
  flex: 0 0 44px;
  place-items: center;
  border-radius: 8px;
  color: #fff;
  background: linear-gradient(145deg, #5687ff 0%, #1e5be9 74%, #1748be 100%);
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.18),
    inset 0 1px 0 rgba(255, 255, 255, 0.22),
    0 9px 22px rgba(30, 91, 233, 0.35);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.02em;
}

.brand-mark::after {
  position: absolute;
  top: 7px;
  right: 7px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #f6bd6b;
  box-shadow: 0 0 0 3px rgba(246, 189, 107, 0.12);
  content: "";
}

.brand-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
}

.brand-copy strong {
  font-size: 18px;
  letter-spacing: 0.01em;
  line-height: 1.3;
}

.brand-copy small {
  margin-top: 4px;
  color: #87a5b5;
  font-size: 9px;
  letter-spacing: 0.12em;
}

.sidebar-nav {
  min-height: 0;
  flex: 1;
  margin-top: 20px;
  padding-bottom: 8px;
  overflow-y: auto;
  scrollbar-width: none;
}

.sidebar-nav::-webkit-scrollbar {
  display: none;
}

.sidebar-group + .sidebar-group {
  position: relative;
  margin-top: 17px;
  padding-top: 16px;
}

.sidebar-group + .sidebar-group::before {
  position: absolute;
  top: 0;
  right: 10px;
  left: 10px;
  height: 1px;
  background: linear-gradient(
    90deg,
    rgba(255, 255, 255, 0.11),
    rgba(255, 255, 255, 0.03)
  );
  content: "";
}

.sidebar-section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin: 0 10px 8px;
}

.sidebar-section-heading span {
  color: #90aab9;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
}

.sidebar-section-heading small {
  color: #587685;
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 0.14em;
}

.sidebar-menu {
  width: 100%;
  border-right: 0;
  background: transparent;
}

.sidebar-menu :deep(.el-menu-item) {
  position: relative;
  height: 48px;
  margin-bottom: 3px;
  padding: 0 11px;
  border: 1px solid transparent;
  border-radius: 8px;
  color: #bdced8;
  font-size: 13px;
  font-weight: 600;
  transition:
    color 0.18s ease,
    border-color 0.18s ease,
    background 0.18s ease,
    box-shadow 0.18s ease;
}

.sidebar-menu :deep(.el-menu-item .el-icon) {
  display: inline-grid;
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  margin-right: 11px;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, 0.055);
  border-radius: 7px;
  color: #9fb6c4;
  background: rgba(255, 255, 255, 0.045);
  font-size: 16px;
  transition:
    color 0.18s ease,
    border-color 0.18s ease,
    background 0.18s ease;
}

.sidebar-menu :deep(.el-menu-item:hover) {
  color: #fff;
  border-color: rgba(255, 255, 255, 0.065);
  background: rgba(255, 255, 255, 0.055);
}

.sidebar-menu :deep(.el-menu-item:hover .el-icon) {
  border-color: rgba(155, 188, 255, 0.16);
  color: #c7dbff;
  background: rgba(105, 151, 255, 0.1);
}

.sidebar-menu :deep(.el-menu-item.is-active) {
  color: #fff;
  border-color: rgba(151, 183, 255, 0.15);
  background: linear-gradient(
    100deg,
    rgba(68, 111, 232, 0.25),
    rgba(38, 122, 111, 0.14)
  );
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.06),
    0 9px 22px rgba(2, 16, 24, 0.16);
}

.sidebar-menu :deep(.el-menu-item.is-active::before) {
  position: absolute;
  top: 9px;
  bottom: 9px;
  left: 0;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: #f4b860;
  box-shadow: 0 0 10px rgba(244, 184, 96, 0.45);
  content: "";
}

.sidebar-menu :deep(.el-menu-item.is-active::after) {
  position: absolute;
  top: 50%;
  right: 11px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #f4b860;
  box-shadow: 0 0 0 4px rgba(244, 184, 96, 0.09);
  content: "";
  transform: translateY(-50%);
}

.sidebar-menu :deep(.el-menu-item.is-active .el-icon) {
  border-color: rgba(246, 189, 107, 0.2);
  color: #ffd28d;
  background: rgba(246, 189, 107, 0.12);
}

.menu-title {
  display: flex;
  min-width: 0;
  flex: 1;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.menu-badge {
  display: inline-flex;
  height: 19px;
  align-items: center;
  padding: 0 6px;
  border: 1px solid rgba(246, 189, 107, 0.22);
  border-radius: 5px;
  color: #f7c77f;
  background: rgba(246, 189, 107, 0.09);
  font-size: 8px;
  font-weight: 800;
  letter-spacing: 0.06em;
}

.sidebar-menu :deep(.el-menu-item.is-active .menu-badge) {
  border-color: rgba(246, 189, 107, 0.32);
  color: #ffe0ad;
  background: rgba(246, 189, 107, 0.14);
}

.sidebar-menu :deep(.el-menu-tooltip__trigger) {
  padding: 0;
}

.is-collapsed .sidebar-menu :deep(.el-menu-item) {
  justify-content: center;
  padding: 0 !important;
}

.is-collapsed .sidebar-menu :deep(.el-menu-item.is-active) {
  background:
    linear-gradient(
      135deg,
      rgba(68, 111, 232, 0.32),
      rgba(38, 122, 111, 0.2)
    ) !important;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.06),
    0 9px 22px rgba(2, 16, 24, 0.16);
}

.is-collapsed .sidebar-menu :deep(.el-menu-item .el-icon) {
  margin-right: 0;
}

.is-collapsed .sidebar-menu :deep(.el-menu-item.is-active::after) {
  display: none;
}

.is-collapsed .sidebar-group + .sidebar-group {
  margin-top: 10px;
  padding-top: 10px;
}

.is-collapsed .brand-button {
  justify-content: center;
  padding-right: 0;
  padding-left: 0;
}

.is-collapsed .brand-button::after {
  right: 8px;
  left: 8px;
}

.collapse-button {
  display: grid;
  width: 40px;
  height: 40px;
  margin: 10px auto 0;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, 0.11);
  border-radius: 8px;
  color: #b7cbd6;
  background: rgba(255, 255, 255, 0.035);
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    color 0.18s ease,
    background 0.18s ease;
}

.collapse-button:hover {
  border-color: rgba(132, 173, 255, 0.28);
  color: #e4efff;
  background: rgba(91, 135, 244, 0.12);
}

.app-main {
  min-height: 100vh;
  transition: margin-left 0.01s cubic-bezier(0.2, 0.75, 0.25, 1);
}

.app-header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  height: 82px;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 0 clamp(20px, 2.7vw, 38px);
  border-bottom: 1px solid var(--app-border);
  background: linear-gradient(
    90deg,
    color-mix(in srgb, var(--app-surface) 98%, var(--app-primary)),
    var(--app-surface) 38%,
    color-mix(in srgb, var(--app-surface) 98%, var(--app-success))
  );
  box-shadow:
    0 1px 0 rgba(23, 43, 58, 0.02),
    0 10px 28px rgba(23, 43, 58, 0.035);
  backdrop-filter: blur(18px);
}

.app-header::after {
  position: absolute;
  right: 0;
  bottom: -1px;
  left: 0;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(36, 107, 254, 0.26) 20%,
    rgba(20, 154, 118, 0.14) 62%,
    rgba(217, 131, 26, 0.22)
  );
  content: "";
  pointer-events: none;
}

.header-leading,
.header-actions,
.user-summary {
  display: flex;
  align-items: center;
}

.header-leading {
  min-width: 0;
  gap: 12px;
}

.header-title {
  display: flex;
  min-width: 0;
  flex-direction: column;
}

.header-context {
  color: var(--app-muted);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.08em;
  line-height: 1.2;
}

.header-page {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 9px;
  margin-top: 4px;
}

.header-page-mark {
  display: grid;
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  place-items: center;
  border: 1px solid color-mix(in srgb, var(--app-primary) 16%, var(--app-border));
  border-radius: 7px;
  color: var(--app-primary);
  background:
    linear-gradient(145deg, var(--app-primary-soft), var(--app-surface));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.62),
    0 3px 9px rgba(36, 107, 254, 0.07);
  font-size: 15px;
}

.header-page strong {
  overflow: hidden;
  color: var(--app-text);
  font-size: 16px;
  font-weight: 740;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-actions {
  gap: 8px;
  flex: none;
}

.header-divider {
  width: 1px;
  height: 24px;
  margin: 0 3px;
  background: linear-gradient(
    to bottom,
    transparent,
    var(--app-border-strong),
    transparent
  );
}

.content-switcher {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 7px;
  padding: 5px 6px 5px 11px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: color-mix(in srgb, var(--app-surface-muted) 74%, transparent);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.72),
    0 2px 8px rgba(23, 43, 58, 0.025);
}

.content-switcher-label {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--app-muted);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

.content-select {
  width: 205px;
}

.content-switcher :deep(.el-select__wrapper) {
  min-height: 32px;
  border-radius: 6px;
  background: var(--app-surface);
  box-shadow:
    inset 0 0 0 1px color-mix(in srgb, var(--app-border) 76%, transparent);
}

.content-switcher :deep(.el-select__wrapper.is-focused) {
  box-shadow:
    inset 0 0 0 1px var(--app-primary),
    0 0 0 2px var(--app-primary-soft);
}

.content-switcher .icon-button {
  width: 32px;
  height: 32px;
  border-color: transparent;
  border-radius: 6px;
  background: transparent;
}

.content-switcher .icon-button:hover {
  border-color: transparent;
  color: var(--app-primary);
  background: var(--app-primary-soft);
}

.generate-button {
  flex: 0 0 32px;
}

.icon-button-wrap {
  display: inline-flex;
}

.icon-button.delete-button:disabled {
  border-color: transparent;
  color: var(--app-muted);
  background: transparent;
  cursor: not-allowed;
  opacity: 0.55;
}

.content-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.content-option small {
  color: var(--app-muted);
  font-size: 10px;
}

.icon-button {
  display: grid;
  width: 36px;
  height: 36px;
  place-items: center;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  color: var(--app-text);
  background: var(--app-surface);
  cursor: pointer;
  transition:
    border-color 0.16s ease,
    color 0.16s ease,
    background 0.16s ease;
}

.icon-button:hover {
  border-color: color-mix(in srgb, var(--app-primary) 58%, var(--app-border));
  color: var(--app-primary);
  background: var(--app-primary-soft);
}

.mobile-menu-button {
  display: none;
}

.header-action-button {
  border-color: transparent;
  background: transparent;
}

.user-summary {
  position: relative;
  gap: 9px;
  padding: 3px 10px 3px 3px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  color: var(--app-text);
  background:
    linear-gradient(145deg, var(--app-surface), var(--app-surface-muted));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.68),
    0 2px 7px rgba(23, 43, 58, 0.025);
  font-family: inherit;
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;
  transition:
    border-color 0.16s ease,
    background 0.16s ease;
}

.user-summary:hover,
.user-summary:focus-visible {
  border-color: color-mix(in srgb, var(--app-primary) 45%, var(--app-border));
  background: var(--app-surface);
  outline: none;
}

.user-menu-arrow {
  color: var(--app-muted);
  font-size: 11px;
}

.user-name {
  max-width: 96px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-avatar {
  color: #fff;
  background:
    linear-gradient(145deg, #5687ff, var(--app-primary-strong));
  box-shadow: 0 2px 7px rgba(36, 107, 254, 0.22);
}

.user-presence {
  width: 6px;
  height: 6px;
  flex: 0 0 6px;
  border-radius: 50%;
  background: var(--app-success);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--app-success) 10%, transparent);
}

.logout-button {
  gap: 5px;
  color: var(--app-muted);
}

.logout-button:hover {
  color: var(--app-text);
}

.page-content {
  width: 100%;
  max-width: 1540px;
  margin: 0 auto;
  padding: clamp(22px, 2.7vw, 38px);
}

.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.16s ease, transform 0.16s ease;
}

.page-fade-enter-from,
.page-fade-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

.sidebar-mask {
  position: fixed;
  inset: 0;
  z-index: 25;
  background: rgba(10, 24, 34, 0.45);
  backdrop-filter: blur(2px);
}

@media (max-width: 900px) {
  .app-sidebar {
    width: 268px !important;
    transform: translateX(-105%);
  }

  .app-sidebar.is-mobile-open {
    transform: translateX(0);
  }

  .app-main {
    margin-left: 0 !important;
  }

  .mobile-menu-button {
    display: grid;
  }

  .content-switcher-label {
    display: none;
  }

  .content-select {
    width: 176px;
  }
}

@media (max-width: 640px) {
  .app-header {
    height: 70px;
    padding: 0 16px;
  }

  .header-context {
    display: none;
  }

  .header-page {
    margin-top: 0;
  }

  .header-page-mark {
    width: 28px;
    height: 28px;
    flex-basis: 28px;
  }

  .header-page strong {
    font-size: 14px;
  }

  .user-name,
  .logout-button span {
    display: none;
  }

  .user-menu-arrow {
    display: none;
  }

  .header-actions {
    gap: 8px;
  }

  .content-switcher {
    margin-left: auto;
  }

  .content-select {
    width: 132px;
  }

  .user-summary {
    padding: 3px;
    border: 0;
    background: transparent;
  }

  .page-content {
    padding: 18px 14px 28px;
  }

}

@media (max-width: 480px) {
  .app-header {
    gap: 8px;
    padding: 0 10px;
  }

  .header-leading,
  .content-switcher {
    gap: 6px;
  }

  .content-select {
    width: 110px;
  }

  .content-switcher .icon-button {
    width: 32px;
    height: 32px;
    flex: 0 0 32px;
  }

  .header-actions > .icon-button,
  .logout-button {
    display: none;
  }
}

@media (max-width: 420px) {
  .header-page strong {
    display: block;
    max-width: 58px;
    font-size: 13px;
  }

  .content-select {
    width: 142px;
  }

  .content-switcher .delete-button:disabled {
    display: none;
  }

  .header-actions {
    display: none;
  }
}

@media (max-width: 360px) {
  .header-page strong {
    display: none;
  }

  .content-select {
    width: 128px;
  }
}
</style>
