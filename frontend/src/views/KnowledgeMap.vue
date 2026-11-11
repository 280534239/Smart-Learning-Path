<script setup>
import {
  ArrowRight,
  Check,
  Close,
  RefreshRight,
  Search,
} from '@element-plus/icons-vue'
import * as d3 from 'd3'
import DOMPurify from 'dompurify'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  generateKnowledgePointResources,
  getKnowledgeGraph,
  getKnowledgePoint,
} from '../api/knowledge'
import { getLearningProgress } from '../api/dashboard'
import { useLearningContentStore } from '../stores/learningContent'
import { useUserStore } from '../stores/user'
import { getUserScopedStorageKey } from '../utils/userStorage'

const STATUS_META = {
  mastered: { label: '已掌握', color: '#149A76' },
  learning: { label: '学习中', color: '#D9831A' },
  weak: { label: '薄弱 / 未学', color: '#D94F59' },
  locked: { label: '前置未满足', color: '#C0C4CC' },
}
const RESOURCE_COMPLETION_STORAGE_KEY =
  'slp_completed_learning_resources_v1'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const learningContentStore = useLearningContentStore()

const graphContainer = ref(null)
const svgRef = ref(null)
const categories = ref([])
const activeCategory = ref('全部')
const graphTitle = ref('')
const searchText = ref('')
const loading = ref(true)
const loadError = ref(false)
const masteryById = ref({})
const graphNodes = ref([])
const graphEdges = ref([])
const selectedNodeId = ref('')
const selectedDetail = ref(null)
const detailLoading = ref(false)
const generatedResources = ref([])
const resourceLoading = ref(false)
const resourceError = ref('')
const readingVisible = ref(false)
const readingResource = ref(null)
const completedResourceKeys = ref(new Set())
const tooltip = ref({
  visible: false,
  x: 0,
  y: 0,
  node: null,
})

let svgSelection
let viewportSelection
let zoomBehavior
let nodeSelection
let linkSelection
let dependencyLinkSelection
let resizeObserver
let graphWidth = 1000
let graphHeight = 680
let fitFrame
let fitTimer
let currentZoomScale = 1
let resourceRequestId = 0
const resourceCache = new Map()

const activeFilter = computed(() =>
  activeCategory.value === '全部' ? null : activeCategory.value,
)

const filteredNodes = computed(() =>
  graphNodes.value.filter(
    (node) =>
      !activeFilter.value || node.category === activeFilter.value,
  ),
)

const filteredEdges = computed(() => {
  const ids = new Set(filteredNodes.value.map((node) => node.id))
  return graphEdges.value.filter(
    (edge) => ids.has(edge.from) && ids.has(edge.to),
  )
})

const selectedNode = computed(
  () =>
    graphNodes.value.find(
      (node) => node.id === selectedNodeId.value,
    ) || null,
)

const selectedMasteryPercent = computed(() =>
  Math.round(getMastery(selectedNodeId.value) * 100),
)
const completedResourceCount = computed(() =>
  generatedResources.value.filter((resource) =>
    isResourceCompleted(resource),
  ).length,
)

function normalizeText(value) {
  return String(value || '').trim().toLocaleLowerCase('zh-CN')
}

function getMastery(pointId) {
  return Number(masteryById.value[pointId] || 0)
}

function prerequisitesMet(node) {
  return node.prerequisites.every(
    (pointId) => getMastery(pointId) >= 0.7,
  )
}

function getNodeStatus(node) {
  const mastery = getMastery(node.id)
  if (!prerequisitesMet(node)) return 'locked'
  if (mastery >= 0.8) return 'mastered'
  if (mastery >= 0.3) return 'learning'
  return 'weak'
}

function getNodeColor(node) {
  return STATUS_META[getNodeStatus(node)].color
}

function getNodeRadius(node) {
  return 10 + Number(node.difficulty || 1) * 3.5
}

function getResourceCompletionKey(resource, pointId = selectedNodeId.value) {
  if (!resource?.title || !pointId) return ''
  const subject = learningContentStore.activeSubject || 'unknown'
  return `${subject}::${pointId}::${resource.title.trim()}`
}

function loadCompletedResources() {
  try {
    const stored = JSON.parse(
      localStorage.getItem(
        getUserScopedStorageKey(RESOURCE_COMPLETION_STORAGE_KEY),
      ) || '[]',
    )
    completedResourceKeys.value = new Set(
      Array.isArray(stored) ? stored : [],
    )
  } catch {
    completedResourceKeys.value = new Set()
  }
}

function saveCompletedResources() {
  localStorage.setItem(
    getUserScopedStorageKey(RESOURCE_COMPLETION_STORAGE_KEY),
    JSON.stringify([...completedResourceKeys.value]),
  )
}

function isResourceCompleted(resource) {
  const key = getResourceCompletionKey(resource)
  return Boolean(key) && completedResourceKeys.value.has(key)
}

function completeReadingResource() {
  const resource = readingResource.value
  const key = getResourceCompletionKey(
    resource,
    selectedDetail.value?.id || selectedNodeId.value,
  )

  if (key && !completedResourceKeys.value.has(key)) {
    completedResourceKeys.value = new Set([
      ...completedResourceKeys.value,
      key,
    ])
    saveCompletedResources()
    ElMessage.success('已标记为完成')
  }

  readingVisible.value = false
}

function nodeMatchesSearch(node) {
  const keyword = normalizeText(searchText.value)
  if (!keyword) return null
  return (
    normalizeText(node.name).includes(keyword) ||
    normalizeText(node.id).includes(keyword)
  )
}

function buildNodeData(nodes) {
  return nodes.map((node) => ({
    ...node,
    radius: getNodeRadius(node),
    color: getNodeColor(node),
    status: getNodeStatus(node),
    mastery: getMastery(node.id),
  }))
}

