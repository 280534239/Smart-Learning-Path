<script setup>
import {
  Close,
  Delete,
  Promotion,
  Rank,
} from '@element-plus/icons-vue'
import DOMPurify from 'dompurify'
import { ElMessage } from 'element-plus'
import hljs from 'highlight.js/lib/core'
import bash from 'highlight.js/lib/languages/bash'
import css from 'highlight.js/lib/languages/css'
import javascript from 'highlight.js/lib/languages/javascript'
import json from 'highlight.js/lib/languages/json'
import python from 'highlight.js/lib/languages/python'
import sql from 'highlight.js/lib/languages/sql'
import typescript from 'highlight.js/lib/languages/typescript'
import xml from 'highlight.js/lib/languages/xml'
import 'highlight.js/styles/github-dark.css'
import { marked } from 'marked'
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch,
} from 'vue'
import { useRoute } from 'vue-router'

import { streamAssistantQuestion } from '../api/assistant'
import {
  LEARNING_CONTENT_DELETED_EVENT,
  useLearningContentStore,
} from '../stores/learningContent'
import { useUserStore } from '../stores/user'
import { getUserScopedStorageKey } from '../utils/userStorage'
import AssistantPet from './AssistantPet.vue'

const CONVERSATION_STORAGE_KEY =
  'slp_floating_assistant_history_v1'
const PET_POSITION_STORAGE_KEY = 'slp_assistant_pet_position_v2'
const PANEL_POSITION_STORAGE_KEY = 'slp_assistant_panel_position_v2'
const PET_GAP = 14
const VIEWPORT_MARGIN = 8
const WELCOME_MESSAGE = {
  id: 'welcome',
  role: 'assistant',
  content: '你好，我是智学小助手。有什么学习问题，可以直接问我。',
  error: false,
}

hljs.registerLanguage('python', python)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('json', json)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('css', css)

marked.setOptions({
  gfm: true,
  breaks: true,
})

const route = useRoute()
const userStore = useUserStore()
const learningContentStore = useLearningContentStore()

const open = ref(false)
const draft = ref('')
const streaming = ref(false)
const unread = ref(false)
const modelName = ref('deepseek-chat')
const activeConversationSubject = ref(
  learningContentStore.activeSubject || '',
)
const conversationThreads = ref(
  loadConversationThreads(activeConversationSubject.value),
)
const messages = ref(
  loadMessagesForSubject(activeConversationSubject.value),
)
const messageListRef = ref(null)
const inputRef = ref(null)
const petElement = ref(null)
const panelElement = ref(null)
const dragging = ref('')
const suppressPetClick = ref(false)
const panelHasPosition = ref(false)
const panelSize = ref({ width: 404, height: 620 })
const discardedConversationSubjects = new Set()

const storedPetPosition = loadStoredPosition(PET_POSITION_STORAGE_KEY)
const storedPanelPosition = loadStoredPosition(
  PANEL_POSITION_STORAGE_KEY,
)
const petPosition = ref(
  storedPetPosition || getDefaultPetPosition(),
)
const panelPosition = ref(storedPanelPosition || { x: 0, y: 0 })
panelHasPosition.value = Boolean(storedPanelPosition)

let requestController
let requestSequence = 0
let dragSession
let resizeFrame

const pageTitle = computed(() => route.meta.title || '学习页面')
const activeTitle = computed(
  () => learningContentStore.activeTitle || '当前学习内容',
)
const canSend = computed(
  () => Boolean(draft.value.trim()) && !streaming.value,
)
const hasConversation = computed(() =>
  messages.value.some((message) => message.role === 'user'),
)
const isLatestAssistantTyping = computed(() => {
  const lastMessage = messages.value[messages.value.length - 1]
  return (
    streaming.value &&
    lastMessage?.role === 'assistant' &&
    !lastMessage.error
  )
})
const quickPrompts = computed(() => [
  `${activeTitle.value}该怎么学？`,
  '解释一下当前知识点的核心概念',
  '给我一个由浅入深的例子',
])
const petHintBelow = computed(() => petPosition.value.y < 86)
const petHintOnRight = computed(() => petPosition.value.x < 150)
const panelTailClass = computed(() => {
  const petCenterX =
    petPosition.value.x + (petElement.value?.offsetWidth || 112) / 2
  const panelCenterX =
    panelPosition.value.x + panelSize.value.width / 2
  return petCenterX < panelCenterX ? 'tail-left' : 'tail-right'
})
const panelTailStyle = computed(() => {
  const petCenterY =
    petPosition.value.y + (petElement.value?.offsetHeight || 116) / 2
  const tailTop = clamp(
    petCenterY - panelPosition.value.y,
    72,
    Math.max(72, panelSize.value.height - 32),
  )
  return { '--tail-top': `${tailTop}px` }
})
const petPositionStyle = computed(() => ({
  left: `${petPosition.value.x}px`,
  top: `${petPosition.value.y}px`,
}))
const panelPositionStyle = computed(() => ({
  left: `${panelPosition.value.x}px`,
  top: `${panelPosition.value.y}px`,
}))

