<script setup>
import {
  ChatDotRound,
  Delete,
  Menu,
  Plus,
  Promotion,
} from '@element-plus/icons-vue'
import DOMPurify from 'dompurify'
import { ElMessage, ElMessageBox } from 'element-plus'
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
  ref,
  watch,
} from 'vue'
import { useRoute } from 'vue-router'

import {
  askQuestion,
  deleteChatSession,
  getChatHistory,
} from '../api/chat'
import {
  LEARNING_CONTENT_DELETED_EVENT,
  useLearningContentStore,
} from '../stores/learningContent'
import { useUserStore } from '../stores/user'
import { getUserScopedStorageKey } from '../utils/userStorage'

const SESSION_STORAGE_KEY = 'slp_chat_sessions'
const TYPEWRITER_INTERVAL = 18

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

const sessions = ref([])
const currentSessionId = ref('')
const messages = ref([])
const inputDraft = ref('')
const sending = ref(false)
const deletingSessionId = ref('')
const loadingHistory = ref(false)
const mobileSessionsOpen = ref(false)
const messageListRef = ref(null)
const inputRef = ref(null)

let typewriterTimer
let activeTypingMessage = null
let pendingKnowledgeContext =
  typeof route.query.kp === 'string' ? route.query.kp : null

const currentSession = computed(
  () =>
    sessions.value.find(
      (session) => session.sessionId === currentSessionId.value,
    ) || null,
)
const subjectSessions = computed(() =>
  sessions.value.filter(
    (session) =>
      session.subject === learningContentStore.activeSubject,
  ),
)
const currentTitle = computed(
  () => currentSession.value?.title || '新的对话',
)
const currentKnowledgeTags = computed(() => {
  const session = currentSession.value
  const tags = session?.relatedKnowledge?.length
    ? session.relatedKnowledge
    : session?.knowledgeContext
      ? [session.knowledgeContext]
      : []
  return tags.slice(0, 4)
})
const isTyping = computed(() =>
  messages.value.some((message) => message.typing),
)
const canSend = computed(
  () =>
    Boolean(inputDraft.value.trim()) &&
    !sending.value &&
    !isTyping.value,
)

onMounted(async () => {
  window.addEventListener(
    LEARNING_CONTENT_DELETED_EVENT,
    handleLearningContentDeleted,
  )
  loadStoredSessions()
  await learningContentStore.fetchSubjects().catch(() => {})
  await activateSubjectSession()
})

watch(
  () => learningContentStore.activeSubject,
  async () => {
    stopTypewriter(false)
    messages.value = []
    pendingKnowledgeContext = null
    await activateSubjectSession(true)
  },
)

onBeforeUnmount(() => {
  window.removeEventListener(
    LEARNING_CONTENT_DELETED_EVENT,
    handleLearningContentDeleted,
  )
  stopTypewriter(false)
})

function handleLearningContentDeleted(event) {
  const subject = event.detail?.subject
  if (!subject) return
  const removedCurrent = currentSession.value?.subject === subject
  sessions.value = sessions.value.filter(
    (session) => session.subject !== subject,
  )
  if (removedCurrent) {
    currentSessionId.value = ''
    messages.value = []
  }
  saveSessions()
}

function loadStoredSessions() {
  try {
    const stored = JSON.parse(
      localStorage.getItem(
        getUserScopedStorageKey(SESSION_STORAGE_KEY),
      ) || '[]',
    )
    sessions.value = Array.isArray(stored)
      ? stored
          .map((session) => ({
            ...session,
            subject:
              session.subject || inferSessionSubject(session),
          }))
          .sort((left, right) => right.updatedAt - left.updatedAt)
      : []
    saveSessions()
  } catch {
    sessions.value = []
  }
}

function inferSessionSubject(session) {
  const knowledgeContext = String(session.knowledgeContext || '')
  const generatedSubject = knowledgeContext.match(
    /^(custom_(?:\d+_)?[a-z0-9]+)_/i,
  )
  return generatedSubject?.[1] || ''
}

function saveSessions() {
  localStorage.setItem(
    getUserScopedStorageKey(SESSION_STORAGE_KEY),
    JSON.stringify(sessions.value),
  )
}

