<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  question: {
    type: Object,
    required: true,
  },
  index: {
    type: Number,
    default: 1,
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['submit'])

const answer = ref('')
const startedAt = ref(Date.now())

const typeLabel = computed(() => {
  const labels = {
    choice: '单选题',
    fill_blank: '填空题',
    short_answer: '简答题',
  }
  return labels[props.question.type] || '题目'
})

const canSubmit = computed(
  () => answer.value.trim().length > 0 && !props.loading,
)

watch(
  () => props.question.id,
  () => {
    answer.value = ''
    startedAt.value = Date.now()
  },
)

function selectOption(option) {
  answer.value = option.trim().slice(0, 1)
}

function submit() {
  if (!canSubmit.value) return
  emit('submit', {
    questionId: props.question.id,
    answer: answer.value.trim(),
    timeSpent: Math.max(1, Math.round((Date.now() - startedAt.value) / 1000)),
  })
}
</script>

<template>
  <article class="question-card">
    <header class="question-header">
      <span class="question-index">{{ String(index).padStart(2, '0') }}</span>
      <div>
        <strong>{{ typeLabel }}</strong>
        <small>难度 {{ question.difficulty }}</small>
      </div>
    </header>

    <p class="question-title">{{ question.question }}</p>

    <el-radio-group
      v-if="question.type === 'choice'"
      v-model="answer"
      class="option-list"
    >
      <el-radio
        v-for="option in question.options"
        :key="option"
        :value="option.trim().slice(0, 1)"
        border
      >
        {{ option }}
      </el-radio>
    </el-radio-group>

    <el-input
      v-else
      v-model="answer"
      :type="question.type === 'short_answer' ? 'textarea' : 'text'"
      :rows="question.type === 'short_answer' ? 4 : undefined"
      :placeholder="question.type === 'short_answer' ? '写下你的理解' : '填写答案'"
      maxlength="2000"
      show-word-limit
    />

    <footer class="question-footer">
      <el-button
        type="primary"
        :loading="loading"
        :disabled="!canSubmit"
        @click="submit"
      >
        提交答案
      </el-button>
    </footer>
  </article>
</template>

<style scoped>
.question-card {
  padding: 20px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
}

.question-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.question-index {
  display: grid;
  width: 36px;
  height: 36px;
  place-items: center;
  border-radius: 8px;
  color: #246BFE;
  background: rgba(36, 107, 254, 0.1);
  font-size: 12px;
  font-weight: 800;
}

.question-header > div {
  display: flex;
  flex-direction: column;
}

.question-header strong {
  color: var(--app-text);
  font-size: 13px;
}

.question-header small {
  color: var(--app-muted);
  font-size: 11px;
}

.question-title {
  margin: 18px 0;
  color: var(--app-text);
  font-size: 16px;
  font-weight: 650;
  line-height: 1.7;
  white-space: pre-wrap;
}

.option-list {
  display: flex;
  align-items: stretch;
  flex-direction: column;
  gap: 10px;
}

.option-list :deep(.el-radio) {
  width: 100%;
  height: auto;
  min-height: 44px;
  margin-right: 0;
  padding: 10px 14px;
}

.option-list :deep(.el-radio__label) {
  white-space: normal;
  line-height: 1.55;
}

.question-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 18px;
}
</style>