watch(open, async (isOpen) => {
  if (!isOpen) {
    saveStoredPosition(
      PET_POSITION_STORAGE_KEY,
      petPosition.value,
    )
    return
  }
  unread.value = false
  await nextTick()
  measurePanel()
  if (panelHasPosition.value) {
    panelPosition.value = clampPosition(
      panelPosition.value,
      panelSize.value.width,
      panelSize.value.height,
    )
  } else {
    positionPanelNearPet()
    panelHasPosition.value = true
  }
  scrollToBottom()
  highlightCodeBlocks()
  inputRef.value?.focus()
})

watch(
  () => learningContentStore.activeSubject,
  async (subject) => {
    const nextSubject = subject || ''
    if (nextSubject === activeConversationSubject.value) return

    requestSequence += 1
    requestController?.abort()
    requestController = undefined
    streaming.value = false
    const previousSubject = activeConversationSubject.value
    if (discardedConversationSubjects.delete(previousSubject)) {
      delete conversationThreads.value[previousSubject]
    } else {
      saveMessages(previousSubject)
    }

    activeConversationSubject.value = nextSubject
    messages.value = loadMessagesForSubject(nextSubject)
    draft.value = ''
    modelName.value = 'deepseek-chat'
    unread.value = false

    await nextTick()
    scrollToBottom()
    highlightCodeBlocks()
    if (open.value) inputRef.value?.focus()
  },
)

onMounted(async () => {
  window.addEventListener('keydown', handleGlobalKeydown)
  window.addEventListener('pointerdown', handleOutsidePointerDown)
  window.addEventListener('resize', handleViewportResize)
  window.addEventListener(
    LEARNING_CONTENT_DELETED_EVENT,
    handleLearningContentDeleted,
  )
  await nextTick()
  syncPositionsToViewport()
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleGlobalKeydown)
  window.removeEventListener('pointerdown', handleOutsidePointerDown)
  window.removeEventListener('resize', handleViewportResize)
  window.removeEventListener(
    LEARNING_CONTENT_DELETED_EVENT,
    handleLearningContentDeleted,
  )
  stopDraggingListeners()
  if (resizeFrame) window.cancelAnimationFrame(resizeFrame)
  requestSequence += 1
  requestController?.abort()
})

function handleLearningContentDeleted(event) {
  const subject = event.detail?.subject
  if (!subject) return

  discardedConversationSubjects.add(subject)
  delete conversationThreads.value[subject]
  saveConversationThreads(conversationThreads.value)
  if (activeConversationSubject.value === subject) {
    requestSequence += 1
    requestController?.abort()
    requestController = undefined
    streaming.value = false
  }
}

function normalizeConversationMessages(value) {
  if (!Array.isArray(value)) return []
  return value
    .filter(
      (message) =>
        message &&
        ['user', 'assistant'].includes(message.role) &&
        typeof message.content === 'string',
    )
    .map((message, index) => ({
      id: String(message.id || `${message.role}-${index}`),
      role: message.role,
      content: message.content,
      error: Boolean(message.error),
    }))
    .slice(-30)
}

function loadConversationThreads(currentSubject) {
  const threads = {}
  try {
    const saved = JSON.parse(
      localStorage.getItem(
        getUserScopedStorageKey(CONVERSATION_STORAGE_KEY),
      ) || 'null',
    )
    if (saved?.version === 1 && saved.threads) {
      for (const [subject, thread] of Object.entries(saved.threads)) {
        const savedMessages = normalizeConversationMessages(
          thread?.messages,
        )
        if (!savedMessages.length) continue
        threads[subject] = {
          messages: savedMessages,
          updatedAt: Number(thread?.updatedAt) || 0,
        }
      }
      return threads
    }
  } catch {
    // 损坏的分内容记录回退到欢迎语。
  }
  return threads
}

function saveConversationThreads(threads) {
  try {
    localStorage.setItem(
      getUserScopedStorageKey(CONVERSATION_STORAGE_KEY),
      JSON.stringify({
        version: 1,
        threads,
      }),
    )
  } catch {
    // 本地存储不可用时仍保留当前内存中的对话。
  }
}

function loadMessagesForSubject(subject) {
  const savedMessages = normalizeConversationMessages(
    conversationThreads.value?.[subject]?.messages,
  )
  if (savedMessages.length) return savedMessages
  return [{ ...WELCOME_MESSAGE }]
}