function buildTreeData(nodes, edges) {
  const nodeById = new Map(nodes.map((node) => [node.id, node]))
  const incoming = new Map(nodes.map((node) => [node.id, []]))
  const outgoing = new Map(nodes.map((node) => [node.id, []]))
  const visibleEdges = edges.filter(
    (edge) => nodeById.has(edge.from) && nodeById.has(edge.to),
  )

  visibleEdges.forEach((edge) => {
    incoming.get(edge.to).push(edge.from)
    outgoing.get(edge.from).push(edge.to)
  })

  const parentById = new Map()
  const visited = new Set()
  const rootIds = nodes
    .filter((node) => incoming.get(node.id).length === 0)
    .map((node) => node.id)

  if (!rootIds.length && nodes.length) {
    rootIds.push(nodes[0].id)
  }

  const queue = [...rootIds]
  rootIds.forEach((id) => visited.add(id))

  while (queue.length) {
    const parentId = queue.shift()
    outgoing.get(parentId).forEach((childId) => {
      if (visited.has(childId)) return
      visited.add(childId)
      parentById.set(childId, parentId)
      queue.push(childId)
    })
  }

  // Defensive fallback for malformed data: still render every visible node.
  nodes.forEach((node) => {
    if (!visited.has(node.id)) {
      visited.add(node.id)
      rootIds.push(node.id)
    }
  })

  const childrenById = new Map(nodes.map((node) => [node.id, []]))
  parentById.forEach((parentId, childId) => {
    childrenById.get(parentId).push(childId)
  })

  function buildBranch(nodeId, ancestors = new Set()) {
    if (ancestors.has(nodeId)) return null
    const nextAncestors = new Set(ancestors).add(nodeId)
    return {
      node: nodeById.get(nodeId),
      children: childrenById
        .get(nodeId)
        .map((childId) => buildBranch(childId, nextAncestors))
        .filter(Boolean),
    }
  }

  const treeRoots = rootIds
    .map((nodeId) => buildBranch(nodeId))
    .filter(Boolean)
  const treeLinks = visibleEdges.map((edge) => ({
    source: nodeById.get(edge.from),
    target: nodeById.get(edge.to),
    relation: edge.relation,
    isPrimary: parentById.get(edge.to) === edge.from,
  }))

  return {
    roots: treeRoots,
    links: treeLinks.filter((link) => link.isPrimary),
    dependencyLinks: treeLinks.filter((link) => !link.isPrimary),
  }
}

function layoutTreeForest(roots) {
  const treeLayout = d3
    .tree()
    .nodeSize([78, 210])
    .separation((left, right) =>
      left.parent === right.parent ? 1 : 1.28,
    )
  let verticalOffset = 0

  roots.forEach((treeRoot) => {
    const hierarchy = treeLayout(d3.hierarchy(treeRoot, (item) => item.children))
    const items = hierarchy.descendants()
    const minX = d3.min(items, (item) => item.x)
    const maxX = d3.max(items, (item) => item.x)

    items.forEach((item) => {
      item.data.node.x = item.y + 80
      item.data.node.y = item.x - minX + verticalOffset + 72
      item.data.node.depth = item.depth
    })

    verticalOffset += maxX - minX + 96
  })
}

function treeLinkPath(link) {
  const sourceX = link.source.x + link.source.radius + 4
  const sourceY = link.source.y
  const targetX = link.target.x - link.target.radius - 8
  const targetY = link.target.y
  const middleX = (sourceX + targetX) / 2

  return (
    `M${sourceX},${sourceY}` +
    `C${middleX},${sourceY} ${middleX},${targetY} ` +
    `${targetX},${targetY}`
  )
}

async function loadGraph() {
  loading.value = true
  loadError.value = false
  resourceCache.clear()
  let requestedNode = null
  try {
    const subject = learningContentStore.activeSubject
    const graph = await getKnowledgeGraph(subject)
    graphTitle.value = graph.title
    graphNodes.value = graph.nodes
    graphEdges.value = graph.edges
    categories.value = [
      '全部',
      ...new Set(graph.nodes.map((node) => node.category)),
    ]
    if (!categories.value.includes(activeCategory.value)) {
      activeCategory.value = '全部'
    }
    if (typeof route.query.kp === 'string') {
      requestedNode =
        graph.nodes.find((node) => node.id === route.query.kp) ||
        null
      if (requestedNode && requestedNode.category !== activeCategory.value) {
        activeCategory.value = requestedNode.category
      }
    }

    if (!userStore.profile?.id) {
      await userStore.fetchProfile()
    }
    if (userStore.profile?.id) {
      try {
        const progress = await getLearningProgress(subject)
        masteryById.value = Object.fromEntries(
          progress.points.map((point) => [
            point.knowledge_point_id,
            point.mastery,
          ]),
        )
      } catch {
        masteryById.value = {}
      }
    }
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
    await nextTick()
    renderGraph()
    if (requestedNode) {
      await nextTick()
      await selectNode(requestedNode)
    }
  }
}

function scheduleFitGraph(delay = 0) {
  window.clearTimeout(fitTimer)
  window.cancelAnimationFrame(fitFrame)

  if (delay > 0) {
    fitTimer = window.setTimeout(() => {
      fitGraphToViewport(180)
    }, delay)
    return
  }

  fitFrame = window.requestAnimationFrame(() => {
    fitGraphToViewport(180)
  })
}

