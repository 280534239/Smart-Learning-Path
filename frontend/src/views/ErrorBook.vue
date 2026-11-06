<script setup>
import {
  Calendar,
  Check,
  EditPen,
  Refresh,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { getKnowledgeGraph } from '../api/knowledge'
import {
  getErrorBook,
  reviewError,
} from '../api/practice'
import { useLearningContentStore } from '../stores/learningContent'

const router = useRouter()
const learningContentStore = useLearningContentStore()

const items = ref([])
const pointNames = ref({})
const selectedPoint = ref('')
const dateRange = ref([])
const page = ref(1)
const pageSize = 5
const loading = ref(true)
const reviewingId = ref(null)

const knowledgeOptions = computed(() => {
  const pointIds = [...new Set(items.value.map((item) => item.knowledge_point_id))]
  return pointIds.map((pointId) => ({
    value: pointId,
    label: pointNames.value[pointId] || pointId,
  }))
})

const filteredItems = computed(() =>
  items.value.filter((item) => {
    if (
      selectedPoint.value &&
      item.knowledge_point_id !== selectedPoint.value
    ) {
      return false
    }
    if (dateRange.value?.length === 2) {
      const itemDate = new Date(item.created_at)
      const start = new Date(`${dateRange.value[0]}T00:00:00`)
      const end = new Date(`${dateRange.value[1]}T23:59:59`)
      if (itemDate < start || itemDate > end) return false
    }
    return true
  }),
)

const pagedItems = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredItems.value.slice(start, start + pageSize)
})

const totalCount = computed(() => items.value.length)
const masteredCount = computed(
  () => items.value.filter((item) => item.is_mastered).length,
)
const masteryRate = computed(() =>
  totalCount.value
    ? Math.round((masteredCount.value / totalCount.value) * 100)
    : 0,
)

watch([selectedPoint, dateRange], () => {
  page.value = 1
})

watch(
  () => learningContentStore.activeSubject,
  () => {
    selectedPoint.value = ''
    dateRange.value = []
    page.value = 1
    loadData()
  },
)

onMounted(loadData)

async function loadData() {
  loading.value = true
  try {
    const subject = learningContentStore.activeSubject
    const book = await getErrorBook(subject)
    items.value = book.items
    try {
      const graph = await getKnowledgeGraph(subject)
      pointNames.value = Object.fromEntries(
        graph.nodes.map((node) => [node.id, node.name]),
      )
    } catch {
      pointNames.value = {}
    }
  } finally {
    loading.value = false
  }
}

async function markMastered(item) {
  if (item.is_mastered) return
  reviewingId.value = item.id
  try {
    const result = await reviewError({
      error_book_id: item.id,
    })
    item.is_mastered = result.is_mastered
    item.review_count = result.review_count
    ElMessage.success('已标记为掌握')
  } finally {
    reviewingId.value = null
  }
}

function repeatPractice(item) {
  router.push({
    path: '/practice',
    query: { kp: item.knowledge_point_id },
  })
}

function pointName(pointId) {
  return pointNames.value[pointId] || pointId
}

function formatDate(value) {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date(value))
}

function questionTypeLabel(type) {
  return {
    choice: '选择题',
    fill_blank: '填空题',
    short_answer: '简答题',
  }[type] || '题目'
}
</script>

