<script setup>
import {
  ArrowRight,
  Lock,
  Message,
  Moon,
  Sunny,
  User,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, nextTick, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useUserStore } from '../stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const mode = ref('login')
const loading = ref(false)
const formRef = ref()
const form = reactive({
  username: '',
  email: '',
  password: '',
})

const isRegister = computed(() => mode.value === 'register')
const isDark = computed(() => userStore.theme === 'dark')

const formRules = computed(() => ({
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    {
      min: isRegister.value ? 3 : 1,
      max: 50,
      message: '用户名长度不符合要求',
      trigger: 'blur',
    },
  ],
  email: isRegister.value
    ? [
        { required: true, message: '请输入邮箱', trigger: 'blur' },
        {
          type: 'email',
          message: '请输入有效的邮箱地址',
          trigger: 'blur',
        },
      ]
    : [],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    {
      min: isRegister.value ? 8 : 6,
      max: 72,
      message: isRegister.value
        ? '密码至少需要 8 个字符'
        : '密码长度不符合要求',
      trigger: 'blur',
    },
  ],
}))

async function switchMode(nextMode) {
  if (mode.value === nextMode) return
  mode.value = nextMode
  form.email = ''
  await nextTick()
  formRef.value?.clearValidate()
}

async function submit() {
  const valid = await formRef.value
    ?.validate()
    .catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    if (isRegister.value) {
      await userStore.register({
        username: form.username,
        email: form.email,
        password: form.password,
      })
      ElMessage.success('注册成功，已为你登录')
    } else {
      await userStore.login({
        username: form.username,
        password: form.password,
      })
      ElMessage.success('登录成功')
    }

    const redirect =
      typeof route.query.redirect === 'string' &&
      route.query.redirect.startsWith('/') &&
      !route.query.redirect.startsWith('//')
        ? route.query.redirect
        : '/dashboard'
    await router.replace(redirect)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="auth-page">
    <button
      class="theme-toggle"
      type="button"
      :aria-label="isDark ? '切换亮色主题' : '切换暗色主题'"
      @click="userStore.toggleTheme"
    >
      <el-icon>
        <Sunny v-if="isDark" />
        <Moon v-else />
      </el-icon>
    </button>

    <section class="auth-intro">
      <div class="intro-brand">
        <span class="intro-mark">SLP</span>
        <span>智学路径</span>
      </div>

      <div class="intro-copy">
        <p class="intro-kicker">SMART LEARNING PATH</p>
        <h1>让每一步学习，<br />都有清晰方向。</h1>
        <p class="intro-description">
          AI 私教、知识图谱与自适应路径，共同组成你的个性化学习空间。
        </p>
      </div>

      <div class="graph-motif" aria-hidden="true">
        <span class="graph-line line-a"></span>
        <span class="graph-line line-b"></span>
        <span class="graph-line line-c"></span>
        <span class="graph-node node-a">诊断</span>
        <span class="graph-node node-b">路径</span>
        <span class="graph-node node-c">练习</span>
        <span class="graph-node node-d">答疑</span>
      </div>
    </section>

    <section class="auth-form-section">
      <div class="auth-card">
        <header class="auth-heading">
          <p>{{ isRegister ? 'CREATE ACCOUNT' : 'WELCOME BACK' }}</p>
          <h2>{{ isRegister ? '创建学习账号' : '欢迎回来' }}</h2>
          <span>
            {{ isRegister ? '开始你的个性化学习旅程' : '继续今天的学习进度' }}
          </span>
        </header>

        <div class="mode-switch" role="tablist" aria-label="账号操作">
          <button
            type="button"
            :class="{ active: mode === 'login' }"
            @click="switchMode('login')"
          >
            登录
          </button>
          <button
            type="button"
            :class="{ active: mode === 'register' }"
            @click="switchMode('register')"
          >
            注册
          </button>
        </div>

        <el-form
          ref="formRef"
          :model="form"
          :rules="formRules"
          label-position="top"
          class="auth-form"
          @submit.prevent="submit"
        >
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model="form.username"
              size="large"
              autocomplete="username"
              placeholder="请输入用户名"
              :prefix-icon="User"
            />
          </el-form-item>

          <el-form-item v-if="isRegister" label="邮箱" prop="email">
            <el-input
              v-model="form.email"
              size="large"
              autocomplete="email"
              placeholder="name@example.com"
              :prefix-icon="Message"
            />
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              size="large"
              type="password"
              show-password
              :autocomplete="isRegister ? 'new-password' : 'current-password'"
              :placeholder="isRegister ? '至少 8 个字符' : '请输入密码'"
              :prefix-icon="Lock"
              @keyup.enter="submit"
            />
          </el-form-item>

          <el-button
            class="submit-button"
            type="primary"
            size="large"
            native-type="submit"
            :loading="loading"
          >
            <span>{{ isRegister ? '创建账号' : '进入学习空间' }}</span>
            <el-icon><ArrowRight /></el-icon>
          </el-button>
        </el-form>

        <p class="form-footnote">
          {{ isRegister ? '已有账号？' : '还没有账号？' }}
          <button
            type="button"
            @click="switchMode(isRegister ? 'login' : 'register')"
          >
            {{ isRegister ? '直接登录' : '立即注册' }}
          </button>
        </p>
      </div>
    </section>
  </main>
</template>

<style scoped>
.auth-page {
  position: relative;
  display: grid;
  min-height: 100vh;
  grid-template-columns: minmax(0, 1.05fr) minmax(420px, 0.95fr);
  overflow-x: hidden;
  background: var(--app-bg);
}

.theme-toggle {
  position: fixed;
  top: 22px;
  right: 24px;
  z-index: 10;
  display: grid;
  width: 40px;
  height: 40px;
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

.theme-toggle:hover {
  border-color: var(--app-primary);
  color: var(--app-primary);
  background: var(--app-primary-soft);
}

.auth-intro {
  position: relative;
  display: flex;
  min-width: 0;
  min-height: 100vh;
  flex-direction: column;
  justify-content: space-between;
  padding: clamp(32px, 5vw, 68px);
  overflow: hidden;
  color: #f7fbff;
  background: #102d3b;
}

.auth-intro::after {
  position: absolute;
  inset: 0;
  content: "";
  pointer-events: none;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.055) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.055) 1px, transparent 1px);
  background-size: 52px 52px;
  mask-image: linear-gradient(to bottom, transparent, black 24%, black 78%, transparent);
}

