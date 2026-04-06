<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useChatStore } from '@/stores'
import ChatWindow from '@/components/ChatWindow.vue'
import { connectWebSocket, disconnectWebSocket, sendMessage, interruptExecution } from '@/services/websocket'

const chatStore = useChatStore()
const sessionId = ref(`session_${Date.now()}`)

onMounted(async () => {
  await connectWebSocket(sessionId.value, (message) => {
    handleMessage(message)
  })
})

onUnmounted(() => {
  disconnectWebSocket()
})

function handleMessage(message: unknown) {
  const msg = message as Record<string, unknown>
  const type = msg.type as string

  switch (type) {
    case 'status':
      chatStore.setConnected((msg.status as string) === 'connected')
      break
    case 'progress':
      chatStore.updateProgress(msg.progress as number, msg.stage as string)
      break
    case 'agent':
      if (msg.is_streaming) {
        chatStore.appendStreamContent(msg.content as string)
      } else {
        chatStore.addMessage({
          role: 'assistant',
          content: msg.content as string,
          timestamp: msg.timestamp as string,
        })
        chatStore.setProcessing(false)
        chatStore.clearStreamContent()
      }
      break
    case 'error':
      chatStore.addMessage({
        role: 'system',
        content: `错误: ${msg.error_message}`,
        timestamp: msg.timestamp as string,
      })
      chatStore.setProcessing(false)
      break
  }
}

function handleSend(content: string) {
  chatStore.addMessage({
    role: 'user',
    content,
    timestamp: new Date().toISOString(),
  })
  chatStore.setProcessing(true)
  sendMessage({
    type: 'user',
    session_id: sessionId.value,
    content,
    user_id: 'default',
    context: {},
  })
}

function handleInterrupt() {
  interruptExecution()
  chatStore.setProcessing(false)
}
</script>

<template>
  <div class="chat-view">
    <el-container>
      <el-header class="chat-header">
        <h2>智能对话</h2>
        <div class="header-status">
          <el-tag :type="chatStore.isConnected ? 'success' : 'danger'">
            {{ chatStore.isConnected ? '已连接' : '未连接' }}
          </el-tag>
        </div>
      </el-header>
      <el-main class="chat-main">
        <ChatWindow
          :messages="chatStore.messages"
          :is-processing="chatStore.isProcessing"
          :progress="chatStore.currentProgress"
          :stage="chatStore.currentStage"
          :streaming-content="chatStore.streamingContent"
          @send="handleSend"
          @interrupt="handleInterrupt"
        />
      </el-main>
    </el-container>
  </div>
</template>

<style scoped>
.chat-view {
  height: 100vh;
  background-color: #f5f7fa;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: white;
  border-bottom: 1px solid #e4e7ed;
  padding: 0 24px;
}

.chat-header h2 {
  font-size: 20px;
  color: #303133;
}

.chat-main {
  padding: 0;
  height: calc(100vh - 60px);
}
</style>