<template>
  <section class="error-book-page">
    <header class="page-heading">
      <div>
        <p class="page-kicker">ERROR REVIEW</p>
        <h1>错题本</h1>
        <span>回看易错知识点，把每一次错误变成下一步的线索。</span>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadData">
        刷新
      </el-button>
    </header>

    <el-card shadow="never" class="filter-card">
      <div class="filter-row">
        <label>
          <span>知识点</span>
          <el-select
            v-model="selectedPoint"
            placeholder="全部知识点"
            clearable
          >
            <el-option
              v-for="option in knowledgeOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </label>

        <label class="date-filter">
          <span>时间范围</span>
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            clearable
          />
        </label>

        <span class="filter-result">
          共 {{ filteredItems.length }} 条匹配错题
        </span>
      </div>
    </el-card>

    <div v-if="loading" class="error-loading">
      <el-skeleton :rows="9" animated />
    </div>

    <template v-else>
      <div v-if="pagedItems.length" class="error-list">
        <el-card
          v-for="item in pagedItems"
          :key="item.id"
          shadow="never"
          class="error-card"
          :class="{ 'is-mastered': item.is_mastered }"
        >
          <header class="error-card-header">
            <div class="error-tags">
              <el-tag effect="plain">
                {{ questionTypeLabel(item.question_type) }}
              </el-tag>
              <el-tag type="info" effect="plain">
                难度 {{ item.difficulty }}
              </el-tag>
              <el-tag
                :type="item.is_mastered ? 'success' : 'danger'"
                effect="light"
              >
                {{ item.is_mastered ? '已掌握' : '待巩固' }}
              </el-tag>
            </div>
            <time>{{ formatDate(item.created_at) }}</time>
          </header>

          <h2>{{ item.question }}</h2>

          <div class="answer-compare">
            <div class="answer-block wrong">
              <span>我的答案</span>
              <p>{{ item.original_answer }}</p>
            </div>
            <div class="answer-block correct">
              <span>正确答案</span>
              <p>{{ item.correct_answer }}</p>
            </div>
          </div>

          <div class="explanation-block">
            <span>解析</span>
            <p>{{ item.explanation || '暂无解析' }}</p>
          </div>

          <footer class="error-card-footer">
            <div>
              <el-tag effect="plain" class="point-tag">
                {{ pointName(item.knowledge_point_id) }}
              </el-tag>
              <span class="review-count">已复习 {{ item.review_count }} 次</span>
            </div>
            <div class="error-actions">
              <el-button :icon="EditPen" @click="repeatPractice(item)">
                再练一次
              </el-button>
              <el-button
                type="success"
                plain
                :icon="Check"
                :loading="reviewingId === item.id"
                :disabled="item.is_mastered"
                @click="markMastered(item)"
              >
                {{ item.is_mastered ? '已掌握' : '标记已掌握' }}
              </el-button>
            </div>
          </footer>
        </el-card>
      </div>

      <el-card v-else shadow="never" class="empty-card">
        <el-empty description="当前筛选条件下没有错题" :image-size="92" />
      </el-card>

      <div v-if="filteredItems.length > pageSize" class="pagination-row">
        <el-pagination
          v-model:current-page="page"
          background
          layout="prev, pager, next"
          :page-size="pageSize"
          :total="filteredItems.length"
        />
      </div>
    </template>

    <el-card shadow="never" class="summary-card">
      <div class="summary-heading">
        <div>
          <span>错题本概览</span>
          <h2>把错题逐渐变成已掌握</h2>
        </div>
        <el-icon><Calendar /></el-icon>
      </div>
      <div class="summary-stats">
        <div>
          <small>总错题数</small>
          <strong>{{ totalCount }}</strong>
        </div>
        <div>
          <small>已掌握</small>
          <strong>{{ masteredCount }}</strong>
        </div>
        <div>
          <small>掌握率</small>
          <strong>{{ masteryRate }}%</strong>
        </div>
      </div>
    </el-card>
  </section>
</template>

<style scoped>
.error-book-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-card,
.summary-card,
.error-card,
.empty-card {
  border-color: var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
}

.filter-card :deep(.el-card__body) {
  padding: 16px 18px;
}

.filter-row {
  display: flex;
  align-items: flex-end;
  gap: 18px;
}

.filter-row label {
  display: flex;
  min-width: 220px;
  flex-direction: column;
  gap: 7px;
}

.filter-row label > span {
  color: var(--app-muted);
  font-size: 11px;
  font-weight: 650;
}

.filter-row :deep(.el-select) {
  width: 220px;
}

.date-filter {
  min-width: 300px !important;
}

.filter-result {
  margin-left: auto;
  padding-bottom: 10px;
  color: var(--app-muted);
  font-size: 11px;
}

.error-loading {
  min-height: 420px;
  padding: 24px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
}

