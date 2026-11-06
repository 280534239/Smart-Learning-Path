<script setup>
import { computed } from 'vue'

const props = defineProps({
  node: {
    type: Object,
    required: true,
  },
  active: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['select'])

const categoryColor = computed(() => {
  const colors = {
    基础语法: '#246BFE',
    流程控制: '#149A76',
    数据结构: '#D9831A',
    函数: '#909399',
    面向对象: '#D94F59',
    高级特性: '#7B61FF',
  }
  return colors[props.node.category] || '#246BFE'
})
</script>

<template>
  <button
    type="button"
    class="knowledge-node"
    :class="{ 'is-active': active }"
    :style="{ '--node-color': categoryColor }"
    @click="emit('select', node)"
  >
    <span class="node-heading">
      <strong>{{ node.name }}</strong>
      <span class="difficulty">L{{ node.difficulty }}</span>
    </span>
    <span class="category">{{ node.category }}</span>
    <span class="node-id">{{ node.id }}</span>
  </button>
</template>

<style scoped>
.knowledge-node {
  display: flex;
  width: 100%;
  min-width: 180px;
  flex-direction: column;
  gap: 7px;
  padding: 14px;
  border: 1px solid var(--app-border);
  border-left: 3px solid var(--node-color);
  border-radius: 8px;
  color: var(--app-text);
  text-align: left;
  background: var(--app-surface);
  cursor: pointer;
}

.knowledge-node:hover,
.knowledge-node.is-active {
  border-color: var(--node-color);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--node-color) 14%, transparent);
}

.node-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.node-heading strong {
  font-size: 14px;
  line-height: 1.45;
}

.difficulty {
  flex: none;
  padding: 2px 6px;
  border-radius: 4px;
  color: var(--node-color);
  background: color-mix(in srgb, var(--node-color) 12%, transparent);
  font-size: 10px;
  font-weight: 700;
}

.category {
  color: var(--node-color);
  font-size: 12px;
  font-weight: 650;
}

.node-id {
  color: var(--app-muted);
  font-family: "SFMono-Regular", Consolas, monospace;
  font-size: 10px;
}
</style>
