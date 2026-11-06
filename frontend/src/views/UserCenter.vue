<script setup>
import {
  Calendar,
  Camera,
  ChatDotRound,
  Clock,
  Collection,
  DataAnalysis,
  EditPen,
  Lock,
  Moon,
  Refresh,
  Setting,
  Sunny,
  SwitchButton,
  User,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import {
  computed,
  onMounted,
  reactive,
  ref,
  watch,
} from 'vue'
import { useRoute, useRouter } from 'vue-router'

import * as authApi from '../api/auth'
import { getUserCenterSummary } from '../api/userCenter'
import { useLearningContentStore } from '../stores/learningContent'
import { useLearningStore } from '../stores/learning'
import { usePracticeStore } from '../stores/practice'
import { useUserStore } from '../stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const learningContentStore = useLearningContentStore()
const learningStore = useLearningStore()
const practiceStore = usePracticeStore()

const tabItems = [
  { key: 'profile', label: '个人资料', icon: User },
  { key: 'learning', label: '学习档案', icon: DataAnalysis },
  { key: 'settings', label: '偏好设置', icon: Setting },
  { key: 'security', label: '账号安全', icon: Lock },
]
const validTabs = new Set(tabItems.map((item) => item.key))

const activeTab = ref(
  validTabs.has(String(route.query.tab || ''))
    ? String(route.query.tab)
    : 'profile',
)
const loading = ref(true)
const loadError = ref(false)
const summary = ref(null)
const profileSaving = ref(false)
const avatarUploading = ref(false)
const passwordSaving = ref(false)
const profileForm = reactive({
  nickname: '',
  bio: '',
})
const passwordForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const profile = computed(() => userStore.profile || {})
const activeContentStats = computed(
  () =>
    summary.value?.contents?.find(
      (item) => item.subject === learningContentStore.activeSubject,
    ) || null,
)
const joinedDays = computed(() => {
  if (!profile.value.created_at) return 0
  const joined = new Date(profile.value.created_at)
  if (Number.isNaN(joined.getTime())) return 0
  return Math.max(
    1,
    Math.ceil((Date.now() - joined.getTime()) / 86_400_000),
  )
})
const accuracyPercent = computed(() =>
  Math.round((summary.value?.overall_accuracy || 0) * 100),
)
const activeLevel = computed(
  () => activeContentStats.value?.level || '待诊断',
)
const activeGoal = computed(
  () =>
    activeContentStats.value?.learning_goal ||
    '建立系统、可实践的知识体系',
)

watch(
  () => route.query.tab,
  (tab) => {
    const nextTab = String(tab || '')
    if (validTabs.has(nextTab) && nextTab !== activeTab.value) {
      activeTab.value = nextTab
    }
  },
)

watch(
  () => userStore.profile,
  () => syncProfileForm(),
  { deep: true },
)

onMounted(loadData)

function syncProfileForm() {
  profileForm.nickname = profile.value.nickname || ''
  profileForm.bio = profile.value.bio || ''
}

async function loadData() {
  loading.value = true
  loadError.value = false
  try {
    const [, summaryData] = await Promise.all([
      userStore.fetchProfile(),
      getUserCenterSummary(),
    ])
    syncProfileForm()
    summary.value = summaryData
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

function switchTab(tab) {
  if (!validTabs.has(tab)) return
  activeTab.value = tab
  router.replace({
    path: '/user-center',
    query: { tab },
  })
}

async function saveProfile() {
  if (profileForm.nickname.length > 50) {
    ElMessage.warning('昵称不能超过 50 个字符')
    return
  }
  if (profileForm.bio.length > 280) {
    ElMessage.warning('个人简介不能超过 280 个字符')
    return
  }

  profileSaving.value = true
  try {
    await userStore.updateProfile({
      nickname: profileForm.nickname.trim() || null,
      bio: profileForm.bio.trim() || null,
    })
    syncProfileForm()
    ElMessage.success('个人资料已保存')
  } catch {
    // 请求层已展示具体错误。
  } finally {
    profileSaving.value = false
  }
}

async function handleAvatarChange(uploadFile) {
  const file = uploadFile?.raw
  if (!file) return
  if (!file.type.startsWith('image/')) {
    ElMessage.warning('请选择图片文件')
    return
  }
  if (file.size > 2 * 1024 * 1024) {
    ElMessage.warning('头像文件不能超过 2 MB')
    return
  }

  avatarUploading.value = true
  try {
    const data = await authApi.uploadAvatar(file)
    userStore.applyProfilePatch({ avatar_url: data.avatar_url })
    ElMessage.success('头像已更新')
  } catch {
    // 请求层已展示具体错误。
  } finally {
    avatarUploading.value = false
  }
}

async function submitPassword() {
  if (passwordForm.newPassword.length < 8) {
    ElMessage.warning('新密码至少需要 8 个字符')
    return
  }
  if (passwordForm.newPassword !== passwordForm.confirmPassword) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }

  passwordSaving.value = true
  try {
    await authApi.changePassword({
      old_password: passwordForm.oldPassword,
      new_password: passwordForm.newPassword,
    })
    passwordForm.oldPassword = ''
    passwordForm.newPassword = ''
    passwordForm.confirmPassword = ''
    ElMessage.success('密码修改成功')
  } catch {
    // 请求层已展示具体错误。
  } finally {
    passwordSaving.value = false
  }
}

function selectTheme(theme) {
  userStore.setTheme(theme)
}

function selectDefaultSubject(subject) {
  learningContentStore.setActiveSubject(subject)
  const title = learningContentStore.activeTitle
  ElMessage.success(`默认学习内容已切换为「${title}」`)
}

function openLearningContent(subject) {
  learningContentStore.setActiveSubject(subject)
  router.push({ name: 'Dashboard' })
}

function handleLogout() {
  learningStore.reset()
  learningContentStore.reset()
  practiceStore.reset()
  userStore.logout()
  router.replace({ name: 'Login' })
}

function formatDate(value, withTime = false) {
  if (!value) return '暂无记录'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '暂无记录'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    ...(withTime
      ? { hour: '2-digit', minute: '2-digit', hour12: false }
      : {}),
  }).format(date)
}