function createSessionId() {
  return crypto.randomUUID?.() ||
    `chat-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

async function activateSubjectSession(force = false) {
  if (subjectSessions.value.length) {
    await selectSession(subjectSessions.value[0].sessionId, force)
    return
  }
  createNewSession(force)
}

function createNewSession(force = false) {
  if (sending.value && !force) return
  if (
    currentSession.value?.subject ===
      learningContentStore.activeSubject &&
    messages.value.length === 0
  ) {
    inputRef.value?.focus()
    return
  }

  stopTypewriter(false)
  const knowledgeContext = pendingKnowledgeContext
  const session = {
    sessionId: createSessionId(),
    subject: learningContentStore.activeSubject,
    title: '新的对话',
    lastMessage: '开始一段新的学习对话',
    updatedAt: Date.now(),
    knowledgeContext,
    relatedKnowledge: knowledgeContext ? [knowledgeContext] : [],
    hasHistory: false,
  }
  sessions.value.unshift(session)
  currentSessionId.value = session.sessionId
  messages.value = []
  mobileSessionsOpen.value = false
  saveSessions()
  nextTick(() => inputRef.value?.focus())
}

async function selectSession(sessionId, force = false) {
  if (sending.value && !force) return
  if (sessionId === currentSessionId.value && messages.value.length) {
    mobileSessionsOpen.value = false
    return
  }

  stopTypewriter(false)
  currentSessionId.value = sessionId
  mobileSessionsOpen.value = false
  const session = sessions.value.find(
    (item) => item.sessionId === sessionId,
  )
  messages.value = []
  if (!session?.hasHistory) {
    await nextTick()
    inputRef.value?.focus()
    return
  }

  loadingHistory.value = true
  try {
    const history = await getChatHistory(sessionId)
    if (currentSessionId.value !== sessionId) return
    if (!history) {
      removeSession(sessionId)
      createNewSession(true)
      return
    }
    messages.value = history.messages.map((message) => ({
      id: `${sessionId}-${message.role}-${message.timestamp || Math.random()}`,
      role: message.role,
      content: message.content,
      displayContent: message.content,
      fullContent: message.content,
      timestamp: message.timestamp,
      typing: false,
    }))
    if (history.knowledge_context) {
      session.knowledgeContext = history.knowledge_context
    }
    if (history.subject) {
      session.subject = history.subject
    }
    saveSessions()
    await nextTick()
    scrollToBottom()
    window.requestAnimationFrame(highlightCodeBlocks)
  } catch (error) {
    if (error.response?.status === 404) {
      removeSession(sessionId)
      if (currentSessionId.value === sessionId) {
        createNewSession(true)
      }
      return
    }
  } finally {
    loadingHistory.value = false
  }
}

function removeSession(sessionId) {
  sessions.value = sessions.value.filter(
    (session) => session.sessionId !== sessionId,
  )
  if (currentSessionId.value === sessionId) {
    currentSessionId.value = ''
    messages.value = []
  }
  saveSessions()
}

async function deleteSession(session) {
  if (sending.value || deletingSessionId.value) return

  try {
    await ElMessageBox.confirm(
      `确定删除“${session.title}”吗？删除后无法恢复。`,
      '删除对话',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
      },
    )
  } catch {
    return
  }

  const wasCurrent = currentSessionId.value === session.sessionId
  deletingSessionId.value = session.sessionId
  try {
    await deleteChatSession(session.sessionId)
    removeSession(session.sessionId)
    if (wasCurrent) {
      const nextSession = subjectSessions.value[0]
      if (nextSession) {
        await selectSession(nextSession.sessionId, true)
      } else {
        createNewSession(true)
      }
    }
    ElMessage.success('对话已删除')
  } catch {
    // 请求层会展示具体错误。
  } finally {
    deletingSessionId.value = ''
  }
}

function handleKeydown(event) {
  if (
    event.key === 'Enter' &&
    !event.shiftKey &&
    !event.isComposing
  ) {
    event.preventDefault()
    sendMessage()
  }
}

async function sendMessage() {
  if (!canSend.value) return
  const content = inputDraft.value.trim()
  inputDraft.value = ''
  await sendContent(content)
}

async function sendContent(content) {
  if (!content) return
  if (!currentSessionId.value) createNewSession()
  const session = currentSession.value
  const requestSessionId = session?.sessionId
  const requestSubject = learningContentStore.activeSubject
  if (!requestSessionId) return
  messages.value.push({
    id: `user-${Date.now()}`,
    role: 'user',
    content,
    displayContent: content,
    fullContent: content,
    timestamp: new Date().toISOString(),
    typing: false,
  })
  scrollToBottom()
  sending.value = true

  try {
    const response = await askQuestion({
      subject: requestSubject,
      session_id: requestSessionId,
      message: content,
      knowledge_context: session?.knowledgeContext || null,
    })
    updateSessionAfterReply(
      requestSessionId,
      content,
      response,
      requestSubject,
    )
    if (
      currentSessionId.value !== requestSessionId ||
      learningContentStore.activeSubject !== requestSubject
    ) {
      return
    }
    const assistantMessage = {
      id: `assistant-${Date.now()}`,
      role: 'assistant',
      content: response.reply,
      displayContent: '',
      fullContent: response.reply,
      timestamp: new Date().toISOString(),
      typing: true,
    }
    messages.value.push(assistantMessage)
    startTypewriter(messages.value[messages.value.length - 1])
  } finally {
    sending.value = false
    if (
      currentSession.value?.subject !==
      learningContentStore.activeSubject
    ) {
      await activateSubjectSession(true)
    }
  }
}

function updateSessionAfterReply(
  sessionId,
  content,
  response,
  requestSubject,
) {
  const session = sessions.value.find(
    (item) => item.sessionId === sessionId,
  )
  if (!session) return
  session.subject = response.subject || requestSubject
  if (session.title === '新的对话') {
    session.title = content.replace(/\s+/g, ' ').slice(0, 24)
  }
  session.lastMessage = response.reply
    .replace(/[#*_`>\n]/g, ' ')
    .replace(/\s+/g, ' ')
    .slice(0, 48)
  session.updatedAt = Date.now()
  session.hasHistory = true
  session.relatedKnowledge = response.related_knowledge || []
  session.knowledgeContext =
    response.related_knowledge?.[0] ||
    session.knowledgeContext ||
    null
  sessions.value = [
    session,
    ...sessions.value.filter(
      (item) => item.sessionId !== session.sessionId,
    ),
  ]
  saveSessions()
}