function fitGraphToViewport(duration = 180) {
  if (!svgSelection || !zoomBehavior || !nodeSelection) return

  let minX = Number.POSITIVE_INFINITY
  let maxX = Number.NEGATIVE_INFINITY
  let minY = Number.POSITIVE_INFINITY
  let maxY = Number.NEGATIVE_INFINITY

  nodeSelection.each((node) => {
    if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) return
    const labelHalfWidth = Math.min(92, node.name.length * 5.2)
    minX = Math.min(minX, node.x - Math.max(node.radius, labelHalfWidth))
    maxX = Math.max(maxX, node.x + Math.max(node.radius, labelHalfWidth))
    minY = Math.min(minY, node.y - node.radius)
    maxY = Math.max(maxY, node.y + node.radius + 28)
  })

  if (!Number.isFinite(minX) || maxX <= minX || maxY <= minY) return

  const padding = 58
  const contentWidth = maxX - minX
  const contentHeight = maxY - minY
  const scale = Math.max(
    0.15,
    Math.min(
      1.12,
      (graphWidth - padding * 2) / contentWidth,
      (graphHeight - padding * 2) / contentHeight,
    ),
  )
  const offsetX =
    graphWidth / 2 - scale * ((minX + maxX) / 2)
  const offsetY =
    graphHeight / 2 - scale * ((minY + maxY) / 2)
  const transform = d3.zoomIdentity
    .translate(offsetX, offsetY)
    .scale(scale)

  if (duration > 0) {
    svgSelection
      .transition()
      .duration(duration)
      .call(zoomBehavior.transform, transform)
  } else {
    svgSelection.call(zoomBehavior.transform, transform)
  }
}

function updateGraphSize() {
  const container = graphContainer.value
  if (!container) return
  const rect = container.getBoundingClientRect()
  graphWidth = Math.max(320, rect.width)
  graphHeight = Math.max(480, rect.height)

  if (!svgSelection) return
  svgSelection.attr('viewBox', [0, 0, graphWidth, graphHeight])
  scheduleFitGraph(80)
}

function renderGraph() {
  const svgElement = svgRef.value
  const container = graphContainer.value
  if (!svgElement || !container) return

  const rect = container.getBoundingClientRect()
  graphWidth = Math.max(320, rect.width)
  graphHeight = Math.max(480, rect.height)
  svgSelection = d3.select(svgElement)
  svgSelection.selectAll('*').remove()
  svgSelection.attr('viewBox', [0, 0, graphWidth, graphHeight])

  if (!filteredNodes.value.length) {
    nodeSelection = null
    linkSelection = null
    dependencyLinkSelection = null
    viewportSelection = null
    return
  }

  const nodes = buildNodeData(filteredNodes.value)
  const treeData = buildTreeData(nodes, filteredEdges.value)
  layoutTreeForest(treeData.roots)

  const defs = svgSelection.append('defs')
  defs
    .append('marker')
    .attr('id', 'knowledge-arrow')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 8)
    .attr('refY', 0)
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-5L10,0L0,5')
    .attr('fill', 'var(--app-muted)')
    .attr('opacity', 0.55)

  zoomBehavior = d3
    .zoom()
    .scaleExtent([0.15, 3.2])
    .on('zoom', (event) => {
      currentZoomScale = event.transform.k
      viewportSelection?.attr('transform', event.transform)
      updateLabelVisibility()
    })
  svgSelection.call(zoomBehavior)
  currentZoomScale = 1

  viewportSelection = svgSelection.append('g')

  dependencyLinkSelection = viewportSelection
    .append('g')
    .selectAll('path')
    .data(treeData.dependencyLinks)
    .join('path')
    .attr('class', 'kg-link kg-dependency-link')
    .attr('d', treeLinkPath)
    .attr('fill', 'none')
    .attr('stroke', 'currentColor')
    .attr('stroke-width', 1)
    .attr('stroke-dasharray', '5 5')
    .attr('stroke-opacity', 0.32)
    .attr('marker-end', 'url(#knowledge-arrow)')

  linkSelection = viewportSelection
    .append('g')
    .selectAll('path')
    .data(treeData.links)
    .join('path')
    .attr('class', 'kg-link kg-tree-link')
    .attr('d', treeLinkPath)
    .attr('fill', 'none')
    .attr('stroke', 'currentColor')
    .attr('stroke-width', 1.4)
    .attr('stroke-opacity', 0.48)
    .attr('marker-end', 'url(#knowledge-arrow)')

  nodeSelection = viewportSelection
    .append('g')
    .selectAll('g')
    .data(nodes)
    .join('g')
    .attr('class', 'kg-node')
    .style('cursor', 'pointer')
    .on('mouseenter', showTooltip)
    .on('mousemove', moveTooltip)
    .on('mouseleave', hideTooltip)
    .on('click', (event, node) => {
      if (node.wasDragged) return
      event.stopPropagation()
      selectNode(node)
    })
    .call(
      d3
        .drag()
        .on('start', dragStarted)
        .on('drag', dragged)
        .on('end', dragEnded),
    )

  nodeSelection
    .append('circle')
    .attr('class', 'kg-node-ring')
    .attr('r', (node) => node.radius + 5)
    .attr('fill', 'none')
    .attr('stroke', '#246BFE')
    .attr('stroke-width', 0)
    .attr('opacity', 0)

  nodeSelection
    .append('circle')
    .attr('class', 'kg-node-circle')
    .attr('r', (node) => node.radius)
    .attr('fill', (node) => node.color)
    .attr('fill-opacity', 0.9)
    .attr('stroke', 'var(--app-surface)')
    .attr('stroke-width', 2.5)

  nodeSelection
    .append('text')
    .attr('class', 'kg-node-label')
    .attr('dy', (node) => node.radius + 15)
    .attr('text-anchor', 'middle')
    .attr('fill', 'var(--app-text)')
    .attr('font-size', 11)
    .attr('font-weight', 600)
    .attr('paint-order', 'stroke')
    .attr('stroke', 'var(--app-bg)')
    .attr('stroke-width', 4)
    .attr('stroke-linejoin', 'round')
    .text((node) => node.name)

  svgSelection.on('click', () => {
    selectedNodeId.value = ''
    selectedDetail.value = null
  })
  updateNodeAppearance()
  positionGraph()
  scheduleFitGraph(0)
}