function formatDuration(minutes) {
  const total = Math.max(0, Math.round(Number(minutes) || 0))
  if (total < 60) return `${total} 分钟`
  const hours = Math.floor(total / 60)
  const remaining = total % 60
  return remaining
    ? `${hours} 小时 ${remaining} 分钟`
    : `${hours} 小时`
}

function masteryPercent(value) {
  return Math.round((Number(value) || 0) * 100)
}
</script>

<template>
  <section class="user-center-page">
    <header class="page-heading">
      <div>
        <p class="page-kicker">ACCOUNT & LEARNING PROFILE</p>
        <h1>用户中心</h1>
        <span>管理个人资料、查看跨学习内容档案并调整账号偏好。</span>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadData">
        刷新数据
      </el-button>
    </header>

    <div v-if="loading" class="user-center-loading surface-panel">
      <el-skeleton :rows="12" animated />
    </div>

    <div v-else-if="loadError" class="surface-panel empty-panel">
      <el-empty description="用户中心数据加载失败" :image-size="92">
        <el-button :icon="Refresh" @click="loadData">重新加载</el-button>
      </el-empty>
    </div>

    <div v-else class="user-center-layout">
      <aside class="user-center-aside">
        <div class="identity-panel">
          <el-avatar
            :size="72"
            :src="profile.avatar_url"
            class="identity-avatar"
          >
            {{ userStore.avatarText }}
          </el-avatar>
          <strong>{{ userStore.displayName }}</strong>
          <span>@{{ profile.username }}</span>
          <small>
            <el-icon><Calendar /></el-icon>
            已加入 {{ joinedDays }} 天
          </small>
        </div>

        <el-menu
          :default-active="activeTab"
          class="user-center-menu"
          @select="switchTab"
        >
          <el-menu-item
            v-for="item in tabItems"
            :key="item.key"
            :index="item.key"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.label }}</span>
          </el-menu-item>
        </el-menu>
      </aside>

      <main class="user-center-content">
        <section v-if="activeTab === 'profile'" class="content-section">
          <header class="section-heading">
            <div>
              <h2>个人资料</h2>
              <p>这些信息会展示在你的学习空间中。</p>
            </div>
          </header>

          <div class="profile-editor">
            <el-upload
              class="avatar-uploader"
              action="#"
              accept="image/png,image/jpeg,image/webp,image/gif"
              :auto-upload="false"
              :show-file-list="false"
              :on-change="handleAvatarChange"
            >
              <div class="avatar-trigger">
                <el-avatar
                  :size="92"
                  :src="profile.avatar_url"
                  class="profile-avatar"
                >
                  {{ userStore.avatarText }}
                </el-avatar>
                <span class="avatar-edit">
                  <el-icon v-if="avatarUploading" class="is-loading">
                    <Refresh />
                  </el-icon>
                  <el-icon v-else><Camera /></el-icon>
                </span>
              </div>
            </el-upload>
            <div class="avatar-copy">
              <strong>个人头像</strong>
              <span>支持 PNG、JPEG、WebP、GIF，文件不超过 2 MB。</span>
            </div>
          </div>

          <el-form
            label-position="top"
            class="profile-form"
            @submit.prevent="saveProfile"
          >
            <div class="form-grid">
              <el-form-item label="昵称">
                <el-input
                  v-model="profileForm.nickname"
                  maxlength="50"
                  show-word-limit
                  placeholder="未设置时显示用户名"
                />
              </el-form-item>
              <el-form-item label="用户名">
                <el-input :model-value="profile.username" disabled />
              </el-form-item>
              <el-form-item label="邮箱">
                <el-input :model-value="profile.email" disabled />
              </el-form-item>
              <el-form-item label="注册时间">
                <el-input
                  :model-value="formatDate(profile.created_at)"
                  disabled
                />
              </el-form-item>
            </div>

            <el-form-item label="个人简介">
              <el-input
                v-model="profileForm.bio"
                type="textarea"
                :rows="4"
                maxlength="280"
                show-word-limit
                placeholder="写一句介绍自己学习方向的话"
              />
            </el-form-item>

            <div class="form-actions">
              <el-button
                type="primary"
                native-type="submit"
                :loading="profileSaving"
              >
                保存个人资料
              </el-button>
            </div>
          </el-form>

          <div class="profile-learning-context">
            <div>
              <span>当前学习内容</span>
              <strong>{{ learningContentStore.activeTitle }}</strong>
            </div>
            <div>
              <span>当前水平</span>
              <strong>{{ activeLevel }}</strong>
            </div>
            <div>
              <span>学习目标</span>
              <strong>{{ activeGoal }}</strong>
            </div>
          </div>
        </section>

        <section v-else-if="activeTab === 'learning'" class="content-section">
          <header class="section-heading">
            <div>
              <h2>学习档案</h2>
              <p>汇总全部学习内容的学习投入与诊断记录。</p>
            </div>
          </header>

          <div class="metric-grid">
            <article class="metric-item">
              <span class="metric-icon blue"><el-icon><Clock /></el-icon></span>
              <div>
                <small>总学习时长</small>
                <strong>{{ formatDuration(summary?.total_study_minutes) }}</strong>
              </div>
            </article>
            <article class="metric-item">
              <span class="metric-icon green"><el-icon><EditPen /></el-icon></span>
              <div>
                <small>累计做题</small>
                <strong>{{ summary?.total_questions || 0 }} 道</strong>
              </div>
            </article>
            <article class="metric-item">
              <span class="metric-icon yellow"><el-icon><DataAnalysis /></el-icon></span>
              <div>
                <small>整体正确率</small>
                <strong>{{ accuracyPercent }}%</strong>
              </div>
            </article>
            <article class="metric-item">
              <span class="metric-icon red"><el-icon><Collection /></el-icon></span>
              <div>
                <small>错题 / 已掌握</small>
                <strong>
                  {{ summary?.error_count || 0 }} /
                  {{ summary?.mastered_error_count || 0 }}
                </strong>
              </div>
            </article>
            <article class="metric-item">
              <span class="metric-icon blue"><el-icon><Calendar /></el-icon></span>
              <div>
                <small>连续学习</small>
                <strong>{{ summary?.study_streak_days || 0 }} 天</strong>
              </div>
            </article>
            <article class="metric-item">
              <span class="metric-icon green"><el-icon><ChatDotRound /></el-icon></span>
              <div>
                <small>AI 答疑会话</small>
                <strong>{{ summary?.chat_session_count || 0 }} 次</strong>
              </div>
            </article>
          </div>

          <section class="subsection">
            <div class="subsection-heading">
              <div>
                <h3>学习内容掌握度</h3>
                <p>{{ summary?.learning_content_count || 0 }} 份学习内容</p>
              </div>
            </div>
            <div v-if="summary?.contents?.length" class="content-progress-list">
              <button
                v-for="item in summary.contents"
                :key="item.subject"
                type="button"
                class="content-progress-row"
                @click="openLearningContent(item.subject)"
              >
                <span class="content-progress-copy">
                  <strong>{{ item.title }}</strong>
                  <small>
                    {{ item.level || '未诊断' }} ·
                    {{ item.assessed_points }} / {{ item.node_count }} 个知识点已评估
                  </small>
                </span>
                <span class="content-mastery">
                  <el-progress
                    :percentage="masteryPercent(item.overall_mastery)"
                    :stroke-width="7"
                    :show-text="false"
                  />
                  <b>{{ masteryPercent(item.overall_mastery) }}%</b>
                </span>
              </button>
            </div>
            <el-empty v-else description="暂无学习内容数据" :image-size="72" />
          </section>

          <div class="history-grid">
            <section class="subsection">
              <div class="subsection-heading">
                <div>
                  <h3>诊断记录</h3>
                  <p>最近 30 次诊断结果</p>
                </div>
              </div>
              <div
                v-if="summary?.diagnoses?.length"
                class="history-list"
              >
                <div
                  v-for="item in summary.diagnoses"
                  :key="item.id"
                  class="history-row"
                >
                  <span class="history-marker"></span>
                  <div>
                    <strong>{{ item.subject_title }}</strong>
                    <span>{{ item.label }}</span>
                  </div>
                  <div class="history-result">
                    <b>{{ masteryPercent(item.overall_mastery) }}%</b>
                    <small>{{ formatDate(item.created_at, true) }}</small>
                  </div>
                </div>
              </div>
              <el-empty v-else description="暂无诊断记录" :image-size="64" />
            </section>

            <section class="subsection">
              <div class="subsection-heading">
                <div>
                  <h3>学习路径</h3>
                  <p>已生成的个性化计划</p>
                </div>
              </div>
              <div
                v-if="summary?.learning_paths?.length"
                class="history-list"
              >
                <div
                  v-for="item in summary.learning_paths"
                  :key="item.id"
                  class="path-history-row"
                >
                  <div>
                    <strong>{{ item.subject_title }}</strong>
                    <span>{{ item.path_summary || '个性化学习路径' }}</span>
                  </div>
                  <div class="history-result">
                    <b>{{ item.step_count }} 步</b>
                    <small>{{ formatDate(item.generated_at) }}</small>
                  </div>
                </div>
              </div>
              <el-empty v-else description="暂无学习路径" :image-size="64" />
            </section>
          </div>
        </section>

        <section v-else-if="activeTab === 'settings'" class="content-section">
          <header class="section-heading">
            <div>
              <h2>偏好设置</h2>
              <p>设置会保存在当前浏览器和账号中。</p>
            </div>
          </header>

          <div class="settings-list">
            <section class="setting-row">
              <div>
                <strong>界面主题</strong>
                <p>切换学习空间的亮色或暗色外观。</p>
              </div>
              <el-radio-group
                :model-value="userStore.theme"
                @change="selectTheme"
              >
                <el-radio-button value="light">
                  <el-icon><Sunny /></el-icon>
                  浅色
                </el-radio-button>
                <el-radio-button value="dark">
                  <el-icon><Moon /></el-icon>
                  深色
                </el-radio-button>
              </el-radio-group>
            </section>

            <section class="setting-row">
              <div>
                <strong>默认学习内容</strong>
                <p>登录后优先打开该学习内容，可在顶部随时切换。</p>
              </div>
              <el-select
                :model-value="learningContentStore.activeSubject"
                class="setting-select"
                @change="selectDefaultSubject"
              >
                <el-option
                  v-for="item in learningContentStore.subjects"
                  :key="item.subject"
                  :label="item.title"
                  :value="item.subject"
                />
              </el-select>
            </section>

            <section class="setting-row setting-summary">
              <div>
                <strong>学习空间概览</strong>
                <p>当前账号关联的学习内容与档案状态。</p>
              </div>
              <div class="setting-summary-values">
                <span>
                  <b>{{ summary?.learning_content_count || 0 }}</b>
                  学习内容
                </span>
                <span>
                  <b>{{ summary?.total_questions || 0 }}</b>
                  累计做题
                </span>
                <span>
                  <b>{{ joinedDays }}</b>
                  加入天数
                </span>
              </div>
            </section>
          </div>
        </section>

        <section v-else class="content-section">
          <header class="section-heading">
            <div>
              <h2>账号安全</h2>
              <p>修改登录密码，或退出当前账号。</p>
            </div>
          </header>

          <section class="security-panel">
            <div class="security-heading">
              <span class="security-icon"><el-icon><Lock /></el-icon></span>
              <div>
                <h3>修改密码</h3>
                <p>修改后，当前登录状态会继续有效。</p>
              </div>
            </div>
            <el-form
              label-position="top"
              class="password-form"
              @submit.prevent="submitPassword"
            >
              <el-form-item label="当前密码">
                <el-input
                  v-model="passwordForm.oldPassword"
                  type="password"
                  show-password
                  autocomplete="current-password"
                />
              </el-form-item>
              <div class="form-grid">
                <el-form-item label="新密码">
                  <el-input
                    v-model="passwordForm.newPassword"
                    type="password"
                    show-password
                    autocomplete="new-password"
                  />
                </el-form-item>
                <el-form-item label="确认新密码">
                  <el-input
                    v-model="passwordForm.confirmPassword"
                    type="password"
                    show-password
                    autocomplete="new-password"
                  />
                </el-form-item>
              </div>
              <el-button
                type="primary"
                native-type="submit"
                :loading="passwordSaving"
              >
                保存新密码
              </el-button>
            </el-form>
          </section>

          <section class="security-panel signout-panel">
            <div>
              <h3>退出当前账号</h3>
              <p>退出后可随时重新登录，学习数据不会丢失。</p>
            </div>
            <el-button :icon="SwitchButton" @click="handleLogout">
              退出登录
            </el-button>
          </section>
        </section>
      </main>
    </div>
  </section>
