<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import { get, getEnvelope, patch, post, postStream } from '@/api/client'
import StatusTag from '@/components/StatusTag.vue'
import type { QaCitationItem, QaMessageItem, QaSessionItem } from '@/types'
import { errorMessage, shortTime } from '@/utils/display'
import { applyQaStreamEvent, inlineQaCitations } from '@/utils/qa'

const loadingSessions = ref(false)
const loadingMessages = ref(false)
const streaming = ref(false)
const sessions = ref<QaSessionItem[]>([])
const messages = ref<QaMessageItem[]>([])
const selectedSession = ref<QaSessionItem | null>(null)
const question = ref('')
const sessionQuery = ref('')
const messagePane = ref<HTMLElement>()
const citationVisible = ref(false)
const citationLoading = ref(false)
const activeCitations = ref<QaCitationItem[]>([])
const sessionPagination = reactive({ page: 1, page_size: 20, total: 0 })
let sessionSearchTimer: number | undefined

const askDisabled = computed(() => streaming.value || !question.value.trim())
const selectedTitle = computed(() => selectedSession.value?.title || '未命名会话')

function buildSessionQuery(): string {
  const params = new URLSearchParams()
  params.set('page', String(sessionPagination.page))
  params.set('page_size', String(sessionPagination.page_size))
  if (sessionQuery.value.trim()) params.set('q', sessionQuery.value.trim())
  return `?${params}`
}

function applySessionPagination(meta?: { page?: number; page_size?: number; total?: number }): void {
  sessionPagination.page = Number(meta?.page ?? sessionPagination.page)
  sessionPagination.page_size = Number(meta?.page_size ?? sessionPagination.page_size)
  sessionPagination.total = Number(meta?.total ?? sessions.value.length)
}

function localId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function citationStatus(citation: QaCitationItem): string | null | undefined {
  return citation.current_status ?? citation.status
}

async function scrollToBottom(): Promise<void> {
  await nextTick()
  if (messagePane.value) messagePane.value.scrollTop = messagePane.value.scrollHeight
}

async function loadSessions(keepSelection = true): Promise<void> {
  loadingSessions.value = true
  try {
    const payload = await getEnvelope<QaSessionItem[]>(`/api/v1/qa/sessions${buildSessionQuery()}`)
    sessions.value = payload.data
    applySessionPagination(payload.meta ?? payload)
    if (keepSelection && selectedSession.value) {
      selectedSession.value = sessions.value.find((item) => item.id === selectedSession.value?.id) ?? selectedSession.value
    } else if (!selectedSession.value && sessions.value.length) {
      await openSession(sessions.value[0])
    }
  } catch (error) {
    ElMessage.warning(errorMessage(error))
  } finally {
    loadingSessions.value = false
  }
}

async function loadMessages(sessionId: string): Promise<void> {
  loadingMessages.value = true
  try {
    messages.value = await get<QaMessageItem[]>(`/api/v1/qa/sessions/${sessionId}/messages`)
    await scrollToBottom()
  } catch (error) {
    ElMessage.warning(errorMessage(error))
  } finally {
    loadingMessages.value = false
  }
}

async function openSession(session: QaSessionItem): Promise<void> {
  selectedSession.value = session
  await loadMessages(session.id)
}

function searchSessions(): void {
  sessionPagination.page = 1
  void loadSessions(false)
}

function queueSearchSessions(): void {
  if (sessionSearchTimer) window.clearTimeout(sessionSearchTimer)
  sessionSearchTimer = window.setTimeout(searchSessions, 300)
}

function changeSessionPage(page: number): void {
  sessionPagination.page = page
  void loadSessions()
}

async function createSession(title = ''): Promise<QaSessionItem | null> {
  try {
    const session = await post<QaSessionItem>('/api/v1/qa/sessions', { title: title || null })
    selectedSession.value = session
    messages.value = []
    await loadSessions()
    return session
  } catch (error) {
    ElMessage.error(errorMessage(error))
    return null
  }
}

