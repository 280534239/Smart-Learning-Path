import { defineStore } from 'pinia'

import {
  getPracticeQuestions,
  submitAnswer,
} from '../api/practice'

export const usePracticeStore = defineStore('practice', {
  state: () => ({
    knowledgePointId: '',
    difficulty: 1,
    questions: [],
    currentIndex: 0,
    answeredCount: 0,
    correctCount: 0,
    totalTimeSeconds: 0,
    feedback: null,
    loading: false,
    submitting: false,
    startedAt: null,
  }),

  getters: {
    currentQuestion: (state) =>
      state.questions[state.currentIndex] || null,
    accuracy: (state) =>
      state.answeredCount
        ? state.correctCount / state.answeredCount
        : 0,
    isFinished: (state) =>
      state.questions.length > 0 &&
      state.currentIndex >= state.questions.length,
    progressPercentage: (state) =>
      state.questions.length
        ? Math.round(
            (state.currentIndex / state.questions.length) * 100,
          )
        : 0,
  },

  actions: {
    async startPractice({
      knowledgePointId,
      difficulty,
      count = 10,
    }) {
      this.$reset()
      this.knowledgePointId = knowledgePointId
      this.difficulty = difficulty
      this.loading = true
      this.startedAt = Date.now()
      try {
        const data = await getPracticeQuestions(knowledgePointId, {
          difficulty,
          count,
        })
        this.questions = data.questions
      } finally {
        this.loading = false
      }
    },

    async submitCurrentAnswer({ answer, timeSpent }) {
      if (!this.currentQuestion || this.feedback) return null
      this.submitting = true
      try {
        const feedback = await submitAnswer({
          question_id: this.currentQuestion.id,
          answer,
          time_spent: timeSpent,
        })
        this.feedback = feedback
        this.answeredCount += 1
        if (feedback.is_correct) {
          this.correctCount += 1
        }
        this.totalTimeSeconds += timeSpent
        return feedback
      } finally {
        this.submitting = false
      }
    },

    nextQuestion() {
      if (!this.questions.length) return
      this.feedback = null
      if (this.currentIndex < this.questions.length - 1) {
        this.currentIndex += 1
      } else {
        this.currentIndex = this.questions.length
      }
    },

    reset() {
      this.$reset()
    },
  },
})
