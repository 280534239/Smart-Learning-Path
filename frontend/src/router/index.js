import { createRouter, createWebHistory } from 'vue-router'

import { getInitialDiagnosisStatus } from '../api/diagnosis'
import AppLayout from '../components/AppLayout.vue'
import { useLearningContentStore } from '../stores/learningContent'
import { useUserStore } from '../stores/user'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/initial-diagnosis/:subject',
    name: 'InitialDiagnosis',
    component: () => import('../views/InitialDiagnosis.vue'),
    meta: { title: '初始诊断' },
  },
  {
    path: '/onboarding',
    name: 'Onboarding',
    component: () => import('../views/LearningContentOnboarding.vue'),
    meta: { title: '创建学习内容' },
  },
  {
    path: '/',
    component: AppLayout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('../views/Dashboard.vue'),
        meta: { title: '学习看板' },
      },
      {
        path: 'diagnosis',
        name: 'Diagnosis',
        component: () => import('../views/Diagnosis.vue'),
        meta: { title: '智能诊断' },
      },
      {
        path: 'knowledge',
        name: 'KnowledgeMap',
        component: () => import('../views/KnowledgeMap.vue'),
        meta: { title: '知识图谱' },
      },
      {
        path: 'learning-path',
        name: 'LearningPath',
        component: () => import('../views/LearningPath.vue'),
        meta: { title: '学习路径' },
      },
      {
        path: 'practice',
        name: 'Practice',
        component: () => import('../views/Practice.vue'),
        meta: { title: '在线练习' },
      },
      {
        path: 'chat',
        name: 'ChatAssistant',
        component: () => import('../views/ChatAssistant.vue'),
        meta: { title: 'AI答疑' },
      },
      {
        path: 'error-book',
        name: 'ErrorBook',
        component: () => import('../views/ErrorBook.vue'),
        meta: { title: '错题本' },
      },
      {
        path: 'user-center',
        name: 'UserCenter',
        component: () => import('../views/UserCenter.vue'),
        meta: {
          title: '用户中心',
          allowPendingDiagnosis: true,
        },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to) => {
  const userStore = useUserStore()
  document.title = to.meta.title
    ? `${to.meta.title} · 智学路径`
    : '智学路径'

  if (!to.meta.public && !userStore.isAuthenticated) {
    return {
      name: 'Login',
      query: { redirect: to.fullPath },
    }
  }

  if (to.meta.public && userStore.isAuthenticated) {
    return { name: 'Dashboard' }
  }

  if (!to.meta.public) {
    const learningContentStore = useLearningContentStore()
    try {
      await learningContentStore.fetchSubjects()
    } catch {
      if (to.name !== 'Onboarding') {
        return { name: 'Onboarding' }
      }
      return true
    }

    if (!learningContentStore.subjects.length) {
      if (to.name !== 'Onboarding') {
        return { name: 'Onboarding' }
      }
      return true
    }

    if (to.name === 'Onboarding') {
      return { name: 'Dashboard' }
    }

    const routeSubject =
      to.name === 'InitialDiagnosis' &&
      typeof to.params.subject === 'string'
        ? to.params.subject
        : ''
    const subject = routeSubject || learningContentStore.activeSubject
    if (routeSubject && routeSubject !== learningContentStore.activeSubject) {
      learningContentStore.setActiveSubject(routeSubject)
    }
    const content = learningContentStore.subjects.find(
      (item) => item.subject === subject,
    )
    if (routeSubject && !content) {
      return { name: 'Dashboard' }
    }
    if (content?.generated && !to.meta.allowPendingDiagnosis) {
      try {
        const diagnosisStatus = await getInitialDiagnosisStatus(subject)
        const isInitialDiagnosisPage = to.name === 'InitialDiagnosis'
        if (diagnosisStatus.completed && isInitialDiagnosisPage) {
          return { name: 'LearningPath' }
        }
        if (!diagnosisStatus.completed && !isInitialDiagnosisPage) {
          return {
            name: 'InitialDiagnosis',
            params: { subject },
          }
        }
      } catch {
        // 页面层的访问守卫会继续提示并阻止未确认状态的访问。
      }
    }
  }

  return true
})

export default router
