<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js'
import UserMessage from './UserMessage.vue'
import AgentMessage from './AgentMessage.vue'
import SystemMessage from './SystemMessage.vue'
import type { Message, TaskEvent } from '@/types'

const props = defineProps<{
  messages: Message[]
  isProcessing: boolean
  progress: number
  stage: string
  streamingContent: string
  taskEvents: TaskEvent[]
  isConnected: boolean
  lastError: string
  interruptRequested: boolean
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

const connectionText = computed(() => props.isConnected ? '已连接' : '未连接')
const runText = computed(() => {
  if (props.interruptRequested) return '正在中断'
  if (props.isProcessing) return '运行中'
  return '空闲'
})

function renderMarkdown(content: string): string {
  return marked(content) as string
}

function formatTime(timestamp: string): string {
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}

function handleSend() {
  if (!inputContent.value.trim() || props.isProcessing || !props.isConnected) return
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
    <main class="chat-main">
      <div
        ref="messagesContainer"
        class="messages-container"
      >
        <div
          v-if="messages.length === 0"
          class="empty-state"
        >
          <el-icon :size="56">
            <ChatDotRound />
          </el-icon>
          <p>发送数据分析需求，系统会自动规划、执行、校验并沉淀可复用 Skill。</p>
        </div>

        <template
          v-for="(msg, index) in messages"
          :key="index"
        >
          <UserMessage
            v-if="msg.role === 'user'"
            :content="msg.content"
          />
          <AgentMessage
            v-else-if="msg.role === 'assistant'"
            :content="msg.content"
            :render-markdown="renderMarkdown"
          />
          <SystemMessage
            v-else
            :content="msg.content"
          />
        </template>

        <div
          v-if="streamingContent"
          class="streaming-message"
        >
          <AgentMessage
            :content="streamingContent"
            :render-markdown="renderMarkdown"
            :is-streaming="true"
          />
        </div>

        <div
          v-if="isProcessing && !streamingContent"
          class="processing-indicator"
        >
          <el-progress
            :percentage="progress"
            :status="progress === 100 ? 'success' : undefined"
          />
          <p class="stage-text">
            {{ stage || '正在准备执行' }}
          </p>
        </div>
      </div>

      <div class="input-area">
        <el-input
          v-model="inputContent"
          type="textarea"
          :rows="3"
          placeholder="输入分析目标，例如：读取上传的 CSV，尝试 Kaplan-Meier 生存分析，失败后自动修正并复用成功路径"
          :disabled="isProcessing || !isConnected"
          @keydown="handleKeydown"
        />
        <div class="input-actions">
          <el-button
            v-if="isProcessing"
            type="danger"
            :loading="interruptRequested"
            @click="emit('interrupt')"
          >
            <el-icon><VideoPause /></el-icon>
            停止
          </el-button>
          <el-button
            type="primary"
            :disabled="!inputContent.trim() || isProcessing || !isConnected"
            @click="handleSend"
          >
            <el-icon><Promotion /></el-icon>
            发送
          </el-button>
        </div>
      </div>
    </main>

    <aside class="task-panel">
      <section class="status-section">
        <div class="status-row">
          <span>连接</span>
          <strong :class="{ ok: isConnected }">{{ connectionText }}</strong>
        </div>
        <div class="status-row">
          <span>任务</span>
          <strong>{{ runText }}</strong>
        </div>
        <div
          v-if="lastError"
          class="error-text"
        >
          {{ lastError }}
        </div>
      </section>

      <section class="progress-section">
        <div class="section-title">
          执行进度
        </div>
        <el-progress :percentage="progress" />
        <p>{{ stage || '等待任务' }}</p>
      </section>

      <section class="events-section">
        <div class="section-title">
          运行日志
        </div>
        <el-empty
          v-if="taskEvents.length === 0"
          description="暂无事件"
          :image-size="72"
        />
        <ol
          v-else
          class="event-list"
        >
          <li
            v-for="event in taskEvents"
            :key="event.id"
            class="event-item"
          >
            <div class="event-meta">
              <span class="event-type">{{ event.type }}</span>
              <time>{{ formatTime(event.timestamp) }}</time>
            </div>
            <strong>{{ event.title }}</strong>
            <p>{{ event.message }}</p>
          </li>
        </ol>
      </section>
    </aside>
  </div>
</template>

<style scoped>
.chat-window {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  height: 100%;
  background-color: #f6f7f9;
  color: #1f2933;
}

.chat-main {
  display: flex;
  min-width: 0;
  flex-direction: column;
  border-right: 1px solid #d9dee7;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.empty-state {
  display: flex;
  height: 100%;
  max-width: 640px;
  margin: 0 auto;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #5f6b7a;
  text-align: center;
}

.empty-state p {
  margin-top: 16px;
  font-size: 16px;
  line-height: 1.7;
}

.streaming-message {
  opacity: 0.78;
}

.processing-indicator {
  padding: 16px;
  text-align: center;
}

.stage-text {
  margin-top: 8px;
  color: #5f6b7a;
  font-size: 14px;
}

.input-area {
  padding: 16px 20px;
  background-color: #ffffff;
  border-top: 1px solid #d9dee7;
}

.input-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 12px;
}

.task-panel {
  display: flex;
  min-width: 0;
  flex-direction: column;
  overflow: hidden;
  background-color: #ffffff;
}

.status-section,
.progress-section,
.events-section {
  padding: 16px;
  border-bottom: 1px solid #d9dee7;
}

.events-section {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.status-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
  font-size: 14px;
}

.status-row strong {
  color: #8a4b08;
}

.status-row strong.ok {
  color: #1f7a4d;
}

.error-text {
  color: #c2410c;
  font-size: 13px;
  line-height: 1.5;
}

.section-title {
  margin-bottom: 12px;
  font-weight: 700;
  color: #111827;
}

.progress-section p {
  margin: 10px 0 0;
  color: #5f6b7a;
  font-size: 13px;
}

.event-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.event-item {
  padding: 12px;
  border: 1px solid #d9dee7;
  border-radius: 8px;
  background-color: #fbfcfd;
}

.event-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
  color: #6b7280;
  font-size: 12px;
}

.event-type {
  text-transform: uppercase;
}

.event-item strong {
  display: block;
  margin-bottom: 4px;
  color: #111827;
  font-size: 14px;
}

.event-item p {
  margin: 0;
  color: #4b5563;
  font-size: 13px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

@media (max-width: 900px) {
  .chat-window {
    grid-template-columns: 1fr;
    grid-template-rows: minmax(0, 1fr) 280px;
  }

  .chat-main {
    border-right: none;
    border-bottom: 1px solid #d9dee7;
  }
}
</style>