function saveMessages(
  subject = activeConversationSubject.value,
  sourceMessages = messages.value,
) {
  if (!subject) return
  const snapshot = normalizeConversationMessages(sourceMessages)
    .filter((message) => message.content.trim())
  conversationThreads.value = {
    ...conversationThreads.value,
    [subject]: {
      messages: snapshot,
      updatedAt: Date.now(),
    },
  }
  saveConversationThreads(conversationThreads.value)
}

function getDefaultPetPosition() {
  return {
    x: Math.max(
      VIEWPORT_MARGIN,
      window.innerWidth - 112 - 24,
    ),
    y: Math.max(
      VIEWPORT_MARGIN,
      window.innerHeight - 116 - 24,
    ),
  }
}

function loadStoredPosition(key) {
  try {
    const position = JSON.parse(
      localStorage.getItem(getUserScopedStorageKey(key)) || 'null',
    )
    if (
      position &&
      Number.isFinite(position.x) &&
      Number.isFinite(position.y)
    ) {
      return { x: position.x, y: position.y }
    }
  } catch {
    // 无效位置使用页面默认位置。
  }
  return null
}

function saveStoredPosition(key, position) {
  localStorage.setItem(
    getUserScopedStorageKey(key),
    JSON.stringify(position),
  )
}

function clamp(value, minimum, maximum) {
  const safeMaximum = Math.max(minimum, maximum)
  return Math.min(Math.max(value, minimum), safeMaximum)
}

function clampPosition(
  position,
  width,
  height,
  margin = VIEWPORT_MARGIN,
) {
  return {
    x: clamp(
      Math.round(position.x),
      margin,
      window.innerWidth - width - margin,
    ),
    y: clamp(
      Math.round(position.y),
      margin,
      window.innerHeight - height - margin,
    ),
  }
}

function measurePanel() {
  if (!panelElement.value) return
  panelSize.value = {
    width: panelElement.value.offsetWidth,
    height: panelElement.value.offsetHeight,
  }
}

function syncPositionsToViewport() {
  const petWidth = petElement.value?.offsetWidth || 112
  const petHeight = petElement.value?.offsetHeight || 116
  petPosition.value = clampPosition(
    petPosition.value,
    petWidth,
    petHeight,
  )
  saveStoredPosition(PET_POSITION_STORAGE_KEY, petPosition.value)

  if (!open.value) return
  measurePanel()
  panelPosition.value = clampPosition(
    panelPosition.value,
    panelSize.value.width,
    panelSize.value.height,
  )
  saveStoredPosition(
    PANEL_POSITION_STORAGE_KEY,
    panelPosition.value,
  )
}

function positionPanelNearPet() {
  const petRect = petElement.value?.getBoundingClientRect()
  if (!petRect) return

  const gap = PET_GAP
  let x
  if (window.innerWidth <= 640) {
    x = (window.innerWidth - panelSize.value.width) / 2
  } else if (petRect.left < window.innerWidth / 2) {
    x = petRect.right + gap
  } else {
    x = petRect.left - panelSize.value.width - gap
  }
  const y =
    petRect.top - panelSize.value.height + petRect.height * 0.62
  panelPosition.value = clampPosition(
    { x, y },
    panelSize.value.width,
    panelSize.value.height,
  )
  saveStoredPosition(
    PANEL_POSITION_STORAGE_KEY,
    panelPosition.value,
  )
}

function handleViewportResize() {
  if (resizeFrame) window.cancelAnimationFrame(resizeFrame)
  resizeFrame = window.requestAnimationFrame(() => {
    resizeFrame = undefined
    syncPositionsToViewport()
  })
}

function startPetDrag(event) {
  if (event.button !== 0) return
  beginDrag('pet', event)
}

function startPanelDrag(event) {
  if (event.button !== 0) return
  if (event.target.closest?.('button, input, textarea, a')) return
  event.preventDefault()
  beginDrag('panel', event)
}

function beginDrag(kind, event) {
  dragSession = {
    kind,
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    originX: kind === 'pet'
      ? petPosition.value.x
      : panelPosition.value.x,
    originY: kind === 'pet'
      ? petPosition.value.y
      : panelPosition.value.y,
    panelOriginX: panelPosition.value.x,
    panelOriginY: panelPosition.value.y,
    captureTarget: event.currentTarget,
    moved: false,
  }
  dragging.value = kind
  document.body.classList.add('assistant-is-dragging')
  try {
    dragSession.captureTarget?.setPointerCapture?.(event.pointerId)
  } catch {
    // 部分移动浏览器不支持指针捕获，窗口级监听仍可完成拖动。
  }
  window.addEventListener('pointermove', handleDragMove, {
    passive: false,
  })
  window.addEventListener('pointerup', handleDragEnd)
  window.addEventListener('pointercancel', handleDragEnd)
}