</template>

<style scoped>
.user-center-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.user-center-loading {
  min-height: 520px;
  padding: 28px;
}

.user-center-layout {
  display: grid;
  grid-template-columns: 248px minmax(0, 1fr);
  align-items: start;
  gap: 18px;
}

.user-center-aside,
.content-section {
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
  box-shadow: var(--app-shadow);
}

.user-center-aside {
  position: sticky;
  top: 104px;
  overflow: hidden;
}

.identity-panel {
  display: flex;
  align-items: center;
  flex-direction: column;
  padding: 24px 18px 20px;
  border-bottom: 1px solid var(--app-border);
  background:
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--app-primary-soft) 66%, var(--app-surface)),
      var(--app-surface)
    );
  text-align: center;
}

.identity-avatar,
.profile-avatar {
  color: #fff;
  background: linear-gradient(145deg, #5687ff, var(--app-primary-strong));
}

.identity-avatar {
  margin-bottom: 12px;
  box-shadow: 0 10px 24px rgba(36, 107, 254, 0.18);
}

.identity-panel strong {
  max-width: 100%;
  overflow: hidden;
  color: var(--app-text);
  font-size: 17px;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.identity-panel > span {
  max-width: 100%;
  overflow: hidden;
  margin-top: 2px;
  color: var(--app-muted);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.identity-panel small {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin-top: 10px;
  color: var(--app-text-soft);
  font-size: 11px;
}

.user-center-menu {
  padding: 10px;
  border-right: 0;
  background: transparent;
}

.user-center-menu :deep(.el-menu-item) {
  height: 44px;
  margin-bottom: 3px;
  border-radius: 6px;
  color: var(--app-text-soft);
}

.user-center-menu :deep(.el-menu-item:hover) {
  color: var(--app-text);
  background: var(--app-surface-muted);
}

.user-center-menu :deep(.el-menu-item.is-active) {
  color: var(--app-primary);
  background: var(--app-primary-soft);
  font-weight: 700;
}

.content-section {
  min-width: 0;
  padding: clamp(20px, 3vw, 30px);
}

.section-heading,
.subsection-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.section-heading {
  padding-bottom: 18px;
  border-bottom: 1px solid var(--app-border);
}

.section-heading h2,
.subsection-heading h3,
.security-heading h3,
.signout-panel h3 {
  margin: 0;
  color: var(--app-text);
  font-size: 18px;
  line-height: 1.4;
}

.section-heading p,
.subsection-heading p,
.security-heading p,
.signout-panel p {
  margin: 4px 0 0;
  color: var(--app-muted);
  font-size: 12px;
  line-height: 1.55;
}

.profile-editor {
  display: flex;
  align-items: center;
  gap: 18px;
  margin-top: 22px;
  padding: 18px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface-muted);
}

.avatar-uploader,
.avatar-trigger {
  display: block;
}

.avatar-trigger {
  position: relative;
  cursor: pointer;
}

.avatar-edit {
  position: absolute;
  right: -2px;
  bottom: 0;
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border: 2px solid var(--app-surface);
  border-radius: 50%;
  color: #fff;
  background: var(--app-primary);
  box-shadow: 0 3px 10px rgba(36, 107, 254, 0.2);
}

.avatar-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
}

.avatar-copy strong {
  color: var(--app-text);
  font-size: 14px;
}

.avatar-copy span {
  color: var(--app-muted);
  font-size: 12px;
  line-height: 1.55;
}

.profile-form {
  margin-top: 22px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 14px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
}

.profile-learning-context {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid var(--app-border);
}

.profile-learning-context > div {
  display: grid;
  gap: 5px;
  min-width: 0;
  padding: 12px 14px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface-muted);
}