function startTypewriter(message) {
  stopTypewriter(false)
  activeTypingMessage = message
  const characters = Array.from(message.fullContent)
  let index = 0

  typewriterTimer = window.setInterval(() => {
    index += 1
    message.displayContent = characters.slice(0, index).join('')
    if (index % 4 === 0) scrollToBottom()
    if (index >= characters.length) {
      stopTypewriter(true)
    }
  }, TYPEWRITER_INTERVAL)
}

function stopTypewriter(finish) {
  if (typewriterTimer) {
    window.clearInterval(typewriterTimer)
    typewriterTimer = null
  }
  if (activeTypingMessage) {
    if (finish) {
      activeTypingMessage.displayContent =
        activeTypingMessage.fullContent
    }
    activeTypingMessage.typing = false
    activeTypingMessage = null
  }
  if (finish) {
    nextTick(() => {
      scrollToBottom()
      highlightCodeBlocks()
    })
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
    if (!container) return
    container.scrollTop = container.scrollHeight
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
  container.querySelectorAll('.markdown-body a').forEach((link) => {
    link.target = '_blank'
    link.rel = 'noreferrer'
  })
}

function formatSessionTime(value) {
  if (!value) return ''
  const date = new Date(value)
  const now = new Date()
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
    })
  }
  return date.toLocaleDateString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
  })
}
</script>

