<script setup>
import {
  ArrowDown,
  ArrowUp,
  Check,
  MagicStick,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { reactive } from 'vue'

const props = defineProps({
  loading: {
    type: Boolean,
    default: false,
  },
  submitLabel: {
    type: String,
    default: '生成学习内容',
  },
  cancelLabel: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['submit', 'cancel'])

const learningGoalOptions = [
  '快速入门',
  '夯实基础',
  '掌握核心概念',
  '理解底层原理',
  '提升解题能力',
  '应对考试',
  '完成实际项目',
  '拓展知识面',
]
const form = reactive({
  topic: '',
  goals: [],
  level: '基础',
})

function toggleLearningGoal(goal) {
  const index = form.goals.indexOf(goal)
  if (index === -1) {
    form.goals.push(goal)
    return
  }
  form.goals.splice(index, 1)
}

function goalPriority(goal) {
  return form.goals.indexOf(goal) + 1
}

function moveLearningGoal(goal, offset) {
  const index = form.goals.indexOf(goal)
  const targetIndex = index + offset
  if (
    index === -1 ||
    targetIndex < 0 ||
    targetIndex >= form.goals.length
  ) {
    return
  }
  const [selectedGoal] = form.goals.splice(index, 1)
  form.goals.splice(targetIndex, 0, selectedGoal)
}

function submit() {
  if (props.loading) return
  const topic = form.topic.trim()
  if (topic.length < 2) {
    ElMessage.warning('请先输入至少 2 个字的主题')
    return
  }
  emit('submit', {
    topic,
    goal: form.goals.join('、') || null,
    goal_priorities: [...form.goals],
    level: form.level,
  })
}
</script>

<template>
  <div class="learning-content-form">
    <label class="form-field">
      <span>想学习什么</span>
      <el-input
        v-model="form.topic"
        placeholder="例如：线性代数、数据结构、英语写作"
        maxlength="100"
        show-word-limit
        @keyup.enter="submit"
      />
    </label>

    <div class="form-field">
      <span>学习目标优先级（可选，多选后按 1、2、3 排序）</span>
      <div class="goal-tag-group" aria-label="选择学习目标">
        <button
          v-for="goal in learningGoalOptions"
          :key="goal"
          class="goal-tag"
          :class="{ 'is-selected': form.goals.includes(goal) }"
          type="button"
          :aria-pressed="form.goals.includes(goal)"
          @click="toggleLearningGoal(goal)"
        >
          <span
            v-if="goalPriority(goal)"
            class="goal-priority-badge"
          >
            {{ goalPriority(goal) }}
          </span>
          <span>{{ goal }}</span>
          <el-icon v-if="goalPriority(goal)">
            <Check />
          </el-icon>
        </button>
      </div>

      <div v-if="form.goals.length" class="goal-priority-editor">
        <div class="priority-editor-heading">
          <span>目标优先顺序</span>
          <small>数字越小，路径规划优先级越高</small>
        </div>
        <ol>
          <li
            v-for="(goal, index) in form.goals"
            :key="goal"
            class="priority-item"
          >
            <span class="priority-rank">{{ index + 1 }}</span>
            <span class="priority-label">{{ goal }}</span>
            <span class="priority-actions">
              <button
                type="button"
                :disabled="index === 0"
                :aria-label="`提升「${goal}」的优先级`"
                @click="moveLearningGoal(goal, -1)"
              >
                <el-icon><ArrowUp /></el-icon>
              </button>
              <button
                type="button"
                :disabled="index === form.goals.length - 1"
                :aria-label="`降低「${goal}」的优先级`"
                @click="moveLearningGoal(goal, 1)"
              >
                <el-icon><ArrowDown /></el-icon>
              </button>
            </span>
          </li>
        </ol>
      </div>
    </div>

    <label class="form-field">
      <span>当前水平</span>
      <el-radio-group v-model="form.level">
        <el-radio-button
          v-for="level in ['入门', '基础', '进阶', '高级']"
          :key="level"
          :value="level"
        >
          {{ level }}
        </el-radio-button>
      </el-radio-group>
    </label>

    <p class="form-hint">
      模型会根据主题复杂度和学习目标自动规划知识点数量；初始诊断后，
      个性化学习路径会优先安排与高优先级目标相关的内容。
    </p>

    <div v-if="loading" class="generation-status" role="status">
      <span class="status-pulse" aria-hidden="true"></span>
      <span>模型正在规划知识图谱，通常需要 20 至 60 秒，请勿关闭页面。</span>
    </div>

    <div class="form-actions">
      <el-button
        v-if="cancelLabel"
        :disabled="loading"
        @click="emit('cancel')"
      >
        {{ cancelLabel }}
      </el-button>
      <el-button
        type="primary"
        :icon="MagicStick"
        :loading="loading"
        @click="submit"
      >
        {{ submitLabel }}
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.learning-content-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-field > span {
  color: var(--app-text);
  font-size: 13px;
  font-weight: 650;
}

.goal-tag-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.goal-tag {
  display: inline-flex;
  min-height: 34px;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  color: var(--app-text-soft);
  background: var(--app-surface-muted);
  cursor: pointer;
  font-size: 12px;
  font-weight: 650;
  line-height: 1.35;
  transition:
    border-color 0.16s ease,
    color 0.16s ease,
    background 0.16s ease,
    box-shadow 0.16s ease;
}

.goal-tag:hover {
  border-color: color-mix(in srgb, var(--app-primary) 42%, var(--app-border));
  color: var(--app-primary);
  background: var(--app-primary-soft);
}

.goal-tag.is-selected {
  border-color: color-mix(in srgb, var(--app-primary) 52%, var(--app-border));
  color: var(--app-primary-strong);
  background: var(--app-primary-soft);
  box-shadow: inset 0 0 0 1px
    color-mix(in srgb, var(--app-primary) 10%, transparent);
}

.goal-tag:focus-visible {
  outline: 2px solid var(--app-primary);
  outline-offset: 2px;
}

.goal-tag .el-icon {
  font-size: 13px;
}

.goal-priority-badge {
  display: inline-grid;
  width: 18px;
  height: 18px;
  flex: 0 0 18px;
  place-items: center;
  border-radius: 50%;
  color: #fff;
  background: var(--app-primary);
  font-size: 10px;
  font-weight: 800;
  line-height: 1;
}

.goal-priority-editor {
  display: grid;
  gap: 8px;
  margin-top: 2px;
  padding: 12px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface-muted);
}

.priority-editor-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.priority-editor-heading span {
  color: var(--app-text);
  font-size: 12px;
  font-weight: 700;
}

.priority-editor-heading small {
  color: var(--app-muted);
  font-size: 10px;
}

.goal-priority-editor ol {
  display: grid;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.priority-item {
  display: flex;
  min-height: 34px;
  align-items: center;
  gap: 8px;
  padding: 4px 6px 4px 4px;
  border: 1px solid color-mix(in srgb, var(--app-border) 74%, transparent);
  border-radius: 6px;
  background: var(--app-surface);
}

.priority-rank {
  display: grid;
  width: 24px;
  height: 24px;
  flex: 0 0 24px;
  place-items: center;
  border-radius: 5px;
  color: var(--app-primary);
  background: var(--app-primary-soft);
  font-size: 12px;
  font-weight: 800;
}

.priority-label {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  color: var(--app-text-soft);
  font-size: 12px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.priority-actions {
  display: inline-flex;
  gap: 3px;
}

.priority-actions button {
  display: grid;
  width: 26px;
  height: 26px;
  place-items: center;
  border: 1px solid var(--app-border);
  border-radius: 5px;
  color: var(--app-text-soft);
  background: var(--app-surface);
  cursor: pointer;
}

.priority-actions button:hover:not(:disabled) {
  border-color: var(--app-primary);
  color: var(--app-primary);
  background: var(--app-primary-soft);
}

.priority-actions button:disabled {
  cursor: not-allowed;
  opacity: 0.35;
}

.learning-content-form :deep(.el-radio-group) {
  display: flex;
  flex-wrap: wrap;
}

.form-hint {
  margin: 0;
  color: var(--app-muted);
  font-size: 12px;
  line-height: 1.6;
}

.generation-status {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 10px 12px;
  border: 1px solid color-mix(in srgb, var(--app-primary) 20%, var(--app-border));
  border-radius: 8px;
  color: var(--app-text-soft);
  background: var(--app-primary-soft);
  font-size: 12px;
  line-height: 1.55;
}

.status-pulse {
  width: 8px;
  height: 8px;
  flex: 0 0 8px;
  border-radius: 50%;
  background: var(--app-primary);
  box-shadow: 0 0 0 0 color-mix(in srgb, var(--app-primary) 34%, transparent);
  animation: status-pulse 1.5s ease-out infinite;
}

@keyframes status-pulse {
  70% {
    box-shadow: 0 0 0 7px transparent;
  }

  100% {
    box-shadow: 0 0 0 0 transparent;
  }
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 2px;
}

@media (max-width: 540px) {
  .priority-editor-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 3px;
  }

  .form-actions {
    flex-direction: column-reverse;
  }

  .form-actions :deep(.el-button) {
    width: 100%;
    margin-left: 0;
  }
}
</style>