.profile-learning-context span {
  color: var(--app-muted);
  font-size: 10px;
}

.profile-learning-context strong {
  overflow: hidden;
  color: var(--app-text);
  font-size: 12px;
  line-height: 1.55;
  text-overflow: ellipsis;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 18px;
}

.metric-item {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 11px;
  padding: 13px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface-muted);
}

.metric-icon {
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  place-items: center;
  border-radius: 8px;
  font-size: 18px;
}

.metric-icon.blue {
  color: var(--app-primary);
  background: var(--app-primary-soft);
}

.metric-icon.green {
  color: var(--app-success);
  background: color-mix(in srgb, var(--app-success) 10%, transparent);
}

.metric-icon.yellow {
  color: var(--app-warning);
  background: color-mix(in srgb, var(--app-warning) 10%, transparent);
}

.metric-icon.red {
  color: var(--app-danger);
  background: color-mix(in srgb, var(--app-danger) 9%, transparent);
}

.metric-item > div {
  display: grid;
  min-width: 0;
  gap: 3px;
}

.metric-item small {
  color: var(--app-muted);
  font-size: 10px;
}

.metric-item strong {
  overflow: hidden;
  color: var(--app-text);
  font-size: 15px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.subsection {
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid var(--app-border);
}

.content-progress-list,
.history-list {
  display: grid;
  gap: 7px;
  margin-top: 12px;
}

.content-progress-row {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 12px 13px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  color: inherit;
  text-align: left;
  background: var(--app-surface-muted);
  cursor: pointer;
}

.content-progress-row:hover {
  border-color: color-mix(in srgb, var(--app-primary) 38%, var(--app-border));
}

.content-progress-copy {
  display: grid;
  min-width: 0;
  gap: 3px;
}

.content-progress-copy strong {
  overflow: hidden;
  color: var(--app-text);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.content-progress-copy small {
  color: var(--app-muted);
  font-size: 10px;
}

.content-mastery {
  display: flex;
  width: min(260px, 34%);
  flex: none;
  align-items: center;
  gap: 9px;
}

.content-mastery :deep(.el-progress) {
  flex: 1;
}

.content-mastery b {
  width: 34px;
  color: var(--app-primary);
  font-size: 12px;
  text-align: right;
}

.history-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

.history-row,
.path-history-row {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 9px;
  padding: 10px 11px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface-muted);
}

.history-marker {
  width: 7px;
  height: 7px;
  flex: 0 0 7px;
  border-radius: 50%;
  background: var(--app-success);
}

.history-row > div:not(.history-result),
.path-history-row > div:not(.history-result) {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 3px;
}

.history-row strong,
.path-history-row strong {
  color: var(--app-text);
  font-size: 12px;
}

.history-row span,
.path-history-row span {
  overflow: hidden;
  color: var(--app-muted);
  font-size: 10px;
  line-height: 1.5;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-result {
  display: grid;
  flex: none;
  gap: 2px;
  text-align: right;
}

.history-result b {
  color: var(--app-primary);
  font-size: 12px;
}

.history-result small {
  color: var(--app-muted);
  font-size: 9px;
}

.settings-list {
  display: grid;
  gap: 0;
  margin-top: 18px;
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 28px;
  padding: 20px 0;
  border-bottom: 1px solid var(--app-border);
}

.setting-row:first-child {
  padding-top: 0;
}

.setting-row:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}

.setting-row > div:first-child {
  min-width: 0;
}

.setting-row strong {
  color: var(--app-text);
  font-size: 14px;
}

.setting-row p {
  margin: 5px 0 0;
  color: var(--app-muted);
  font-size: 11px;
  line-height: 1.6;
}

.setting-row :deep(.el-radio-button__inner) {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.setting-select {
  width: min(300px, 45%);
}

.setting-summary-values {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.setting-summary-values span {
  display: grid;
  min-width: 92px;
  gap: 2px;
  padding: 9px 11px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  color: var(--app-muted);
  background: var(--app-surface-muted);
  font-size: 9px;
  text-align: center;
}

.setting-summary-values b {
  color: var(--app-text);
  font-size: 15px;
}

.security-panel {
  margin-top: 18px;
  padding: 18px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface-muted);
}

.security-heading {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.security-icon {
  display: grid;
  width: 40px;
  height: 40px;
  flex: 0 0 40px;
  place-items: center;
  border-radius: 8px;
  color: var(--app-primary);
  background: var(--app-primary-soft);
  font-size: 19px;
}

.password-form {
  max-width: 620px;
  margin-top: 18px;
}

.signout-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

@media (max-width: 1080px) {
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .history-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 820px) {
  .user-center-layout {
    grid-template-columns: 1fr;
  }

  .user-center-aside {
    position: static;
  }

  .identity-panel {
    align-items: flex-start;
    flex-direction: row;
    flex-wrap: wrap;
    gap: 8px 12px;
    padding: 16px;
    text-align: left;
  }

  .identity-avatar {
    width: 50px !important;
    height: 50px !important;
    margin: 0;
  }

  .identity-panel strong {
    align-self: flex-end;
  }

  .identity-panel > span,
  .identity-panel small {
    align-self: flex-end;
    margin-top: 0;
  }

  .identity-panel small {
    flex-basis: 100%;
  }

  .user-center-menu {
    display: flex;
    overflow-x: auto;
    padding: 8px;
    scrollbar-width: none;
  }

  .user-center-menu::-webkit-scrollbar {
    display: none;
  }

  .user-center-menu :deep(.el-menu-item) {
    flex: 0 0 auto;
    margin: 0 3px 0 0;
    padding: 0 13px;
  }
}

@media (max-width: 640px) {
  .content-section {
    padding: 18px 14px;
  }

  .profile-editor {
    align-items: flex-start;
  }

  .form-grid,
  .profile-learning-context,
  .metric-grid {
    grid-template-columns: 1fr;
  }

  .content-progress-row {
    align-items: stretch;
    flex-direction: column;
    gap: 10px;
  }

  .content-mastery {
    width: 100%;
  }

  .setting-row,
  .signout-panel {
    align-items: stretch;
    flex-direction: column;
    gap: 14px;
  }

  .setting-select {
    width: 100%;
  }

  .setting-summary-values {
    justify-content: stretch;
  }

  .setting-summary-values span {
    flex: 1;
  }
}
</style>