function positionGraph() {
  linkSelection
    ?.attr('d', treeLinkPath)

  dependencyLinkSelection
    ?.attr('d', treeLinkPath)

  nodeSelection?.attr(
    'transform',
    (node) => `translate(${node.x},${node.y})`,
  )
}

function dragStarted(event, node) {
  node.wasDragged = false
}

function dragged(event, node) {
  if (Math.abs(event.dx) + Math.abs(event.dy) > 1) {
    node.wasDragged = true
  }
  node.x = event.x
  node.y = event.y
  positionGraph()
}

function dragEnded(event, node) {
  window.setTimeout(() => {
    node.wasDragged = false
  }, 120)
}

function pointerPosition(event) {
  const bounds = graphContainer.value?.getBoundingClientRect()
  if (!bounds) return { x: 0, y: 0 }
  return {
    x: Math.min(event.clientX - bounds.left + 14, bounds.width - 230),
    y: Math.min(event.clientY - bounds.top + 14, bounds.height - 120),
  }
}

function showTooltip(event, node) {
  const position = pointerPosition(event)
  tooltip.value = {
    visible: true,
    ...position,
    node,
  }
}

function moveTooltip(event) {
  if (!tooltip.value.visible) return
  tooltip.value = {
    ...tooltip.value,
    ...pointerPosition(event),
  }
}

function hideTooltip() {
  tooltip.value = {
    ...tooltip.value,
    visible: false,
  }
}

async function selectNode(node) {
  const requestId = ++resourceRequestId
  selectedNodeId.value = node.id
  detailLoading.value = true
  selectedDetail.value = null
  readingVisible.value = false
  readingResource.value = null
  updateNodeAppearance()
  loadNodeResources(node, requestId)
  try {
    selectedDetail.value = await getKnowledgePoint(node.id)
  } catch {
    selectedDetail.value = null
  } finally {
    detailLoading.value = false
    await nextTick()
    scheduleFitGraph(0)
  }
}

function closeDetail() {
  resourceRequestId += 1
  selectedNodeId.value = ''
  selectedDetail.value = null
  generatedResources.value = []
  resourceLoading.value = false
  resourceError.value = ''
  readingVisible.value = false
  readingResource.value = null
  updateNodeAppearance()
}

function buildFallbackResources(node) {
  return [
    {
      type: 'article',
      title: `${node.name}：核心概念速览`,
      url: `https://www.bing.com/search?q=${encodeURIComponent(
        `${graphTitle.value} ${node.name} 核心概念`,
      )}`,
      content:
        `## 核心定义\n${node.description}\n\n` +
        `## 它解决什么问题\n${node.name} 用于帮助学习者判断某类问题` +
        '应当如何描述、分析和处理。理解定义时应同时明确对象、目标' +
        '以及判断结果是否正确的方法。\n\n' +
        '## 适用范围\n检查使用前需要满足的条件，区分概念本身的定义' +
        '与某个具体实现方式。当输入、前提或目标变化时，先判断结论是否' +
        '仍然成立，再决定能否继续套用已有方法。',
    },
    {
      type: 'tutorial',
      title: `${node.name}：示例与应用场景`,
      url: `https://www.bing.com/search?q=${encodeURIComponent(
        `${graphTitle.value} ${node.name} 示例 教程`,
      )}`,
      content:
        `## 示例目标\n选择一个能够完整跟踪的最小案例来学习 ${node.name}。` +
        '示例开始前先写明已知条件、初始状态和希望得到的结果，' +
        '不要一开始就引入过多变量。\n\n' +
        '## 分步执行\n每一步只执行一个明确动作，并记录这一步使用了哪些信息、' +
        '产生了哪些变化。遇到判断时，写出判断依据而不是直接给出答案。' +
        '这样可以把最终结果与知识点中的规则逐项对应起来。\n\n' +
        '## 结果解释\n完成后重新检查示例，说明每个中间结果为什么出现，' +
        '以及最终结果是否满足最初目标。若结果与预期不同，' +
        '从第一个出现差异的步骤开始定位。',
    },
    {
      type: 'article',
      title: `${node.name}：关键原理与运行过程`,
      url: `https://www.bing.com/search?q=${encodeURIComponent(
        `${graphTitle.value} ${node.name} 原理 过程`,
      )}`,
      content:
        `## 前提条件\n理解 ${node.name} 时，先把问题拆成前提、过程和结果。` +
        '前提是方法能够成立的环境和输入约束；如果前提不满足，' +
        '即使操作步骤看起来相同，结果也可能失去意义。\n\n' +
        '## 运行过程\n按照时间或逻辑顺序列出关键步骤，并记录每一步' +
        '接收什么输入、执行什么处理、产生什么中间结果。' +
        '将中间结果与前一步连接起来，可以判断某个结论由哪条规则产生。\n\n' +
        '## 结果检查\n最后检查输出是否满足目标，并解释结果为什么合理。' +
        '如果只记住最终结果，却无法说明条件和过程，就难以迁移到新问题。',
    },
    {
      type: 'tutorial',
      title: `${node.name}：条件变化与举一反三`,
      url: `https://www.bing.com/search?q=${encodeURIComponent(
        `${graphTitle.value} ${node.name} 变式 边界`,
      )}`,
      content:
        `## 单一变量变化\n掌握基本示例后，每次只改变 ${node.name} 的` +
        '一个条件，例如输入内容、数量、顺序或边界值。变化前先根据原理' +
        '预测结果，执行后再比较预测与实际结果。\n\n' +
        '## 区分影响层次\n有些变化只改变结果数值，有些变化会改变处理步骤，' +
        '还有一些变化会直接破坏使用前提。学习时要能指出变化属于哪一类，' +
        '并说明判断依据。\n\n' +
        '## 形成迁移规律\n记录多次变化中稳定出现的规律，同时记录首次失效的条件。' +
        '稳定规律说明适用范围，失效条件划出知识边界，' +
        '二者共同构成可以迁移到新问题中的理解。',
    },
    {
      type: 'reference',
      title: `${node.name}：常见误区与纠偏`,
      url: `https://www.bing.com/search?q=${encodeURIComponent(
        `${graphTitle.value} ${node.name} 常见误区`,
      )}`,
      content:
        `## 常见错误类型\n学习 ${node.name} 时，常见问题包括只记结论` +
        '而说不清前提、混淆定义与具体实现、忽略边界条件，以及只会照搬示例。' +
        '这些错误的共同点是缺少对条件和过程的解释。\n\n' +
        '## 定位错误\n不要只说答案错了，而要指出错误首次出现的环节：' +
        '是前提判断错误、信息读取错误、步骤顺序错误，还是结果检查遗漏。' +
        '定位到具体环节后，才能选择正确的修正方法。\n\n' +
        '## 用反例纠偏\n构造一个不满足条件或结论相反的案例，' +
        '观察方法是否失效，并解释失效原因。能够正确说明反例，' +
        '通常比再做一道相似题更能证明已经理解知识边界。',
    },
    {
      type: 'reference',
      title: `${node.name}：练习与自检清单`,
      url: `https://www.bing.com/search?q=${encodeURIComponent(
        `${graphTitle.value} ${node.name} 练习 自检`,
      )}`,
      content:
        `## 知识复述\n合上资料后，用自己的话解释 ${node.name} 的定义、` +
        '作用、前提条件和一个具体例子。复述时不照抄原文，' +
        '重点检查这些内容之间是否形成完整逻辑。\n\n' +
        '## 独立练习\n先完成一个最小示例，再完成一个改变条件后的变式题。' +
        '答题过程中写出关键判断依据，结果出来后检查错误发生在哪一步。' +
        '如果卡住，只回到对应知识环节，而不是重新浏览全部内容。\n\n' +
        '## 自检标准\n能够说明是什么、为什么这样做、怎样判断结果正确，' +
        '并能指出一个不适用的情况，才算形成较完整的理解。' +
        '最后记录仍未解决的问题，作为下一次学习的起点。',
    },
  ]
}

