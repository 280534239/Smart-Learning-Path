<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import AIFloatingAssistant from './components/AIFloatingAssistant.vue'
import { useUserStore } from './stores/user'

const route = useRoute()
const userStore = useUserStore()
const showAssistant = computed(
  () =>
    userStore.isAuthenticated &&
    !route.meta.public &&
    !['InitialDiagnosis', 'Onboarding', 'UserCenter'].includes(route.name),
)
</script>

<template>
  <router-view />
  <AIFloatingAssistant v-if="showAssistant" />
</template>
