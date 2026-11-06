import { defineStore } from 'pinia'

import {
  deleteLearningSubject,
  generateLearningSubject,
  getLearningSubjects,
} from '../api/knowledge'
import { getUserScopedStorageKey } from '../utils/userStorage'

export const SUBJECT_STORAGE_KEY = 'slp_active_subject'
export const LEARNING_CONTENT_DELETED_EVENT =
  'slp-learning-content-deleted'

const FLOATING_ASSISTANT_HISTORY_BASE_KEY =
  'slp_floating_assistant_history_v1'
const CHAT_SESSIONS_BASE_KEY = 'slp_chat_sessions'

function getSubjectStorageKey() {
  return getUserScopedStorageKey(SUBJECT_STORAGE_KEY)
}

function removeSubjectLocalData(subject) {
  try {
    const storageKey = getUserScopedStorageKey(
      FLOATING_ASSISTANT_HISTORY_BASE_KEY,
    )
    const saved = JSON.parse(
      localStorage.getItem(storageKey) || 'null',
    )
    if (saved?.version === 1 && saved.threads?.[subject]) {
      delete saved.threads[subject]
      localStorage.setItem(
        storageKey,
        JSON.stringify(saved),
      )
    }
  } catch {
    // 本地对话记录损坏时不影响服务端删除。
  }

  try {
    const storageKey = getUserScopedStorageKey(CHAT_SESSIONS_BASE_KEY)
    const sessions = JSON.parse(
      localStorage.getItem(storageKey) || '[]',
    )
    if (Array.isArray(sessions)) {
      const remainingSessions = sessions.filter((session) => {
        const knowledgeContext = String(
          session.knowledgeContext || '',
        )
        const inferredSubject =
          knowledgeContext.match(
            /^(custom_(?:\d+_)?[a-z0-9]+)_/i,
          )?.[1] ||
          ''
        return (session.subject || inferredSubject) !== subject
      })
      localStorage.setItem(
        storageKey,
        JSON.stringify(remainingSessions),
      )
    }
  } catch {
    // 损坏的会话索引会在下次进入答疑页时自动重置。
  }
}

export const useLearningContentStore = defineStore('learningContent', {
  state: () => ({
    subjects: [],
    activeSubject: localStorage.getItem(getSubjectStorageKey()) || '',
    loading: false,
    generating: false,
    deleting: false,
    initialized: false,
  }),

  getters: {
    activeContent: (state) =>
      state.subjects.find(
        (item) => item.subject === state.activeSubject,
      ) || null,
    activeTitle() {
      return this.activeContent?.title || '未选择学习内容'
    },
  },

  actions: {
    async fetchSubjects({ force = false } = {}) {
      if (this.loading || (this.initialized && !force)) return
      this.loading = true
      try {
        const data = await getLearningSubjects()
        this.subjects = data.subjects || []
        const available = new Set(
          this.subjects.map((item) => item.subject),
        )
        if (!available.has(this.activeSubject)) {
          const defaultSubject = available.has(data.default_subject)
            ? data.default_subject
            : this.subjects[0]?.subject || ''
          this.setActiveSubject(defaultSubject)
        }
        this.initialized = true
      } finally {
        this.loading = false
      }
    },

    setActiveSubject(subject) {
      const nextSubject = subject || ''
      this.activeSubject = nextSubject
      if (nextSubject) {
        localStorage.setItem(getSubjectStorageKey(), nextSubject)
      } else {
        localStorage.removeItem(getSubjectStorageKey())
      }
    },

    async generateSubject(payload) {
      this.generating = true
      try {
        const graph = await generateLearningSubject(payload)
        await this.fetchSubjects({ force: true })
        this.setActiveSubject(graph.subject)
        return graph
      } finally {
        this.generating = false
      }
    },

    async deleteSubject(subject) {
      this.deleting = true
      let result
      try {
        result = await deleteLearningSubject(subject)
        removeSubjectLocalData(subject)
        window.dispatchEvent(
          new CustomEvent(LEARNING_CONTENT_DELETED_EVENT, {
            detail: { subject },
          }),
        )
        if (this.activeSubject === subject) {
          this.setActiveSubject('')
        }
      } finally {
        this.deleting = false
      }

      await this.fetchSubjects({ force: true }).catch(() => {})
      return result
    },

    reset() {
      this.subjects = []
      this.activeSubject = ''
      this.loading = false
      this.generating = false
      this.deleting = false
      this.initialized = false
      localStorage.removeItem(getSubjectStorageKey())
    },
  },
})