<template>
  <section class="chat-page">
    <div
      v-if="mobileSessionsOpen"
      class="sessions-mask"
      @click="mobileSessionsOpen = false"
    ></div>

    <aside
      class="sessions-panel"
      :class="{ 'is-open': mobileSessionsOpen }"
    >
      <header class="sessions-header">
        <div>
          <h1>对话记录</h1>
          <span>{{ subjectSessions.length }} 个会话</span>
        </div>
        <el-button
          type="primary"
          :icon="Plus"
          class="new-chat-button"
          :disabled="sending"
          @click="createNewSession()"
        >
          新建对话
        </el-button>
      </header>

      <div class="session-list">
        <div
          v-for="session in subjectSessions"
          :key="session.sessionId"
          class="session-item"
          :class="{
            active: session.sessionId === currentSessionId,
          }"
        >
          <button
            type="button"
            class="session-select"
            :disabled="sending"
            @click="selectSession(session.sessionId)"
          >
            <span class="session-icon">
              <el-icon><ChatDotRound /></el-icon>
            </span>
            <span class="session-copy">
              <strong>{{ session.title }}</strong>
              <small>{{ session.lastMessage }}</small>
            </span>
            <time>{{ formatSessionTime(session.updatedAt) }}</time>
          </button>
          <el-tooltip content="删除对话" placement="right">
            <button
              type="button"
              class="session-delete-button"
              aria-label="删除对话"
              :disabled="sending || deletingSessionId === session.sessionId"
              @click="deleteSession(session)"
            >
              <el-icon><Delete /></el-icon>
            </button>
          </el-tooltip>
        </div>
      </div>
    </aside>

    <main class="conversation-panel">
      <header class="conversation-header">
        <div class="conversation-heading">
          <button
            class="mobile-menu-button"
            type="button"
            aria-label="打开会话列表"
            @click="mobileSessionsOpen = true"
          >
            <el-icon><Menu /></el-icon>
          </button>
          <div>
            <h2>{{ currentTitle }}</h2>
            <div class="knowledge-tags">
              <el-tag
                v-for="tag in currentKnowledgeTags"
                :key="tag"
                size="small"
                effect="plain"
              >
                {{ tag }}
              </el-tag>
              <span v-if="!currentKnowledgeTags.length">
                直接回答学习问题
              </span>
            </div>
          </div>
        </div>
        <span class="tutor-status">
          <i></i>
          智学小助手
        </span>
      </header>

      <div ref="messageListRef" class="message-list">
        <div v-if="loadingHistory" class="history-loading">
          <el-skeleton :rows="6" animated />
        </div>

        <div v-else-if="!messages.length" class="chat-empty">
          <span class="assistant-mark">智</span>
          <h2>从一个问题开始</h2>
          <p>直接描述你的问题，我会给出答案、解释和示例。</p>
        </div>

        <template v-else>
          <article
            v-for="message in messages"
            :key="message.id"
            class="message-row"
            :class="message.role"
          >
            <span v-if="message.role === 'assistant'" class="message-avatar">
              智
            </span>
            <div class="message-body">
              <div class="message-bubble">
                <div
                  v-if="message.role === 'assistant'"
                  class="markdown-body"
                  v-html="renderMarkdown(message.displayContent)"
                ></div>
                <p v-else>{{ message.displayContent }}</p>
                <span v-if="message.typing" class="typing-cursor"></span>
              </div>
              <time>{{ formatSessionTime(message.timestamp) }}</time>
            </div>
            <span v-if="message.role === 'user'" class="message-avatar user">
              {{ userStore.avatarText }}
            </span>
          </article>
        </template>
      </div>

      <footer class="composer">
        <div class="composer-shell">
          <el-input
            ref="inputRef"
            v-model="inputDraft"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 5 }"
            resize="none"
            placeholder="输入你的问题..."
            maxlength="4000"
            :disabled="sending"
            @keydown="handleKeydown"
          />
          <div class="composer-actions">
            <el-button
              type="primary"
              circle
              :icon="Promotion"
              :loading="sending"
              :disabled="!canSend"
              aria-label="发送消息"
              @click="sendMessage"
            />
          </div>
        </div>
      </footer>
    </main>
  </section>
</template>

<style scoped>
.chat-page {
  position: relative;
  display: grid;
  height: calc(100vh - 144px);
  min-height: 620px;
  grid-template-columns: 268px minmax(0, 1fr);
  overflow: hidden;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
}

.sessions-panel {
  display: flex;
  min-width: 0;
  flex-direction: column;
  border-right: 1px solid var(--app-border);
  background: var(--app-surface-muted);
}

.sessions-header {
  padding: 18px;
  border-bottom: 1px solid var(--app-border);
}