async function loadNodeResources(node, requestId) {
  const cached = resourceCache.get(node.id)
  if (cached) {
    generatedResources.value = cached
    resourceLoading.value = false
    resourceError.value = ''
    return
  }

  generatedResources.value = []
  resourceLoading.value = true
  resourceError.value = ''
  try {
    const data = await generateKnowledgePointResources(node.id)
    const resources = data?.resources?.length
      ? data.resources
      : buildFallbackResources(node)
    resourceCache.set(node.id, resources)
    if (
      requestId !== resourceRequestId ||
      selectedNodeId.value !== node.id
    ) {
      return
    }
    generatedResources.value = resources
  } catch {
    const resources = buildFallbackResources(node)
    resourceCache.set(node.id, resources)
    if (
      requestId !== resourceRequestId ||
      selectedNodeId.value !== node.id
    ) {
      return
    }
    generatedResources.value = resources
    resourceError.value = '模型资源生成失败，已展示基础学习内容。'
  } finally {
    if (
      requestId === resourceRequestId &&
      selectedNodeId.value === node.id
    ) {
      resourceLoading.value = false
    }
  }
}

function openReadingResource(resource) {
  readingResource.value = resource
  readingVisible.value = true
}

function resourceTypeLabel(type) {
  return (
    {
      article: '文章',
      tutorial: '教程',
      reference: '参考',
      video: '视频',
    }[type] || '资料'
  )
}

function renderLearningContent(content) {
  if (!content) return ''
  const html = marked.parse(content, { async: false })
  return DOMPurify.sanitize(html)
}

function updateNodeAppearance() {
  if (!nodeSelection) return
  nodeSelection
    .classed('is-selected', (node) => node.id === selectedNodeId.value)
    .attr('opacity', (node) => {
      const match = nodeMatchesSearch(node)
      return match === false ? 0.18 : 1
    })
    .select('.kg-node-ring')
    .attr('opacity', (node) => {
      const match = nodeMatchesSearch(node)
      const selected = node.id === selectedNodeId.value
      return selected || match ? 1 : 0
    })
    .attr(
      'stroke-width',
      (node) =>
        node.id === selectedNodeId.value || nodeMatchesSearch(node)
          ? 2.5
          : 0,
    )

  nodeSelection
    .select('.kg-node-label')
    .attr('font-weight', (node) =>
      nodeMatchesSearch(node) || node.id === selectedNodeId.value
        ? 800
        : 600,
    )
  updateLabelVisibility()
}

function updateLabelVisibility() {
  if (!nodeSelection) return
  nodeSelection
    .select('.kg-node-label')
    .attr('opacity', (node) => {
      const matched = nodeMatchesSearch(node)
      if (
        node.id === selectedNodeId.value ||
        matched ||
        currentZoomScale >= 0.9 ||
        node.status !== 'locked'
      ) {
        return 1
      }
      return 0
    })
}

function resetZoom() {
  if (!svgSelection || !zoomBehavior) return
  svgSelection
    .transition()
    .duration(350)
    .call(
      zoomBehavior.transform,
      d3.zoomIdentity.translate(0, 0).scale(1),
    )
}

function statusLabel(node) {
  return STATUS_META[node.status]?.label || '未知'
}

watch(activeCategory, async () => {
  if (
    selectedNode.value &&
    activeFilter.value &&
    selectedNode.value.category !== activeFilter.value
  ) {
    closeDetail()
  }
  await nextTick()
  renderGraph()
})

watch(searchText, updateNodeAppearance)

watch(selectedNodeId, updateNodeAppearance)

