<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useChatStore } from '@/stores'
import ChatWindow from '@/components/ChatWindow.vue'
import {
  connectWebSocket,
  disconnectWebSocket,
  fetchSessionStatus,
  interruptExecution,
  resumeExecution,
  sendMessage,
} from '@/services/websocket'
import type { SessionStatusResponse, TaskEvent, WebSocketMessage } from '@/types'

const chatStore = useChatStore()
const route = useRoute()
const router = useRouter()
const SESSION_STORAGE_KEY = 'pubhagent_session_id'
const sessionId = ref(resolveSessionId())
const handledRouteAction = ref('')

onMounted(async () => {
  await connectCurrentSession()
  await maybeRunRouteAction()
})

onUnmounted(() => {
  disconnectWebSocket()
})

watch(
  () => route.fullPath,
  async () => {
    const nextSessionId = resolveSessionId()
    if (nextSessionId !== sessionId.value) {
      sessionId.value = nextSessionId
      chatStore.clearMessages()
      await connectCurrentSession()
    }
    await maybeRunRouteAction()
  },
)

function resolveSessionId(): string {
  const querySessionId = typeof route.query.sessionId === 'string' ? route.query.sessionId : ''
  if (querySessionId) {
    window.sessionStorage.setItem(SESSION_STORAGE_KEY, querySessionId)
    return querySessionId
  }
  const saved = window.sessionStorage.getItem(SESSION_STORAGE_KEY)
  if (saved) {
    return saved
  }
  const created = `session_${Date.now()}`
  window.sessionStorage.setItem(SESSION_STORAGE_KEY, created)
  return created
}

async function connectCurrentSession() {
  chatStore.setCurrentSessionId(sessionId.value)
  await connectWebSocket(
    sessionId.value,
    handleMessage,
    (connected) => chatStore.setConnected(connected),
  )
  await syncSessionStatus()
}

function createEvent(
  type: TaskEvent['type'],
  title: string,
  message: string,
  extra: Partial<TaskEvent> = {},
): TaskEvent {
  return {
    id: `${Date.now()}_${Math.random().toString(36).slice(2)}`,
    type,
    title,
    message,
    timestamp: new Date().toISOString(),
    ...extra,
  }
}

function handleMessage(message: WebSocketMessage) {
  switch (message.type) {
    case 'status':
      handleStatusMessage(message.status, message.message, message.timestamp)
      break
    case 'progress':
      chatStore.updateProgress(message.progress, message.stage)
      chatStore.addTaskEvent(createEvent('progress', message.stage, message.message, {
        timestamp: message.timestamp,
        progress: message.progress,
        stage: message.stage,
        details: message.details,
      }))
      break
    case 'agent':
      if (message.is_streaming) {
        chatStore.appendStreamContent(message.content)
      } else {
        chatStore.addMessage({
          role: 'assistant',
          content: message.content,
          timestamp: message.timestamp,
          evaluation_report: message.evaluation_report,
          task_family: message.task_family,
          evaluation_score: message.evaluation_score,
          analysis_id: message.analysis_id,
          trajectory_id: message.trajectory_id,
        })
        if (message.analysis_id) {
          chatStore.setLastAnalysisId(message.analysis_id)
        }
        chatStore.addTaskEvent(createEvent('agent', 'Agent 输出', '已生成最终结果', {
          timestamp: message.timestamp,
          details: {
            analysis_id: message.analysis_id,
            evaluation_report: message.evaluation_report,
          },
        }))
        chatStore.clearStreamContent()
      }
      break
    case 'error':
      chatStore.setLastError(message.error_message)
      chatStore.addMessage({
        role: 'system',
        content: `错误: ${message.error_message}`,
        timestamp: message.timestamp,
      })
      chatStore.addTaskEvent(createEvent('error', message.error_code, message.error_message, {
        timestamp: message.timestamp,
        details: message.details,
      }))
      chatStore.setProcessing(false)
      break
  }
}