.sessions-header > div {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.sessions-header h1 {
  margin: 0;
  color: var(--app-text);
  font-size: 16px;
}

.sessions-header span {
  color: var(--app-muted);
  font-size: 10px;
}

.new-chat-button {
  width: 100%;
  height: 38px;
  margin-top: 14px;
}

.session-list {
  flex: 1;
  padding: 10px;
  overflow-y: auto;
}

.session-item {
  display: flex;
  width: 100%;
  align-items: start;
  gap: 2px;
  padding: 3px;
  border: 1px solid transparent;
  border-radius: 8px;
}

.session-select {
  display: grid;
  min-width: 0;
  flex: 1;
  grid-template-columns: 30px minmax(0, 1fr) auto;
  align-items: start;
  gap: 8px;
  padding: 8px 6px;
  border: 0;
  color: var(--app-muted);
  text-align: left;
  background: transparent;
  cursor: pointer;
}

.session-select:disabled,
.session-delete-button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.session-item:hover {
  background: color-mix(in srgb, var(--app-surface) 60%, transparent);
}

.session-item.active {
  border-color: rgba(36, 107, 254, 0.25);
  background: rgba(36, 107, 254, 0.1);
}

.session-icon {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border-radius: 7px;
  color: #246BFE;
  background: rgba(36, 107, 254, 0.1);
}

.session-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
}

