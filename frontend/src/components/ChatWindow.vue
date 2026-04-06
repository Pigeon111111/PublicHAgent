<script setup lang="ts">
import { ref, nextTick, watch, onMounted } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js'
import UserMessage from './UserMessage.vue'
import AgentMessage from './AgentMessage.vue'
import SystemMessage from './SystemMessage.vue'
import type { Message } from '@/types'

const props = defineProps<{
  messages: Message[]
  isProcessing: boolean
  progress: number
  stage: string
  streamingContent: string
}>()

const emit = defineEmits<{
  send: [content: string]
  interrupt: []
}>()

const inputContent = ref('')
const messagesContainer = ref<HTMLElement | null>(null)

const renderer = new marked.Renderer()
renderer.code = function(code: string, infostring: string | undefined): string {
  let highlighted: string
  if (infostring && hljs.getLanguage(infostring)) {
    highlighted = hljs.highlight(code, { language: infostring }).value
  } else {
    highlighted = hljs.highlightAuto(code).value
  }
  return `<pre><code class="hljs">${highlighted}</code></pre>`
}

marked.setOptions({
  renderer,
  breaks: true,
})

function renderMarkdown(content: string): string {
  return marked(content) as string
}

function handleSend() {
  if (!inputContent.value.trim() || props.isProcessing) return
  emit('send', inputContent.value.trim())
  inputContent.value = ''
}

function handleKeydown(e: Event | KeyboardEvent) {
  if ('key' in e && e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

watch(() => props.messages.length, scrollToBottom)
watch(() => props.streamingContent, scrollToBottom)
onMounted(scrollToBottom)
</script>

<template>
  <div class="chat-window">
    <div class="messages-container" ref="messagesContainer">
      <div v-if="messages.length === 0" class="empty-state">
        <el-icon :size="64"><ChatDotRound /></el-icon>
        <p>开始您的数据分析对话</p>
      </div>
      <template v-for="(msg, index) in messages" :key="index">
        <UserMessage v-if="msg.role === 'user'" :content="msg.content" />
        <AgentMessage v-else-if="msg.role === 'assistant'" :content="msg.content" :render-markdown="renderMarkdown" />
        <SystemMessage v-else :content="msg.content" />
      </template>
      <div v-if="streamingContent" class="streaming-message">
        <AgentMessage :content="streamingContent" :render-markdown="renderMarkdown" :is-streaming="true" />
      </div>
      <div v-if="isProcessing && !streamingContent" class="processing-indicator">
        <el-progress :percentage="progress" :status="progress === 100 ? 'success' : undefined" />
        <p class="stage-text">{{ stage }}</p>
      </div>
    </div>
    <div class="input-area">
      <el-input
        v-model="inputContent"
        type="textarea"
        :rows="3"
        placeholder="请输入您的问题..."
        :disabled="isProcessing"
        @keydown="handleKeydown"
      />
      <div class="input-actions">
        <el-button
          v-if="isProcessing"
          type="danger"
          @click="emit('interrupt')"
        >
          <el-icon><VideoPause /></el-icon>
          停止
        </el-button>
        <el-button
          type="primary"
          :disabled="!inputContent.trim() || isProcessing"
          @click="handleSend"
        >
          <el-icon><Promotion /></el-icon>
          发送
        </el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-window {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: #f5f7fa;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #909399;
}

.empty-state p {
  margin-top: 16px;
  font-size: 16px;
}

.streaming-message {
  opacity: 0.7;
}

.processing-indicator {
  padding: 16px;
  text-align: center;
}

.stage-text {
  margin-top: 8px;
  color: #909399;
  font-size: 14px;
}

.input-area {
  padding: 16px 20px;
  background-color: white;
  border-top: 1px solid #e4e7ed;
}

.input-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 12px;
}
</style>