function handleDragMove(event) {
  if (!dragSession || event.pointerId !== dragSession.pointerId) {
    return
  }
  const deltaX = event.clientX - dragSession.startX
  const deltaY = event.clientY - dragSession.startY
  if (
    !dragSession.moved &&
    Math.hypot(deltaX, deltaY) < 4
  ) {
    return
  }

  dragSession.moved = true
  event.preventDefault()
  if (dragSession.kind === 'pet') {
    petPosition.value = clampPosition(
      {
        x: dragSession.originX + deltaX,
        y: dragSession.originY + deltaY,
      },
      petElement.value?.offsetWidth || 112,
      petElement.value?.offsetHeight || 116,
    )
    if (open.value && panelHasPosition.value) {
      panelPosition.value = clampPosition(
        {
          x: dragSession.panelOriginX + deltaX,
          y: dragSession.panelOriginY + deltaY,
        },
        panelSize.value.width,
        panelSize.value.height,
      )
    }
    return
  }

  panelPosition.value = clampPosition(
    {
      x: dragSession.originX + deltaX,
      y: dragSession.originY + deltaY,
    },
    panelSize.value.width,
    panelSize.value.height,
  )
}

function handleDragEnd(event) {
  if (!dragSession || event.pointerId !== dragSession.pointerId) {
    return
  }
  const session = dragSession
  stopDraggingListeners()
  try {
    session.captureTarget?.releasePointerCapture?.(event.pointerId)
  } catch {
    // 指针捕获可能已由浏览器自动释放。
  }
  dragSession = undefined
  dragging.value = ''
  document.body.classList.remove('assistant-is-dragging')

  if (!session.moved) return
  if (session.kind === 'pet') {
    suppressPetClick.value = true
    saveStoredPosition(
      PET_POSITION_STORAGE_KEY,
      petPosition.value,
    )
    if (open.value && panelHasPosition.value) {
      saveStoredPosition(
        PANEL_POSITION_STORAGE_KEY,
        panelPosition.value,
      )
    }
    window.setTimeout(() => {
      suppressPetClick.value = false
    }, 0)
    return
  }

  panelHasPosition.value = true
  saveStoredPosition(
    PANEL_POSITION_STORAGE_KEY,
    panelPosition.value,
  )
}

function stopDraggingListeners() {
  window.removeEventListener('pointermove', handleDragMove)
  window.removeEventListener('pointerup', handleDragEnd)
  window.removeEventListener('pointercancel', handleDragEnd)
  document.body.classList.remove('assistant-is-dragging')
}

function handleGlobalKeydown(event) {
  if (event.key === 'Escape' && open.value) {
    open.value = false
  }
}

function handleOutsidePointerDown(event) {
  if (!open.value) return
  const target = event.target
  if (!(target instanceof Node)) return
  if (
    panelElement.value?.contains(target) ||
    petElement.value?.contains(target)
  ) {
    return
  }
  open.value = false
}

function handleInputKeydown(event) {
  if (
    event.key === 'Enter' &&
    !event.shiftKey &&
    !event.isComposing
  ) {
    event.preventDefault()
    sendMessage()
  }
}

function toggleAssistant() {
  open.value = !open.value
}

function handlePetClick() {
  if (suppressPetClick.value) {
    suppressPetClick.value = false
    return
  }
  toggleAssistant()
}

function clearConversation() {
  if (streaming.value) return
  messages.value = [{ ...WELCOME_MESSAGE }]
  modelName.value = 'deepseek-chat'
  saveMessages()
  nextTick(() => inputRef.value?.focus())
}

async function sendQuickPrompt(prompt) {
  draft.value = prompt
  await sendMessage()
}

async function sendMessage() {
  const content = draft.value.trim()
  if (!content || streaming.value) return

  const requestSubject = activeConversationSubject.value
  const requestMessages = messages.value
  const requestId = ++requestSequence
  open.value = true
  draft.value = ''
  const history = requestMessages
    .filter(
      (message) =>
        message.id !== WELCOME_MESSAGE.id &&
        !message.error &&
        message.content.trim(),
    )
    .slice(-8)
    .map((message) => ({
      role: message.role,
      content: message.content,
    }))
  const userMessage = {
    id: `user-${Date.now()}`,
    role: 'user',
    content,
    error: false,
  }
  const assistantMessage = reactive({
    id: `assistant-${Date.now()}`,
    role: 'assistant',
    content: '',
    error: false,
  })
  messages.value.push(userMessage, assistantMessage)
  streaming.value = true
  scrollToBottom()

  const controller = new AbortController()
  requestController = controller
  try {
    await streamAssistantQuestion(
      {
        message: content,
        subject: requestSubject,
        page_title: pageTitle.value,
        knowledge_context:
          typeof route.query.kp === 'string'
            ? route.query.kp
            : null,
        history,
      },
      {
        signal: controller.signal,
        onEvent(event) {
          handleStreamEvent(
            event,
            assistantMessage,
            requestSubject,
          )
        },
      },
    )
    if (!assistantMessage.content.trim()) {
      throw new Error('助手没有返回内容')
    }
  } catch (error) {
    if (error.name === 'AbortError') return
    assistantMessage.error = true
    assistantMessage.content =
      error.message || '助手暂时无法回答，请稍后重试'
    if (activeConversationSubject.value === requestSubject) {
      ElMessage.error(assistantMessage.content)
    }
  } finally {
    saveMessages(requestSubject, requestMessages)
    if (requestId !== requestSequence) return
    streaming.value = false
    if (requestController === controller) {
      requestController = undefined
    }
    await nextTick()
    scrollToBottom()
    highlightCodeBlocks()
    if (!open.value) unread.value = true
  }
}

