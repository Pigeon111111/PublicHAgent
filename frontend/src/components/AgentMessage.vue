<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  content: string
  renderMarkdown?: (content: string) => string
  isStreaming?: boolean
}>()

const renderedContent = computed(() => {
  if (props.renderMarkdown) {
    return props.renderMarkdown(props.content)
  }
  return props.content
})
</script>

<template>
  <div class="agent-message" :class="{ streaming: isStreaming }">
    <div class="message-avatar">
      <el-icon :size="24"><Robot /></el-icon>
    </div>
    <div class="message-content">
      <div class="message-bubble" v-html="renderedContent" />
    </div>
  </div>
</template>

<style scoped>
.agent-message {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.message-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background-color: #67c23a;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
}

.message-content {
  max-width: 70%;
}

.message-bubble {
  padding: 12px 16px;
  background-color: white;
  border-radius: 8px;
  word-wrap: break-word;
  white-space: pre-wrap;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.streaming {
  opacity: 0.7;
}

.message-bubble :deep(pre) {
  background-color: #282c34;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 8px 0;
}

.message-bubble :deep(code) {
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 14px;
}

.message-bubble :deep(p) {
  margin: 8px 0;
}

.message-bubble :deep(p:first-child) {
  margin-top: 0;
}

.message-bubble :deep(p:last-child) {
  margin-bottom: 0;
}

.message-bubble :deep(ul),
.message-bubble :deep(ol) {
  padding-left: 20px;
  margin: 8px 0;
}

.message-bubble :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
}

.message-bubble :deep(th),
.message-bubble :deep(td) {
  border: 1px solid #e4e7ed;
  padding: 8px;
  text-align: left;
}

.message-bubble :deep(th) {
  background-color: #f5f7fa;
}
</style>