.error-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.error-card {
  transition: opacity 0.2s ease;
}

.error-card.is-mastered {
  opacity: 0.82;
}

.error-card :deep(.el-card__body) {
  padding: clamp(20px, 3vw, 28px);
}

.error-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.error-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.error-card-header time {
  color: var(--app-muted);
  font-size: 10px;
  white-space: nowrap;
}

.error-card h2 {
  margin: 18px 0;
  color: var(--app-text);
  font-size: 17px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.answer-compare {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.answer-block {
  min-width: 0;
  padding: 12px;
  border: 1px solid;
  border-radius: 8px;
}

.answer-block.wrong {
  border-color: rgba(217, 79, 89, 0.3);
  background: rgba(217, 79, 89, 0.05);
}

.answer-block.correct {
  border-color: rgba(20, 154, 118, 0.3);
  background: rgba(20, 154, 118, 0.05);
}

.answer-block span {
  font-size: 10px;
  font-weight: 700;
}

.answer-block.wrong span {
  color: #D94F59;
}

.answer-block.correct span {
  color: #149A76;
}

.answer-block p {
  margin: 7px 0 0;
  color: var(--app-text);
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.explanation-block {
  margin-top: 14px;
  padding: 12px;
  border-left: 3px solid #246BFE;
  background: var(--app-surface-muted);
}

.explanation-block span {
  color: #246BFE;
  font-size: 10px;
  font-weight: 700;
}

.explanation-block p {
  margin: 5px 0 0;
  color: var(--app-muted);
  font-size: 12px;
  line-height: 1.7;
}

.error-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--app-border);
}

.error-card-footer > div:first-child {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 10px;
}

.point-tag {
  max-width: 220px;
}

.review-count {
  color: var(--app-muted);
  font-size: 10px;
}

.error-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.empty-card :deep(.el-card__body) {
  min-height: 300px;
}

.pagination-row {
  display: flex;
  justify-content: center;
  padding: 8px 0;
}

.summary-card {
  margin-top: 2px;
}

.summary-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 28px;
}

.summary-heading {
  display: flex;
  align-items: center;
  gap: 14px;
}

.summary-heading > .el-icon {
  color: #246BFE;
  font-size: 26px;
}

.summary-heading span {
  color: var(--app-muted);
  font-size: 10px;
}

.summary-heading h2 {
  margin: 5px 0 0;
  color: var(--app-text);
  font-size: 16px;
}

.summary-stats {
  display: flex;
  min-width: min(480px, 50%);
  justify-content: space-between;
}

.summary-stats > div {
  display: flex;
  min-width: 90px;
  align-items: flex-end;
  flex-direction: column;
  padding-left: 22px;
  border-left: 1px solid var(--app-border);
}

.summary-stats small {
  color: var(--app-muted);
  font-size: 10px;
}

.summary-stats strong {
  margin-top: 5px;
  color: var(--app-text);
  font-size: 26px;
  line-height: 1;
}

@media (max-width: 900px) {
  .filter-row {
    align-items: stretch;
    flex-direction: column;
    gap: 12px;
  }

  .filter-row label,
  .filter-row :deep(.el-select),
  .date-filter,
  .filter-row :deep(.el-date-editor) {
    width: 100%;
    min-width: 0 !important;
  }

  .filter-result {
    margin-left: 0;
    padding-bottom: 0;
  }

  .summary-card :deep(.el-card__body) {
    align-items: stretch;
    flex-direction: column;
  }

  .summary-stats {
    width: 100%;
    min-width: 0;
  }
}

@media (max-width: 640px) {
  .answer-compare {
    grid-template-columns: 1fr;
  }

  .error-card-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .error-card-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .error-card-footer > div:first-child {
    justify-content: space-between;
  }

  .error-actions {
    flex-direction: column;
  }

  .error-actions .el-button {
    width: 100%;
    margin-left: 0;
  }

  .summary-stats {
    gap: 10px;
  }

  .summary-stats > div {
    flex: 1;
    align-items: flex-start;
    padding-left: 10px;
  }
}
</style>