async function promptCreateSession(): Promise<void> {
  const result = await ElMessageBox.prompt('给新会话起一个标题，也可以留空。', '新建问数会话', {
    inputPlaceholder: '例如：本周农业信息摘要',
  }).catch(() => null)
  if (result) await createSession(result.value)
}

async function renameSession(): Promise<void> {
  if (!selectedSession.value) return
  const result = await ElMessageBox.prompt('修改当前会话标题。', '重命名会话', {
    inputValue: selectedSession.value.title ?? '',
  }).catch(() => null)
  if (!result) return
  try {
    selectedSession.value = await patch<QaSessionItem>(`/api/v1/qa/sessions/${selectedSession.value.id}`, { title: result.value || null })
    await loadSessions()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function archiveSession(): Promise<void> {
  if (!selectedSession.value) return
  try {
    await ElMessageBox.confirm(`确认归档会话「${selectedTitle.value}」？`, '归档会话', { type: 'warning' })
    await patch<QaSessionItem>(`/api/v1/qa/sessions/${selectedSession.value.id}`, { status: 'archived' })
    selectedSession.value = null
    messages.value = []
    await loadSessions(false)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(errorMessage(error))
  }
}

async function askQuestion(): Promise<void> {
  const text = question.value.trim()
  if (!text || streaming.value) return
  let active = selectedSession.value
  if (!active) active = await createSession(text.slice(0, 30))
  if (!active) return

  question.value = ''
  const userMessage: QaMessageItem = {
    id: localId('question'),
    session_id: active.id,
    role: 'user',
    content: text,
    status: 'completed',
  }
  const answerMessage: QaMessageItem = {
    id: localId('answer'),
    session_id: active.id,
    role: 'assistant',
    content: '',
    status: 'streaming',
    citations: [],
  }
  messages.value.push(userMessage, answerMessage)
  await scrollToBottom()

  streaming.value = true
  try {
    await postStream(`/api/v1/qa/sessions/${active.id}/questions/stream`, { question: text }, ({ event, data }) => {
      applyQaStreamEvent(answerMessage, event, data)
      if (event === 'delta') {
        void scrollToBottom()
      }
    })
    if (answerMessage.status === 'streaming') answerMessage.status = 'completed'
    await loadMessages(active.id).catch(() => undefined)
    await loadSessions()
  } catch (error) {
    answerMessage.status = 'failed'
    answerMessage.error_summary = errorMessage(error)
    if (!answerMessage.content) answerMessage.content = answerMessage.error_summary
    ElMessage.error(answerMessage.error_summary)
  } finally {
    streaming.value = false
    await scrollToBottom()
  }
}

async function openCitations(message: QaMessageItem): Promise<void> {
  citationVisible.value = true
  citationLoading.value = true
  activeCitations.value = inlineQaCitations(message)
  try {
    if (!activeCitations.value.length) {
      activeCitations.value = await get<QaCitationItem[]>(`/api/v1/qa/messages/${message.id}/citations`)
    }
  } catch (error) {
    ElMessage.warning(errorMessage(error))
  } finally {
    citationLoading.value = false
  }
}

onMounted(() => {
  void loadSessions()
})

onBeforeUnmount(() => {
  if (sessionSearchTimer) window.clearTimeout(sessionSearchTimer)
})
</script>

<template>
  <section class="qa-workbench">
    <aside class="qa-sessions">
      <div class="qa-sessions-head">
        <div>
          <p class="page-eyebrow">QUESTION ANSWERING</p>
          <h1>智能问数</h1>
        </div>
        <el-button type="primary" @click="promptCreateSession">新建</el-button>
      </div>
      <el-input v-model="sessionQuery" clearable placeholder="搜索会话" @input="queueSearchSessions" @keyup.enter="searchSessions" />
      <div v-loading="loadingSessions" class="qa-session-list">
        <button
          v-for="session in sessions"
          :key="session.id"
          class="qa-session-item"
          :class="{ active: session.id === selectedSession?.id }"
          type="button"
          @click="openSession(session)"
        >
          <strong>{{ session.title || '未命名会话' }}</strong>
          <span>{{ shortTime(session.updated_at) }}</span>
          <status-tag :value="session.status" />
        </button>
        <el-empty v-if="!sessions.length && !loadingSessions" description="暂无会话" />
      </div>
      <el-pagination
        small
        layout="prev, pager, next"
        :current-page="sessionPagination.page"
        :page-size="sessionPagination.page_size"
        :total="sessionPagination.total"
        @current-change="changeSessionPage"
      />
    </aside>

    <main class="qa-panel">
      <header class="qa-panel-head">
        <div>
          <h2>{{ selectedTitle }}</h2>
          <p>回答只使用已治理为 available 的内容，引用由服务端检索后固定保存。</p>
        </div>
        <div class="qa-panel-actions">
          <el-button :disabled="!selectedSession" @click="renameSession">重命名</el-button>
          <el-button :disabled="!selectedSession" @click="archiveSession">归档</el-button>
        </div>
      </header>

      <section ref="messagePane" v-loading="loadingMessages" class="qa-messages">
        <el-empty v-if="!selectedSession && !messages.length" description="新建会话或直接输入问题开始问数" />
        <article
          v-for="message in messages"
          :key="message.id"
          class="qa-message"
          :class="message.role === 'user' ? 'from-user' : 'from-assistant'"
        >
          <div class="qa-message-meta">
            <span>{{ message.role === 'user' ? '我' : '智能问数' }}</span>
            <status-tag v-if="message.role === 'assistant'" :value="message.status" />
          </div>
          <p class="qa-message-content">{{ message.content || (message.status === 'streaming' ? '正在生成回答...' : '-') }}</p>
          <p v-if="message.error_summary" class="qa-message-error">{{ message.error_summary }}</p>
          <div v-if="message.role === 'assistant' && message.citations?.length" class="qa-citation-strip">
            <button v-for="citation in message.citations" :key="`${message.id}-${citation.knowledge_item_id}`" type="button" @click="openCitations(message)">
              <strong>[{{ citation.rank }}] {{ citation.title || citation.knowledge_item_id }}</strong>
              <span>{{ citation.source_name || '未知来源' }}</span>
            </button>
          </div>
          <el-button v-if="message.role === 'assistant' && message.status === 'completed'" link type="primary" @click="openCitations(message)">
            查看引用
          </el-button>
        </article>
      </section>

      <footer class="qa-composer">
        <el-input
          v-model="question"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 5 }"
          resize="none"
          placeholder="输入问题，系统会基于可用数据内容生成带引用的回答"
          @keydown.ctrl.enter.prevent="askQuestion"
        />
        <el-button type="primary" :loading="streaming" :disabled="askDisabled" @click="askQuestion">发送</el-button>
      </footer>
    </main>

    <el-drawer v-model="citationVisible" title="回答引用" size="560px">
      <el-skeleton v-if="citationLoading" :rows="6" animated />
      <div v-else class="qa-citation-list">
        <article v-for="citation in activeCitations" :key="`${citation.rank}-${citation.knowledge_item_id}`" class="qa-citation-card">
          <div class="qa-citation-title">
            <strong>[{{ citation.rank }}] {{ citation.title || citation.knowledge_item_id }}</strong>
            <status-tag v-if="citationStatus(citation)" :value="citationStatus(citation)" />
          </div>
          <p>{{ citation.source_name || '未知来源' }}</p>
          <blockquote>{{ citation.excerpt }}</blockquote>
        </article>
        <el-empty v-if="!activeCitations.length" description="当前回答没有引用" />
      </div>
    </el-drawer>
  </section>
</template>