watch(
  () => route.query.kp,
  async (kpId) => {
    if (typeof kpId !== 'string') return
    const node = graphNodes.value.find((item) => item.id === kpId)
    if (!node) return

    if (activeFilter.value && node.category !== activeFilter.value) {
      activeCategory.value = node.category
    }
    await nextTick()
    if (
      selectedNodeId.value === node.id &&
      selectedDetail.value?.id === node.id
    ) {
      return
    }
    await selectNode(node)
  },
)

watch(
  () => learningContentStore.activeSubject,
  () => loadGraph(),
)

onMounted(async () => {
  loadCompletedResources()
  resizeObserver = new ResizeObserver(() => updateGraphSize())
  if (graphContainer.value) {
    resizeObserver.observe(graphContainer.value)
  }
  await loadGraph()
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  svgSelection?.on('.zoom', null)
  window.clearTimeout(fitTimer)
  window.cancelAnimationFrame(fitFrame)
})
</script>

<template>
  <section class="knowledge-page">
    <header class="page-heading">
      <div>
        <p class="page-kicker">KNOWLEDGE GRAPH</p>
        <h1>知识图谱</h1>
        <span>
          当前学习内容：{{ graphTitle || learningContentStore.activeTitle }}。
          点击节点生成学习资源，再选择资源学习详细知识点。
        </span>
      </div>
      <el-button :icon="RefreshRight" @click="loadGraph">
        刷新图谱
      </el-button>
    </header>

    <section class="graph-shell">
      <div class="graph-toolbar">
        <el-radio-group v-model="activeCategory" size="small">
          <el-radio-button
            v-for="category in categories"
            :key="category"
            :value="category"
          >
            {{ category }}
          </el-radio-button>
        </el-radio-group>

        <el-input
          v-model="searchText"
          class="graph-search"
          :prefix-icon="Search"
          placeholder="搜索知识点"
          clearable
        />
      </div>

      <div
        class="graph-workspace"
        :class="{ 'has-detail': selectedNodeId }"
      >
        <div ref="graphContainer" class="graph-canvas">
          <svg ref="svgRef" class="knowledge-svg" role="img">
            <title>
              {{ graphTitle || learningContentStore.activeTitle }} 知识图谱
            </title>
          </svg>

          <div v-if="loading" class="graph-loading">
            <el-skeleton :rows="7" animated />
          </div>

          <div v-else-if="loadError" class="graph-state">
            <el-empty description="知识图谱加载失败" :image-size="82">
              <el-button @click="loadGraph">重新加载</el-button>
            </el-empty>
          </div>

          <div v-else-if="!filteredNodes.length" class="graph-state">
            <el-empty description="当前分类暂无知识点" :image-size="82" />
          </div>

          <div
            v-if="tooltip.visible && tooltip.node"
            class="node-tooltip"
            :style="{ left: `${tooltip.x}px`, top: `${tooltip.y}px` }"
          >
            <strong>{{ tooltip.node.name }}</strong>
            <span>{{ tooltip.node.category }}</span>
            <div>
              <i :style="{ background: tooltip.node.color }"></i>
              掌握度 {{ Math.round(tooltip.node.mastery * 100) }}%
              · {{ statusLabel(tooltip.node) }}
            </div>
          </div>

          <div class="graph-legend">
            <span
              v-for="item in Object.values(STATUS_META)"
              :key="item.label"
            >
              <i :style="{ background: item.color }"></i>
              {{ item.label }}
            </span>
          </div>

          <button
            class="reset-button"
            type="button"
            title="重置视图"
            aria-label="重置视图"
            @click="resetZoom"
          >
            <el-icon><RefreshRight /></el-icon>
          </button>
        </div>

        <transition name="detail-slide">
          <aside v-if="selectedNodeId" class="detail-panel">
            <header class="detail-header">
              <div>
                <span class="detail-kicker">KNOWLEDGE DETAIL</span>
                <h2>
                  {{ selectedDetail?.name || selectedNode?.name }}
                </h2>
              </div>
              <el-button
                text
                circle
                :icon="Close"
                aria-label="关闭详情"
                @click="closeDetail"
              />
            </header>

            <el-skeleton v-if="detailLoading" :rows="7" animated />

            <template v-else-if="selectedDetail">
              <div class="detail-tags">
                <el-tag effect="plain">{{ selectedDetail.category }}</el-tag>
                <el-tag type="info" effect="plain">
                  难度 {{ selectedDetail.difficulty }}
                </el-tag>
                <el-tag
                  :type="
                    selectedMasteryPercent >= 80
                      ? 'success'
                      : selectedMasteryPercent >= 30
                        ? 'warning'
                        : 'danger'
                  "
                  effect="light"
                >
                  掌握 {{ selectedMasteryPercent }}%
                </el-tag>
              </div>

              <p class="detail-description">
                {{ selectedDetail.description }}
              </p>

              <section class="detail-section">
                <h3>前置知识点</h3>
                <div
                  v-if="selectedDetail.prerequisites.length"
                  class="prerequisite-list"
                >
                  <div
                    v-for="point in selectedDetail.prerequisites"
                    :key="point.id"
                    class="prerequisite-row"
                  >
                    <div>
                      <strong>{{ point.name }}</strong>
                      <span>{{ point.category }}</span>
                    </div>
                    <div class="prerequisite-progress">
                      <el-progress
                        :percentage="Math.round(getMastery(point.id) * 100)"
                        :stroke-width="5"
                        :show-text="false"
                        :color="
                          getMastery(point.id) >= 0.7
                            ? '#149A76'
                            : '#D9831A'
                        "
                      />
                      <small>
                        {{ Math.round(getMastery(point.id) * 100) }}%
                      </small>
                    </div>
                  </div>
                </div>
                <p v-else class="empty-copy">这是当前知识体系的起点。</p>
              </section>

              <section class="detail-section">
                <div class="resource-heading">
                  <h3>学习资源</h3>
                  <span>
                    {{
                      resourceLoading
                        ? '正在生成'
                        : `已完成 ${completedResourceCount} / ${generatedResources.length}`
                    }}
                  </span>
                </div>
                <div
                  v-if="resourceLoading"
                  class="resource-loading"
                >
                  <p>正在为该知识点生成详细学习内容...</p>
                  <el-skeleton :rows="4" animated />
                </div>
                <div
                  v-else-if="generatedResources.length"
                  class="resource-list"
                >
                  <button
                    v-for="resource in generatedResources"
                    :key="resource.title"
                    type="button"
                    class="resource-row"
                    :class="{
                      'is-completed': isResourceCompleted(resource),
                    }"
                    @click="openReadingResource(resource)"
                  >
                    <span class="resource-copy">
                      <span class="resource-type">
                        {{ resourceTypeLabel(resource.type) }}
                      </span>
                      <strong>{{ resource.title }}</strong>
                      <span class="resource-hint">
                        {{
                          isResourceCompleted(resource)
                            ? '已完成学习 · 可再次阅读'
                            : '详细学习内容 · 点击阅读'
                        }}
                      </span>
                    </span>
                    <span
                      v-if="isResourceCompleted(resource)"
                      class="resource-complete"
                    >
                      <el-icon><Check /></el-icon>
                      已完成
                    </span>
                    <el-icon v-else class="resource-arrow">
                      <ArrowRight />
                    </el-icon>
                  </button>
                </div>
                <p v-else class="empty-copy">暂无学习资源。</p>
                <p v-if="resourceError" class="resource-error">
                  {{ resourceError }}
                </p>
              </section>

              <el-button
                type="primary"
                class="practice-button"
                @click="
                  router.push({
                    path: '/practice',
                    query: { kp: selectedDetail.id },
                  })
                "
              >
                开始练习
              </el-button>
            </template>
          </aside>
        </transition>
      </div>
    </section>

    <el-drawer
      v-model="readingVisible"
      class="reading-drawer"
      size="min(760px, 96vw)"
      append-to-body
    >
      <template #header>
        <div class="reading-header">
          <span class="detail-kicker">LEARNING RESOURCE</span>
          <h2>{{ readingResource?.title }}</h2>
        </div>
      </template>

      <div v-if="readingResource" class="reading-content">
        <div class="detail-tags">
          <el-tag effect="plain">
            {{ resourceTypeLabel(readingResource.type) }}
          </el-tag>
          <el-tag type="info" effect="plain">
            {{ selectedDetail?.name }}
          </el-tag>
        </div>

        <article
          class="reading-article"
          v-html="renderLearningContent(readingResource.content)"
        ></article>

        <div class="reading-actions">
          <el-button
            type="primary"
            @click="completeReadingResource"
          >
            完成学习
          </el-button>
        </div>
      </div>
    </el-drawer>
  </section>