function handleStreamEvent(event, assistantMessage, requestSubject) {
  if (event.type === 'meta') {
    if (activeConversationSubject.value === requestSubject) {
      modelName.value =
        event.model === 'local-preview'
          ? '本地预览'
          : String(event.model || 'deepseek-chat')
    }
    return
  }
  if (event.type === 'delta') {
    assistantMessage.content += String(event.content || '')
    if (activeConversationSubject.value === requestSubject) {
      if (!open.value) unread.value = true
      scrollToBottom()
    }
    return
  }
  if (event.type === 'error') {
    assistantMessage.error = true
    assistantMessage.content =
      event.message || '回答暂时中断，请稍后重试'
    return
  }
  if (event.type === 'done') {
    if (activeConversationSubject.value === requestSubject) {
      nextTick(() => highlightCodeBlocks())
    }
  }
}

function renderMarkdown(content) {
  if (!content) return ''
  const html = marked.parse(content, { async: false })
  return DOMPurify.sanitize(html)
}

function scrollToBottom() {
  nextTick(() => {
    const container = messageListRef.value
    if (container) {
      container.scrollTop = container.scrollHeight
    }
  })
}

function highlightCodeBlocks() {
  const container = messageListRef.value
  if (!container) return
  container.querySelectorAll('pre code').forEach((block) => {
    if (!block.dataset.highlighted) {
      hljs.highlightElement(block)
    }
  })
  container.querySelectorAll('.assistant-markdown a').forEach((link) => {
    link.target = '_blank'
    link.rel = 'noreferrer'
  })
}
</script>

<template>
  <Teleport to="body">
    <Transition name="assistant-window">
      <section
        v-if="open"
        ref="panelElement"
        class="assistant-window"
        :class="[
          panelTailClass,
          { 'is-dragging': dragging === 'panel' },
        ]"
        :style="[panelPositionStyle, panelTailStyle]"
        role="dialog"
        aria-label="AI 小助手"
      >
        <header
          class="assistant-header"
          @pointerdown="startPanelDrag"
        >
          <div class="assistant-identity">
            <span class="assistant-logo">
              <AssistantPet variant="mini" />
            </span>
            <div>
              <strong>AI 小助手</strong>
              <span>
                <i></i>
                {{ modelName }}
              </span>
            </div>
          </div>
          <div class="assistant-header-actions">
            <span
              class="drag-indicator"
              title="拖动窗口"
              aria-hidden="true"
            >
              <el-icon><Rank /></el-icon>
            </span>
            <el-tooltip content="清空对话" placement="bottom">
              <button
                type="button"
                class="assistant-icon-button"
                aria-label="清空对话"
                :disabled="streaming"
                @click="clearConversation"
              >
                <el-icon><Delete /></el-icon>
              </button>
            </el-tooltip>
            <el-tooltip content="关闭助手" placement="bottom">
              <button
                type="button"
                class="assistant-icon-button"
                aria-label="关闭助手"
                @click="toggleAssistant"
              >
                <el-icon><Close /></el-icon>
              </button>
            </el-tooltip>
          </div>
        </header>

        <div class="assistant-context">
          <span>{{ activeTitle }}</span>
          <small>{{ pageTitle }}</small>
        </div>

        <div ref="messageListRef" class="assistant-messages">
          <article
            v-for="(message, index) in messages"
            :key="message.id"
            class="assistant-message"
            :class="[
              message.role,
              { 'is-error': message.error },
            ]"
          >
            <span
              v-if="message.role === 'assistant'"
              class="message-avatar"
            >
              智
            </span>
            <div class="message-content">
              <div
                v-if="message.role === 'assistant'"
                class="message-bubble assistant-markdown"
                v-html="renderMarkdown(message.content)"
              ></div>
              <p v-else class="message-bubble">
                {{ message.content }}
              </p>
              <span
                v-if="
                  isLatestAssistantTyping &&
                  index === messages.length - 1
                "
                class="typing-cursor"
                aria-label="正在回答"
              ></span>
            </div>
            <span
              v-if="message.role === 'user'"
              class="message-avatar user-avatar"
            >
              {{ userStore.avatarText }}
            </span>
          </article>

          <div
            v-if="isLatestAssistantTyping && !messages.at(-1)?.content"
            class="thinking-row"
          >
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>

        <div v-if="!hasConversation" class="quick-prompts">
          <button
            v-for="prompt in quickPrompts"
            :key="prompt"
            type="button"
            @click="sendQuickPrompt(prompt)"
          >
            {{ prompt }}
          </button>
        </div>

        <footer class="assistant-composer">
          <div class="composer-box">
            <el-input
              ref="inputRef"
              v-model="draft"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 4 }"
              resize="none"
              maxlength="4000"
              placeholder="输入你的问题..."
              :disabled="streaming"
              @keydown="handleInputKeydown"
            />
            <el-button
              type="primary"
              circle
              :icon="Promotion"
              :loading="streaming"
              :disabled="!canSend"
              aria-label="发送消息"
              @click="sendMessage"
            />
          </div>
        </footer>
      </section>
    </Transition>

    <button
      ref="petElement"
      type="button"
      class="assistant-pet"
      :class="{
        'is-open': open,
        'is-dragging': dragging === 'pet',
        'hint-below': petHintBelow,
        'hint-right': petHintOnRight,
      }"
      :style="petPositionStyle"
      :aria-expanded="open"
      aria-label="AI 桌面宠物，点击打开对话，拖动可移动"
      draggable="false"
      @pointerdown="startPetDrag"
      @click="handlePetClick"
    >
      <span class="pet-hint" aria-hidden="true">有问题？</span>
      <span class="pet-stage">
        <AssistantPet />
      </span>
      <span v-if="unread" class="pet-unread" aria-label="有新回答">
        <i></i>
      </span>
    </button>
  </Teleport>
