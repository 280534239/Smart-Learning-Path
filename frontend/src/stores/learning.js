import { defineStore } from 'pinia'

import {
  analyzeLearning,
  getLearningProgress,
} from '../api/dashboard'

export const useLearningStore = defineStore('learning', {
  state: () => ({
    masteryMap: {},
    overallLevel: '入门',
    overallMastery: 0,
    recommendations: [],
    learningPath: [],
    progressPoints: [],
    totalPoints: 0,
    assessedPoints: 0,
    masteredPoints: 0,
    studyStreakDays: 0,
    totalStudyMinutes: 0,
    weeklyQuestions: 0,
    weeklyAccuracy: 0,
    weeklyStudyMinutes: 0,
    recentActivities: [],
    weakPoints: [],
    dailyActivity: [],
    loading: false,
    loaded: false,
  }),

  getters: {
    categoryMastery: (state) => {
      const grouped = new Map()
      for (const point of state.progressPoints) {
        const current = grouped.get(point.category) || {
          total: 0,
          count: 0,
        }
        current.total += point.mastery
        current.count += 1
        grouped.set(point.category, current)
      }
      return Array.from(grouped.entries()).map(([name, value]) => ({
        name,
        value: value.total / value.count,
      }))
    },
  },

  actions: {
    async fetchDashboard(subject) {
      this.loading = true
      try {
        const [progress, analysis] = await Promise.all([
          getLearningProgress(subject),
          analyzeLearning(subject),
        ])
        this.masteryMap = analysis.mastery_map
        this.overallLevel = analysis.overall_level
        this.overallMastery = analysis.overall_mastery
        this.recommendations = analysis.recommendations
        this.learningPath = analysis.learning_path
        this.progressPoints = progress.points
        this.totalPoints = progress.total_points
        this.assessedPoints = progress.assessed_points
        this.masteredPoints = progress.mastered_points
        this.studyStreakDays = progress.study_streak_days
        this.totalStudyMinutes = progress.total_study_minutes
        this.weeklyQuestions = progress.weekly_questions
        this.weeklyAccuracy = progress.weekly_accuracy
        this.weeklyStudyMinutes = progress.weekly_study_minutes
        this.recentActivities = progress.recent_activities
        this.weakPoints = progress.weak_points
        this.dailyActivity = progress.daily_activity
        this.loaded = true
      } finally {
        this.loading = false
      }
    },

    reset() {
      this.$reset()
    },
  },
})