</template>

<style scoped>
.knowledge-page {
  display: flex;
  flex-direction: column;
}

.graph-shell {
  overflow: hidden;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
}

.graph-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--app-border);
}

.graph-toolbar :deep(.el-radio-group) {
  display: flex;
  flex-wrap: wrap;
}

.graph-search {
  width: min(280px, 100%);
  flex: none;
}

.graph-workspace {
  position: relative;
  display: grid;
  min-height: 680px;
  grid-template-columns: minmax(0, 1fr);
  transition: grid-template-columns 0.25s ease;
}

.graph-workspace.has-detail {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
}

.graph-canvas {
  position: relative;
  min-width: 0;
  height: 680px;
  overflow: hidden;
  background:
    radial-gradient(circle at center, rgba(36, 107, 254, 0.045), transparent 52%),
    var(--app-bg);
}

.knowledge-svg {
  display: block;
  width: 100%;
  height: 100%;
  color: var(--app-muted);
  touch-action: none;
}

.graph-canvas :deep(.kg-link) {
  color: var(--app-muted);
}

.graph-canvas :deep(.kg-dependency-link) {
  color: var(--app-border-strong);
}

.graph-canvas :deep(.kg-node:hover .kg-node-circle) {
  stroke: #246BFE;
  stroke-width: 4;
}

.graph-canvas :deep(.kg-node.is-selected .kg-node-circle) {
  stroke: #246BFE;
  stroke-width: 4;
}

.graph-canvas :deep(.kg-node-label) {
  pointer-events: none;
  user-select: none;
}

.graph-loading {
  position: absolute;
  inset: 0;
  padding: 90px 48px;
  background: var(--app-bg);
}

.graph-state {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
}

.node-tooltip {
  position: absolute;
  z-index: 8;
  display: flex;
  width: 220px;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  color: var(--app-text);
  background: var(--app-surface);
  box-shadow: 0 8px 26px rgba(10, 32, 47, 0.14);
  pointer-events: none;
}

.node-tooltip strong {
  font-size: 13px;
}

.node-tooltip > span {
  color: #246BFE;
  font-size: 11px;
}

.node-tooltip > div {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--app-muted);
  font-size: 11px;
}

.node-tooltip i,
.graph-legend i {
  display: inline-block;
  width: 8px;
  height: 8px;
  flex: 0 0 8px;
  border-radius: 50%;
}

.graph-legend {
  position: absolute;
  bottom: 14px;
  left: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 8px 10px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  color: var(--app-muted);
  background: color-mix(in srgb, var(--app-surface) 92%, transparent);
  font-size: 10px;
  backdrop-filter: blur(6px);
}

.graph-legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.reset-button {
  position: absolute;
  top: 14px;
  right: 14px;
  display: grid;
  width: 36px;
  height: 36px;
  place-items: center;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  color: var(--app-muted);
  background: var(--app-surface);
  cursor: pointer;
}

.reset-button:hover {
  border-color: #246BFE;
  color: #246BFE;
}