</template>

<style scoped>
.assistant-window {
  position: fixed;
  z-index: 1200;
  display: flex;
  width: min(404px, calc(100vw - 32px));
  height: min(620px, calc(100vh - 16px));
  min-height: 430px;
  flex-direction: column;
  overflow: visible;
  border: 1px solid color-mix(in srgb, #58b9a5 38%, var(--app-border));
  border-radius: 18px;
  background: var(--app-surface);
  box-shadow:
    0 24px 64px rgba(15, 33, 48, 0.22),
    0 5px 16px rgba(15, 33, 48, 0.1);
  isolation: isolate;
}

.assistant-window::after {
  position: absolute;
  z-index: -1;
  top: var(--tail-top, 108px);
  width: 16px;
  height: 16px;
  border: 1px solid color-mix(in srgb, #58b9a5 38%, var(--app-border));
  background: var(--app-bg);
  content: "";
  transform: rotate(45deg);
}

.assistant-window.tail-left::after {
  left: -8px;
}

.assistant-window.tail-right::after {
  right: -8px;
}

.assistant-header {
  display: flex;
  min-height: 64px;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px 10px 16px;
  border-bottom: 1px solid color-mix(in srgb, #58b9a5 26%, var(--app-border));
  border-radius: 17px 17px 0 0;
  color: var(--app-text);
  background: color-mix(in srgb, #58b9a5 13%, var(--app-surface));
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.assistant-window.is-dragging .assistant-header {
  cursor: grabbing;
}

.assistant-identity,
.assistant-header-actions {
  display: flex;
  align-items: center;
}

.assistant-identity {
  min-width: 0;
  gap: 10px;
}

.assistant-logo {
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  place-items: center;
  padding: 3px;
  border: 1px solid color-mix(in srgb, #58b9a5 44%, var(--app-border));
  border-radius: 12px;
  background: var(--app-surface);
}

.assistant-identity > div {
  display: flex;
  min-width: 0;
  flex-direction: column;
}

.assistant-identity strong {
  font-size: 15px;
  line-height: 1.35;
}

.assistant-identity > div > span {
  display: flex;
  max-width: 230px;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
  overflow: hidden;
  color: var(--app-muted);
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.assistant-identity > div > span i {
  width: 6px;
  height: 6px;
  flex: 0 0 6px;
  border-radius: 50%;
  background: #58b9a5;
  box-shadow: 0 0 0 3px rgba(88, 185, 165, 0.13);
}

.assistant-header-actions {
  gap: 4px;
}

.assistant-icon-button {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  padding: 0;
  border: 0;
  border-radius: 7px;
  color: var(--app-muted);
  background: transparent;
  cursor: pointer;
}

.assistant-icon-button:hover {
  color: var(--app-text);
  background: rgba(88, 185, 165, 0.12);
}

.drag-indicator {
  display: grid;
  width: 28px;
  height: 34px;
  place-items: center;
  color: var(--app-muted);
  opacity: 0.58;
}

.assistant-icon-button:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.assistant-context {
  display: flex;
  min-height: 34px;
  align-items: center;
  gap: 8px;
  padding: 0 14px;
  border-bottom: 1px solid var(--app-border);
  color: var(--app-text);
  background: var(--app-surface-muted);
  font-size: 11px;
}

.assistant-context span {
  overflow: hidden;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.assistant-context small {
  flex: none;
  padding-left: 8px;
  border-left: 1px solid var(--app-border);
  color: var(--app-muted);
  font-size: 10px;
}

.assistant-messages {
  flex: 1;
  min-height: 0;
  padding: 18px 14px;
  overflow-y: auto;
  background: var(--app-bg);
  scroll-behavior: smooth;
}

.assistant-message {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 16px;
}

.assistant-message.user {
  justify-content: flex-end;
}

.message-avatar {
  display: grid;
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  place-items: center;
  border-radius: 7px;
  color: #fff;
  background: #246BFE;
  font-size: 11px;
  font-weight: 750;
}

.message-avatar.user-avatar {
  color: #2f7fbc;
  background: #dceefb;
}

.message-content {
  display: flex;
  max-width: calc(100% - 36px);
  min-width: 0;
  flex-direction: column;
}

.assistant-message.user .message-content {
  align-items: flex-end;
}

.message-bubble {
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  color: var(--app-text);
  background: var(--app-surface);
  font-size: 13px;
  line-height: 1.7;
  overflow-wrap: anywhere;
}

.assistant-message.user .message-bubble {
  border-color: #246BFE;
  color: #fff;
  background: #246BFE;
  white-space: pre-wrap;
}

.assistant-message.is-error .message-bubble {
  border-color: rgba(217, 79, 89, 0.4);
  color: #c45656;
  background: rgba(217, 79, 89, 0.07);
}

.assistant-markdown :deep(p) {
  margin: 0 0 8px;
}

.assistant-markdown :deep(p:last-child) {
  margin-bottom: 0;
}

.assistant-markdown :deep(ul),
.assistant-markdown :deep(ol) {
  margin: 7px 0;
  padding-left: 19px;
}

.assistant-markdown :deep(h1),
.assistant-markdown :deep(h2),
.assistant-markdown :deep(h3) {
  margin: 10px 0 6px;
  font-size: 1em;
}

.assistant-markdown :deep(code:not(pre code)) {
  padding: 2px 4px;
  border-radius: 4px;
  color: #2f78b7;
  background: rgba(36, 107, 254, 0.1);
  font-family: "SFMono-Regular", Consolas, monospace;
  font-size: 0.9em;
}

.assistant-markdown :deep(pre) {
  margin: 9px 0;
  overflow-x: auto;
  border-radius: 7px;
  background: #0d1117;
}

.assistant-markdown :deep(pre code) {
  display: block;
  padding: 12px;
  font-family: "SFMono-Regular", Consolas, monospace;
  font-size: 11px;
  line-height: 1.6;
}

.assistant-markdown :deep(blockquote) {
  margin: 8px 0;
  padding-left: 10px;
  border-left: 3px solid #246BFE;
  color: var(--app-muted);
}

.typing-cursor {
  display: inline-block;
  width: 2px;
  height: 13px;
  margin-top: 5px;
  background: #246BFE;
  animation: assistant-cursor-blink 0.8s steps(1) infinite;
}

.thinking-row {
  display: flex;
  align-items: center;
  gap: 4px;
  margin: -8px 0 14px 36px;
  color: #246BFE;
}

.thinking-row span {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
  animation: assistant-thinking 1.1s ease-in-out infinite;
}

.thinking-row span:nth-child(2) {
  animation-delay: 0.16s;
}

.thinking-row span:nth-child(3) {
  animation-delay: 0.32s;
}

.quick-prompts {
  display: flex;
  gap: 6px;
  padding: 0 12px 10px;
  overflow-x: auto;
  background: var(--app-bg);
}

.quick-prompts button {
  flex: none;
  padding: 6px 9px;
  border: 1px solid var(--app-border);
  border-radius: 7px;
  color: var(--app-muted);
  background: var(--app-surface);
  font-size: 10px;
  white-space: nowrap;
  cursor: pointer;
}

.quick-prompts button:hover {
  border-color: #246BFE;
  color: #246BFE;
}

.assistant-composer {
  padding: 10px 12px 12px;
  border-top: 1px solid var(--app-border);
  background: var(--app-surface);
}

.composer-box {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}

.composer-box :deep(.el-textarea) {
  min-width: 0;
  flex: 1;
}

.composer-box :deep(.el-textarea__inner) {
  min-height: 42px !important;
  padding: 10px 12px;
  border-radius: 8px;
  box-shadow: none;
  font-size: 13px;
}

.composer-box :deep(.el-button) {
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  margin-bottom: 2px;
}

.assistant-pet {
  position: fixed;
  z-index: 1210;
  display: block;
  width: 112px;
  height: 116px;
  padding: 0;
  border: 0;
  color: var(--app-text);
  background: transparent;
  cursor: pointer;
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.assistant-pet:active,
.assistant-pet.is-dragging {
  cursor: grabbing;
}

.pet-stage {
  display: block;
  width: 100%;
  height: 100%;
  filter: drop-shadow(0 12px 12px rgba(15, 33, 48, 0.18));
  transition: transform 0.18s ease, filter 0.18s ease;
}

.assistant-pet:hover .pet-stage,
.assistant-pet:focus-visible .pet-stage {
  filter: drop-shadow(0 15px 15px rgba(15, 33, 48, 0.22));
  transform: translateY(-3px) scale(1.035);
}

.assistant-pet.is-dragging .pet-stage {
  transition: none;
  transform: scale(1.06) rotate(-2deg);
}

.pet-hint {
  position: absolute;
  right: calc(100% - 12px);
  bottom: 67px;
  padding: 7px 10px;
  border: 1px solid color-mix(in srgb, #58b9a5 38%, var(--app-border));
  border-radius: 12px;
  color: var(--app-text);
  background: var(--app-surface);
  box-shadow: 0 5px 16px rgba(15, 33, 48, 0.12);
  font-size: 11px;
  font-weight: 650;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transform: translateY(4px) scale(0.96);
  transition: opacity 0.16s ease, transform 0.16s ease;
}

.pet-hint::after {
  position: absolute;
  right: -5px;
  bottom: 10px;
  width: 8px;
  height: 8px;
  border-top: 1px solid color-mix(in srgb, #58b9a5 38%, var(--app-border));
  border-right: 1px solid color-mix(in srgb, #58b9a5 38%, var(--app-border));
  background: var(--app-surface);
  content: "";
  transform: rotate(45deg);
}

.hint-right .pet-hint {
  right: auto;
  left: calc(100% - 12px);
}

.hint-right .pet-hint::after {
  right: auto;
  left: -5px;
  border-top: 0;
  border-right: 0;
  border-bottom: 1px solid
    color-mix(in srgb, #58b9a5 38%, var(--app-border));
  border-left: 1px solid
    color-mix(in srgb, #58b9a5 38%, var(--app-border));
}

.hint-below .pet-hint {
  top: calc(100% - 11px);
  bottom: auto;
}

.hint-below .pet-hint::after {
  top: -5px;
  bottom: auto;
}

.assistant-pet:hover .pet-hint,
.assistant-pet:focus-visible .pet-hint,
.assistant-pet.is-open .pet-hint {
  opacity: 1;
  transform: translateY(0) scale(1);
}

.assistant-pet.is-open .pet-hint {
  opacity: 0;
}

.pet-unread {
  position: absolute;
  top: 5px;
  right: 7px;
  display: grid;
  width: 18px;
  height: 18px;
  place-items: center;
  border: 2px solid var(--app-bg);
  border-radius: 50%;
  background: #D94F59;
  box-shadow: 0 2px 8px rgba(217, 79, 89, 0.34);
}

.pet-unread i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #fff;
}

:global(body.assistant-is-dragging) {
  cursor: grabbing;
  user-select: none;
}

.assistant-window-enter-active,
.assistant-window-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.assistant-window-enter-from,
.assistant-window-leave-to {
  opacity: 0;
  transform: translateY(12px) scale(0.98);
}

@keyframes assistant-cursor-blink {
  0%,
  50% {
    opacity: 1;
  }

  51%,
  100% {
    opacity: 0;
  }
}

@keyframes assistant-thinking {
  0%,
  60%,
  100% {
    opacity: 0.35;
    transform: translateY(0);
  }

  30% {
    opacity: 1;
    transform: translateY(-3px);
  }
}

@media (max-width: 640px) {
  .assistant-window {
    width: calc(100vw - 16px);
    height: min(620px, calc(100dvh - 16px));
    min-height: 0;
    border-radius: 15px;
  }

  .assistant-window::after {
    display: none;
  }

  .assistant-header {
    border-radius: 14px 14px 0 0;
  }

  .assistant-pet.is-open {
    display: none;
  }

  .assistant-messages {
    padding: 15px 12px;
  }

  .assistant-context {
    padding: 0 12px;
  }

  .quick-prompts {
    padding-right: 10px;
    padding-left: 10px;
  }
}

@media (max-width: 380px) {
  .assistant-pet {
    width: 104px;
    height: 108px;
  }
}
</style>
