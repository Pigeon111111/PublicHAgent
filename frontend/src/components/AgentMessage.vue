<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { promoteAnalysisVariant, rerunAnalysis } from '@/services/api'
import type { Message } from '@/types'

const props = defineProps<{
  message: Message
  renderMarkdown?: (content: string) => string
  isStreaming?: boolean
}>()

const router = useRouter()
const promoting = ref(false)
const rerunning = ref(false)

const renderedContent = computed(() => {
  if (props.renderMarkdown) {
    return props.renderMarkdown(props.message.content)
  }
  return props.message.content
})

const evaluationSummary = computed(() => props.message.evaluation_report)

async function handlePromoteVariant() {
  if (!props.message.analysis_id || promoting.value) return
  promoting.value = true
  try {
    const response = await promoteAnalysisVariant(props.message.analysis_id)
    ElMessage.success(`已学习为新细分方法：${response.variant}`)
    await router.push(`/methods?family=${response.family}&variant=${response.skill_name}`)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '学习新细分方法失败')
  } finally {
    promoting.value = false
  }
}

async function handleRerun() {
  if (!props.message.analysis_id || rerunning.value) return
  rerunning.value = true
  try {
    const response = await rerunAnalysis(props.message.analysis_id)
    await router.push({
      path: '/chat',
      query: {
        sessionId: response.session_id,
        query: response.query,
        action: response.resume_available ? 'resume' : 'rerun',
        analysisId: response.analysis_id,
      },
    })
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '重新运行失败')
  } finally {
    rerunning.value = false
  }
}

function openEvaluation() {
  if (!props.message.analysis_id) return
  router.push(`/history?analysisId=${props.message.analysis_id}`)
}
</script>

<template>
  <div
    class="agent-message"
    :class="{ streaming: isStreaming }"
  >
    <div class="message-avatar">
      <el-icon :size="24">
        <Robot />
      </el-icon>
    </div>
    <div class="message-content">
      <div
        class="message-bubble"
        v-html="renderedContent"
      />

      <el-card
        v-if="evaluationSummary"
        class="evaluation-card"
        shadow="never"
      >
        <div class="evaluation-header">
          <div>
            <strong>结果评估</strong>
            <div class="evaluation-meta">
              <span>{{ evaluationSummary.task_family || message.task_family || 'general' }}</span>
              <el-tag :type="evaluationSummary.passed ? 'success' : 'danger'">
                {{ evaluationSummary.passed ? '通过' : '未通过' }}
              </el-tag>
            </div>
          </div>
          <div class="score-chip">
            {{ ((message.evaluation_score ?? evaluationSummary.final_score) * 100).toFixed(0) }} 分
          </div>
        </div>

        <p class="evaluation-summary">
          {{ evaluationSummary.summary || '暂无评估摘要' }}
        </p>

        <ul
          v-if="evaluationSummary.hard_failures?.length"
          class="failure-list"
        >
          <li
            v-for="item in evaluationSummary.hard_failures.slice(0, 3)"
            :key="item"
          >
            {{ item }}
          </li>
        </ul>

        <div class="evaluation-actions">
          <el-button
            size="small"
            @click="openEvaluation"
          >
            进入审阅
          </el-button>
          <el-button
            size="small"
            :loading="rerunning"
            @click="handleRerun"
          >
            重新运行
          </el-button>
          <el-button
            v-if="message.analysis_id"
            size="small"
            type="primary"
            plain
            :loading="promoting"
            @click="handlePromoteVariant"
          >
            学习为新变体
          </el-button>
        </div>
      </el-card>
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
  background: linear-gradient(135deg, #1f7a4d, #0f5c3c);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
}

.message-content {
  max-width: min(78%, 920px);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message-bubble {
  padding: 12px 16px;
  background-color: white;
  border-radius: 12px;
  word-wrap: break-word;
  white-space: pre-wrap;
  box-shadow: 0 2px 4px rgba(15, 23, 42, 0.08);
}

.streaming {
  opacity: 0.7;
}

.evaluation-card {
  border-radius: 12px;
  border: 1px solid #dbe7df;
  background: linear-gradient(180deg, #ffffff, #f4fbf7);
}

.evaluation-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.evaluation-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  color: #52606d;
  font-size: 13px;
}

.score-chip {
  min-width: 64px;
  padding: 6px 10px;
  border-radius: 999px;
  background-color: #0f5c3c;
  color: white;
  text-align: center;
  font-weight: 700;
}

.evaluation-summary {
  margin: 14px 0 8px;
  color: #243b30;
  line-height: 1.6;
}

.failure-list {
  margin: 0 0 12px;
  padding-left: 18px;
  color: #a61b1b;
}

.evaluation-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
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