.intro-brand,
.intro-copy,
.graph-motif {
  position: relative;
  z-index: 1;
}

.intro-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 18px;
  font-weight: 750;
}

.intro-mark {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: 8px;
  background: var(--app-primary);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.14);
  font-size: 12px;
  font-weight: 800;
}

.intro-copy {
  width: 100%;
  max-width: 660px;
}

.intro-kicker {
  margin: 0 0 20px;
  color: #a9c8ff;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
}

.intro-copy h1 {
  margin: 0;
  font-size: clamp(42px, 5.7vw, 76px);
  font-weight: 800;
  letter-spacing: 0;
  line-height: 1.12;
}

.intro-description {
  max-width: 560px;
  margin: 24px 0 0;
  color: #b8ccd8;
  font-size: clamp(15px, 1.5vw, 18px);
  line-height: 1.8;
  overflow-wrap: anywhere;
}

.graph-motif {
  width: min(500px, 90%);
  height: 150px;
}

.graph-line {
  position: absolute;
  height: 1px;
  transform-origin: left center;
  background: rgba(142, 199, 255, 0.4);
}

.line-a {
  top: 48px;
  left: 72px;
  width: 190px;
  transform: rotate(19deg);
}

.line-b {
  top: 92px;
  left: 80px;
  width: 210px;
  transform: rotate(-11deg);
}

.line-c {
  top: 72px;
  left: 270px;
  width: 150px;
  transform: rotate(29deg);
}

.graph-node {
  position: absolute;
  display: grid;
  min-width: 64px;
  min-height: 40px;
  place-items: center;
  border: 1px solid rgba(142, 199, 255, 0.5);
  border-radius: 8px;
  color: #e8f3ff;
  background: #183e53;
  font-size: 12px;
  font-weight: 650;
}

.node-a { top: 12px; left: 0; }
.node-b { top: 68px; left: 150px; }
.node-c { top: 116px; left: 60px; }
.node-d { top: 32px; right: 0; }

.auth-form-section {
  display: grid;
  width: 100%;
  min-width: 0;
  min-height: 100vh;
  place-items: center;
  padding: 56px clamp(24px, 6vw, 88px);
}

.auth-card {
  width: 100%;
  max-width: 440px;
  min-width: 0;
  padding: clamp(24px, 4vw, 36px);
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
  box-shadow: var(--app-shadow-raised);
}

.auth-heading p {
  margin: 0 0 12px;
  color: var(--app-primary);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.15em;
}

.auth-heading h2 {
  margin: 0;
  color: var(--app-text);
  font-size: clamp(28px, 4vw, 38px);
  font-weight: 760;
  line-height: 1.25;
}

.auth-heading span {
  display: block;
  margin-top: 10px;
  color: var(--app-muted);
  font-size: 14px;
}

.mode-switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  margin: 30px 0 24px;
  padding: 4px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface-muted);
}

.mode-switch button {
  height: 38px;
  border: 0;
  border-radius: 6px;
  color: var(--app-muted);
  background: transparent;
  font: inherit;
  font-size: 14px;
  font-weight: 650;
  cursor: pointer;
}

.mode-switch button.active {
  color: var(--app-primary);
  background: var(--app-surface);
  box-shadow: 0 2px 8px rgba(24, 54, 76, 0.08);
  font-weight: 700;
}

.auth-form :deep(.el-form-item__label) {
  color: var(--app-text);
  font-weight: 650;
}

.auth-form :deep(.el-input__wrapper) {
  min-height: 46px;
  border-radius: 8px;
}

.submit-button {
  width: 100%;
  height: 48px;
  margin-top: 8px;
  border-radius: 8px;
}

.submit-button :deep(span) {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.form-footnote {
  margin: 22px 0 0;
  color: var(--app-muted);
  font-size: 13px;
  text-align: center;
}

.form-footnote button {
  padding: 0;
  border: 0;
  color: var(--app-primary);
  background: transparent;
  font: inherit;
  font-weight: 650;
  cursor: pointer;
}

@media (max-width: 960px) {
  .auth-page {
    grid-template-columns: 1fr;
  }

  .auth-intro {
    min-height: auto;
    padding: 32px 24px 48px;
  }

  .intro-copy {
    margin-top: 64px;
  }

  .intro-copy h1 {
    font-size: clamp(38px, 11vw, 58px);
  }

  .graph-motif {
    display: none;
  }

  .auth-form-section {
    min-height: auto;
    padding: 40px 24px 64px;
  }
}

@media (max-width: 540px) {
  .theme-toggle {
    top: 22px;
    right: 20px;
  }

  .auth-heading h2 {
    font-size: 28px;
  }

  .auth-card {
    padding: 22px 18px;
  }
}
</style>