function handleStatusMessage(status: string, message: string, timestamp: string) {
  if (status === 'connected') {
    chatStore.setConnected(true)
  }
  if (status === 'processing') {
    chatStore.setProcessing(true)
    chatStore.setCanResume(false)
  }
  if (status === 'completed' || status === 'interrupted' || status === 'error') {
    chatStore.setProcessing(false)
  }
  if (status === 'interrupted') {
    chatStore.setCanResume(true)
  }
  if (status === 'completed') {
    chatStore.setCanResume(false)
  }
  chatStore.addTaskEvent(createEvent('status', status, message, { timestamp }))
}

async function syncSessionStatus() {
  try {
    const status = await fetchSessionStatus(sessionId.value)
    applySessionStatus(status)
  } catch {
    chatStore.setLastError('获取会话状态失败')
  }
}

function applySessionStatus(status: SessionStatusResponse | null) {
  if (!status) return
  chatStore.setCanResume(Boolean(status.checkpoint?.resumable))
  if (status.last_error) {
    chatStore.setLastError(status.last_error)
  }
  if (status.current_analysis_id) {
    chatStore.setLastAnalysisId(status.current_analysis_id)
  }
}

function sendUserMessage(content: string) {
  chatStore.clearTaskEvents()
  chatStore.addMessage({
    role: 'user',
    content,
    timestamp: new Date().toISOString(),
  })
  chatStore.setProcessing(true)
  chatStore.setInterruptRequested(false)
  chatStore.setCanResume(false)
  const sent = sendMessage({
    type: 'user',
    session_id: sessionId.value,
    content,
    user_id: 'default',
    context: {},
  })
  if (!sent) {
    chatStore.setProcessing(false)
    ElMessage.error('WebSocket 未连接，无法发送请求')
  }
}

async function maybeRunRouteAction() {
  const action = typeof route.query.action === 'string' ? route.query.action : ''
  const query = typeof route.query.query === 'string' ? route.query.query : ''
  const actionKey = `${sessionId.value}:${action}:${query}:${String(route.query.analysisId || '')}`
  if (!action || handledRouteAction.value === actionKey) {
    return
  }
  handledRouteAction.value = actionKey

  if (action === 'resume') {
    chatStore.setProcessing(true)
    chatStore.setInterruptRequested(false)
    const sent = resumeExecution()
    if (!sent) {
      chatStore.setProcessing(false)
      ElMessage.error('WebSocket 未连接，无法恢复任务')
      return
    }
  } else if (action === 'rerun' && query) {
    sendUserMessage(query)
  }

  await router.replace({ path: '/chat' })
}

function handleSend(content: string) {
  sendUserMessage(content)
}

function handleInterrupt() {
  chatStore.setInterruptRequested(true)
  chatStore.addTaskEvent(createEvent('status', '请求中断', '正在请求后端停止当前任务'))
  const sent = interruptExecution()
  if (!sent) {
    chatStore.setInterruptRequested(false)
    ElMessage.error('WebSocket 未连接，无法中断任务')
  }
}

function handleResume() {
  chatStore.setProcessing(true)
  chatStore.setInterruptRequested(false)
  const sent = resumeExecution()
  if (!sent) {
    chatStore.setProcessing(false)
    ElMessage.error('WebSocket 未连接，无法恢复任务')
  }
}
</script>

<template>
  <div class="chat-view">
    <ChatWindow
      :messages="chatStore.messages"
      :is-processing="chatStore.isProcessing"
      :progress="chatStore.currentProgress"
      :stage="chatStore.currentStage"
      :streaming-content="chatStore.streamingContent"
      :task-events="chatStore.taskEvents"
      :is-connected="chatStore.isConnected"
      :last-error="chatStore.lastError"
      :interrupt-requested="chatStore.interruptRequested"
      :can-resume="chatStore.canResume"
      @send="handleSend"
      @interrupt="handleInterrupt"
      @resume="handleResume"
    />
  </div>
</template>

<style scoped>
.chat-view {
  height: calc(100vh - 60px);
  background-color: #f6f7f9;
}
</style>
