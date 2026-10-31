<script setup>
import { computed, onMounted, ref } from 'vue'
import { CircleCheckFilled, Loading, WarningFilled } from '@element-plus/icons-vue'

import { getHealth } from './api/client'

const healthState = ref('checking')
const healthMessage = ref('正在连接后端服务')

const statusMeta = computed(() => {
  const states = {
    checking: {
      label: '连接中',
      type: 'info',
      icon: Loading,
    },
    online: {
      label: '服务正常',
      type: 'success',
      icon: CircleCheckFilled,
    },
    offline: {
      label: '服务未连接',
      type: 'danger',
      icon: WarningFilled,
    },
  }

  return states[healthState.value]
})

async function checkHealth() {
  healthState.value = 'checking'
  healthMessage.value = '正在连接后端服务'

  try {
    const data = await getHealth()
    healthState.value = 'online'
    healthMessage.value = `${data.service} · v${data.version}`
  } catch (error) {
    healthState.value = 'offline'
    healthMessage.value =
      error instanceof Error ? error.message : '无法连接后端服务'
  }
}

onMounted(checkHealth)
</script>

<template>
  <main class="welcome">
    <div class="brand" aria-hidden="true">SLP</div>

    <section class="hero" aria-labelledby="welcome-title">
      <p class="eyebrow">SMART LEARNING PATH</p>
      <h1 id="welcome-title">
        <span class="hello">Hello</span>
        <span class="brand-name">智学路径</span>
      </h1>
      <p class="subtitle">为每一位学生生成专属学习路径的 AI 私教平台</p>

      <div class="health" aria-live="polite">
        <el-tag :type="statusMeta.type" effect="plain" round>
          <el-icon
            :class="{ 'is-loading': healthState === 'checking' }"
            class="health-icon"
          >
            <component :is="statusMeta.icon" />
          </el-icon>
          {{ statusMeta.label }}
        </el-tag>
        <span class="health-copy">{{ healthMessage }}</span>
      </div>
    </section>

    <footer class="footer">
      <span>Vue 3</span>
      <span class="divider" aria-hidden="true"></span>
      <span>FastAPI</span>
      <span class="divider" aria-hidden="true"></span>
      <span>AI Adaptive Learning</span>
    </footer>
  </main>
</template>