.session-copy strong {
  overflow: hidden;
  color: var(--app-text);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-copy small {
  display: -webkit-box;
  margin-top: 4px;
  overflow: hidden;
  color: var(--app-muted);
  font-size: 10px;
  line-height: 1.45;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.session-item time {
  color: var(--app-muted);
  font-size: 9px;
  white-space: nowrap;
}

.session-delete-button {
  display: grid;
  width: 28px;
  height: 28px;
  flex: 0 0 auto;
  place-items: center;
  margin-top: 4px;
  padding: 0;
  border: 0;
  border-radius: 6px;
  color: var(--app-muted);
  background: transparent;
  cursor: pointer;
  opacity: 0.5;
}

.session-delete-button:hover,
.session-delete-button:focus-visible {
  color: #D94F59;
  background: rgba(217, 79, 89, 0.1);
  opacity: 1;
}

.conversation-panel {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
}

.conversation-header {
  display: flex;
  min-height: 76px;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 12px 22px;
  border-bottom: 1px solid var(--app-border);
}

.conversation-heading {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 12px;
}

.conversation-heading > div {
  min-width: 0;
}

.conversation-heading h2 {
  margin: 0;
  overflow: hidden;
  color: var(--app-text);
  font-size: 16px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.knowledge-tags {
  display: flex;
  min-height: 20px;
  align-items: center;
  gap: 5px;
  margin-top: 5px;
  overflow: hidden;
}

.knowledge-tags > span {
  color: var(--app-muted);
  font-size: 10px;
}

.tutor-status {
  display: inline-flex;
  flex: none;
  align-items: center;
  gap: 6px;
  color: var(--app-muted);
  font-size: 10px;
}

.tutor-status i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #149A76;
  box-shadow: 0 0 0 3px rgba(20, 154, 118, 0.1);
}

.mobile-menu-button {
  display: none;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  place-items: center;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  color: var(--app-text);
  background: var(--app-surface);
  cursor: pointer;
}

.message-list {
  flex: 1;
  min-height: 0;
  padding: 24px clamp(16px, 4vw, 48px);
  overflow-y: auto;
  background:
    linear-gradient(
      color-mix(in srgb, var(--app-bg) 70%, transparent),
      color-mix(in srgb, var(--app-bg) 70%, transparent)
    );
  scroll-behavior: smooth;
}

.history-loading {
  max-width: 760px;
  margin: 0 auto;
}

.chat-empty {
  display: flex;
  height: 100%;
  min-height: 300px;
  align-items: center;
  flex-direction: column;
  justify-content: center;
  text-align: center;
}

.assistant-mark,
.message-avatar {
  display: grid;
  place-items: center;
  color: #fff;
  background: #246BFE;
  font-weight: 750;
}

.assistant-mark {
  width: 54px;
  height: 54px;
  margin-bottom: 16px;
  border-radius: 8px;
  font-size: 20px;
}

.chat-empty h2 {
  margin: 0;
  color: var(--app-text);
  font-size: 22px;
}

.chat-empty p {
  margin: 8px 0 0;
  color: var(--app-muted);
  font-size: 13px;
}

.message-row {
  display: flex;
  width: min(900px, 100%);
  align-items: flex-start;
  gap: 10px;
  margin: 0 auto 18px;
}

.message-row.user {
  justify-content: flex-end;
}

.message-avatar {
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  border-radius: 8px;
  font-size: 12px;
}

.message-avatar.user {
  color: #246BFE;
  background: rgba(36, 107, 254, 0.12);
}

.message-body {
  display: flex;
  max-width: min(78%, 720px);
  min-width: 0;
  flex-direction: column;
}

.message-row.user .message-body {
  align-items: flex-end;
}

.message-bubble {
  position: relative;
  padding: 12px 15px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  color: var(--app-text);
  background: var(--app-surface);
  font-size: 14px;
  line-height: 1.75;
  overflow-wrap: anywhere;
}

.message-row.user .message-bubble {
  border-color: #246BFE;
  color: #fff;
  background: #246BFE;
}

.message-bubble > p {
  margin: 0;
  white-space: pre-wrap;
}

.message-body > time {
  margin-top: 5px;
  color: var(--app-muted);
  font-size: 9px;
}

.typing-cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  margin-left: 2px;
  vertical-align: text-bottom;
  background: #246BFE;
  animation: cursor-blink 0.8s steps(1) infinite;
}

.markdown-body :deep(p) {
  margin: 0 0 9px;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 8px 0;
  padding-left: 20px;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: 12px 0 8px;
  font-size: 1em;
}

.markdown-body :deep(code:not(pre code)) {
  padding: 2px 5px;
  border-radius: 4px;
  color: #c7254e;
  background: rgba(36, 107, 254, 0.1);
  font-family: "SFMono-Regular", Consolas, monospace;
  font-size: 0.9em;
}

.markdown-body :deep(pre) {
  margin: 12px 0;
  overflow-x: auto;
  border-radius: 8px;
  background: #0d1117;
}

.markdown-body :deep(pre code) {
  display: block;
  padding: 14px;
  font-family: "SFMono-Regular", Consolas, monospace;
  font-size: 12px;
  line-height: 1.65;
}

.markdown-body :deep(blockquote) {
  margin: 10px 0;
  padding-left: 12px;
  border-left: 3px solid #246BFE;
  color: var(--app-muted);
}

.composer {
  padding: 12px clamp(16px, 4vw, 48px) 10px;
  border-top: 1px solid var(--app-border);
  background: var(--app-surface);
}

.composer-shell {
  position: relative;
  max-width: 900px;
  margin: 0 auto;
  padding-right: 110px;
}

.composer-shell :deep(.el-textarea__inner) {
  min-height: 44px !important;
  padding: 11px 14px;
  border-radius: 8px;
  box-shadow: none;
}

.composer-actions {
  position: absolute;
  right: 6px;
  bottom: 6px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.sessions-mask {
  display: none;
}

@keyframes cursor-blink {
  0%,
  50% {
    opacity: 1;
  }

  51%,
  100% {
    opacity: 0;
  }
}

@media (max-width: 900px) {
  .chat-page {
    height: calc(100vh - 110px);
    min-height: 560px;
    grid-template-columns: 1fr;
  }

  .sessions-panel {
    position: absolute;
    inset: 0 auto 0 0;
    z-index: 20;
    width: 280px;
    transform: translateX(-102%);
    transition: transform 0.2s ease;
  }

  .sessions-panel.is-open {
    transform: translateX(0);
  }

  .sessions-mask {
    position: absolute;
    inset: 0;
    z-index: 15;
    display: block;
    background: rgba(13, 30, 42, 0.4);
  }

  .mobile-menu-button {
    display: grid;
  }

  .tutor-status {
    display: none;
  }
}

@media (max-width: 640px) {
  .conversation-header {
    min-height: 68px;
    padding: 10px 12px;
  }

  .message-list {
    padding: 18px 12px;
  }

  .message-body {
    max-width: calc(100% - 42px);
  }

  .message-bubble {
    padding: 10px 12px;
    font-size: 13px;
  }

  .composer {
    padding: 10px 10px 8px;
  }

  .composer-shell {
    padding-right: 94px;
  }

  .composer-actions :deep(.el-button.is-text) {
    padding: 6px;
  }

  .composer-actions :deep(.el-button.is-text span) {
    display: none;
  }
}
</style>