.detail-panel {
  min-width: 0;
  height: 680px;
  padding: 20px;
  overflow-y: auto;
  border-left: 1px solid var(--app-border);
  background: var(--app-surface);
}

.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.detail-kicker {
  color: #246BFE;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.detail-header h2 {
  margin: 6px 0 0;
  color: var(--app-text);
  font-size: 21px;
  line-height: 1.35;
}

.detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 16px;
}

.detail-description {
  margin: 18px 0;
  color: var(--app-muted);
  font-size: 13px;
  line-height: 1.75;
}

.detail-section {
  margin-top: 22px;
}

.detail-section h3 {
  margin: 0 0 12px;
  color: var(--app-text);
  font-size: 13px;
}

.prerequisite-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.prerequisite-row {
  padding: 10px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface-muted);
}

.prerequisite-row > div:first-child {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.prerequisite-row strong {
  color: var(--app-text);
  font-size: 12px;
}

.prerequisite-row span {
  color: var(--app-muted);
  font-size: 10px;
}

.prerequisite-progress {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 34px;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.prerequisite-progress small {
  color: var(--app-muted);
  font-size: 10px;
  text-align: right;
}

.resource-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.resource-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.resource-heading h3 {
  margin: 0;
}

.resource-heading > span {
  color: #246BFE;
  font-size: 10px;
  font-weight: 700;
}

.resource-loading {
  padding: 10px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface-muted);
}

.resource-loading > p {
  margin: 0 0 12px;
  color: var(--app-muted);
  font-size: 11px;
}

.resource-row {
  display: grid;
  width: 100%;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  color: var(--app-text);
  text-align: left;
  background: var(--app-surface-muted);
  cursor: pointer;
}

.resource-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
}

.resource-type {
  width: fit-content;
  padding: 1px 6px;
  border-radius: 4px;
  color: #246BFE;
  background: color-mix(in srgb, #246BFE 10%, transparent);
  font-size: 9px;
  font-weight: 700;
}

.resource-copy strong {
  font-size: 12px;
  line-height: 1.45;
}

.resource-hint {
  color: var(--app-muted);
  font-size: 10px;
  line-height: 1.5;
}

.resource-row > .el-icon {
  color: #246BFE;
}

.resource-row:hover {
  border-color: #246BFE;
}

.resource-row.is-completed {
  border-color: color-mix(in srgb, #149A76 42%, var(--app-border));
  background: color-mix(in srgb, #149A76 5%, var(--app-surface-muted));
}

.resource-complete {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #149A76;
  font-size: 10px;
  font-weight: 700;
  white-space: nowrap;
}

.resource-arrow {
  color: #246BFE;
}

.resource-error {
  margin: 8px 0 0;
  color: var(--app-muted);
  font-size: 10px;
  line-height: 1.5;
}

.empty-copy {
  margin: 0;
  color: var(--app-muted);
  font-size: 12px;
}

.practice-button {
  width: 100%;
  height: 42px;
  margin-top: 24px;
}

.reading-header {
  min-width: 0;
}

.reading-header h2 {
  margin: 6px 0 0;
  color: var(--app-text);
  font-size: 20px;
  line-height: 1.4;
}

.reading-content {
  color: var(--app-text);
}

.reading-article {
  margin-top: 22px;
  color: var(--app-text);
  font-size: 14px;
  line-height: 1.9;
}

.reading-article :deep(h1),
.reading-article :deep(h2) {
  margin: 30px 0 12px;
  color: var(--app-text);
  font-size: 18px;
  line-height: 1.5;
}

.reading-article :deep(h1:first-child),
.reading-article :deep(h2:first-child) {
  margin-top: 0;
}

.reading-article :deep(h3) {
  margin: 24px 0 10px;
  color: var(--app-text);
  font-size: 15px;
  line-height: 1.5;
}

.reading-article :deep(p),
.reading-article :deep(li) {
  color: var(--app-muted);
  font-size: 14px;
  line-height: 1.9;
}

.reading-article :deep(p) {
  margin: 0 0 14px;
}

.reading-article :deep(ul),
.reading-article :deep(ol) {
  margin: 0 0 16px;
  padding-left: 20px;
}

.reading-article :deep(li + li) {
  margin-top: 7px;
}

.reading-article :deep(strong) {
  color: var(--app-text);
}

.reading-article :deep(blockquote) {
  margin: 18px 0;
  padding: 10px 14px;
  border-left: 3px solid #246BFE;
  color: var(--app-muted);
  background: var(--app-surface-muted);
}

.reading-article :deep(code) {
  padding: 2px 5px;
  border-radius: 4px;
  background: var(--app-surface-muted);
  font-size: 12px;
}

.reading-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 14px;
  margin-top: 32px;
  padding-top: 18px;
  border-top: 1px solid var(--app-border);
}

.detail-slide-enter-active,
.detail-slide-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.detail-slide-enter-from,
.detail-slide-leave-to {
  opacity: 0;
  transform: translateX(18px);
}

@media (max-width: 1180px) {
  .graph-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .graph-search {
    width: 100%;
  }

  .graph-workspace.has-detail {
    grid-template-columns: minmax(0, 1fr);
  }

  .detail-panel {
    position: absolute;
    inset: 0 0 0 auto;
    z-index: 10;
    width: min(380px, 92%);
    box-shadow: -8px 0 30px rgba(10, 32, 47, 0.14);
  }
}

@media (max-width: 700px) {
  .graph-workspace,
  .graph-canvas,
  .detail-panel {
    height: 560px;
    min-height: 560px;
  }

  .graph-legend {
    right: 14px;
    left: 14px;
  }

  .graph-toolbar {
    padding: 12px;
  }

  .graph-toolbar :deep(.el-radio-button__inner) {
    padding: 7px 9px;
    font-size: 11px;
  }
}
</style>
