<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useChatStore } from '@/stores'
import ChatWindow from '@/components/ChatWindow.vue'
import { connectWebSocket, disconnectWebSocket, sendMessage, interruptExecution } from '@/services/websocket'
import type { TaskEvent, WebSocketMessage } from '@/types'

const chatStore = useChatStore()
const sessionId = ref(`session_${Date.now()}`)

onMounted(async () => {
  await connectWebSocket(
    sessionId.value,
    handleMessage,
    (connected) => chatStore.setConnected(connected),
  )
})

onUnmounted(() => {
  disconnectWebSocket()
})

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
        })
        chatStore.addTaskEvent(createEvent('agent', 'Agent 输出', '已生成最终结果', {
          timestamp: message.timestamp,
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
  }

  if (status === 'completed' || status === 'interrupted' || status === 'error') {
    chatStore.setProcessing(false)
  }

  chatStore.addTaskEvent(createEvent('status', status, message, { timestamp }))
}

function handleSend(content: string) {
  chatStore.clearTaskEvents()
  chatStore.addMessage({
    role: 'user',
    content,
    timestamp: new Date().toISOString(),
  })
  chatStore.setProcessing(true)
  chatStore.setInterruptRequested(false)
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

function handleInterrupt() {
  chatStore.setInterruptRequested(true)
  chatStore.addTaskEvent(createEvent('status', '请求中断', '正在请求后端停止当前任务'))
  const sent = interruptExecution()
  if (!sent) {
    chatStore.setInterruptRequested(false)
    ElMessage.error('WebSocket 未连接，无法中断任务')
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
      @send="handleSend"
      @interrupt="handleInterrupt"
    />
  </div>
</template>

<style scoped>
.chat-view {
  height: calc(100vh - 60px);
  background-color: #f6f7f9;
}
</style>
