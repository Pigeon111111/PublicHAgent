<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  getAnalysisDetail,
  getAnalysisHistory,
  getConversations,
  promoteAnalysisVariant,
  rerunAnalysis,
  reviewAnalysisEvaluation,
} from '@/services/api'
import type {
  AnalysisDetailResponse,
  AnalysisRecord,
  Conversation,
  EvaluationReport,
  EvaluationReview,
} from '@/types'

const route = useRoute()
const router = useRouter()

const conversations = ref<Conversation[]>([])
const analysisRecords = ref<AnalysisRecord[]>([])
const loading = ref(false)
const detailLoading = ref(false)
const activeTab = ref<'analysis' | 'conversations'>('analysis')
const selectedAnalysisId = ref('')
const detail = ref<AnalysisDetailResponse | null>(null)
const reviewForm = ref<EvaluationReview>({
  review_status: 'confirmed',
  review_label: 'correct',
  review_comment: '',
  reviewed_by: 'default',
})

const selectedRecord = computed(() => detail.value?.record || null)
const selectedEvaluation = computed(() => detail.value?.evaluation || null)

onMounted(async () => {
  await loadData()
})

watch(
  () => route.query.analysisId,
  async (analysisId) => {
    if (typeof analysisId === 'string' && analysisId && analysisId !== selectedAnalysisId.value) {
      selectedAnalysisId.value = analysisId
      await loadAnalysisDetail(analysisId)
    }
  },
)

async function loadData() {
  loading.value = true
  try {
    const [conversationResponse, analysisResponse] = await Promise.all([
      getConversations(),
      getAnalysisHistory(),
    ])
    conversations.value = conversationResponse.conversations
    analysisRecords.value = analysisResponse.records

    const routeAnalysisId = typeof route.query.analysisId === 'string' ? route.query.analysisId : ''
    const initialAnalysisId = routeAnalysisId || analysisResponse.records[0]?.id || ''
    if (initialAnalysisId) {
      activeTab.value = 'analysis'
      selectedAnalysisId.value = initialAnalysisId
      await loadAnalysisDetail(initialAnalysisId)
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载历史记录失败')
  } finally {
    loading.value = false
  }
}

async function loadAnalysisDetail(analysisId: string) {
  detailLoading.value = true
  try {
    detail.value = await getAnalysisDetail(analysisId)
    if (detail.value.evaluation) {
      reviewForm.value = {
        review_status: detail.value.evaluation.review_status,
        review_label: (detail.value.evaluation.review_label || 'correct') as EvaluationReview['review_label'],
        review_comment: detail.value.evaluation.review_comment,
        reviewed_by: detail.value.evaluation.reviewed_by || 'default',
      }
    }
  } catch (error) {
    detail.value = null
    ElMessage.error(error instanceof Error ? error.message : '加载分析详情失败')
  } finally {
    detailLoading.value = false
  }
}

async function selectAnalysis(record: AnalysisRecord) {
  await router.push({ path: '/history', query: { analysisId: record.id } })
}

async function submitReview() {
  if (!selectedAnalysisId.value || !selectedEvaluation.value) return
  try {
    const evaluation = await reviewAnalysisEvaluation(selectedAnalysisId.value, reviewForm.value)
    detail.value = {
      record: {
        ...(detail.value?.record as AnalysisRecord),
        review_status: evaluation.review_status,
      },
      evaluation,
    }
    await loadData()
    ElMessage.success('评估审阅已保存')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '提交审阅失败')
  }
}

async function handleRerun() {
  if (!selectedRecord.value) return
  try {
    const response = await rerunAnalysis(selectedRecord.value.id)
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
  }
}

async function handlePromoteVariant() {
  if (!selectedRecord.value) return
  try {
    const response = await promoteAnalysisVariant(selectedRecord.value.id)
    ElMessage.success(`已学习为新细分方法：${response.variant}`)
    await router.push({
      path: '/methods',
      query: { family: response.family, variant: response.skill_name },
    })
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '学习新变体失败')
  }
}

function openMethods() {
  if (!selectedEvaluation.value?.associated_skill) return
  router.push('/methods')
}

function formatScore(value: number) {
  return `${(value * 100).toFixed(0)} 分`
}

function formatPassed(report: EvaluationReport | null) {
  if (!report) return '未评估'
  return report.passed ? '通过' : '未通过'
}
</script>

<template>
  <div class="history-view">
    <header class="page-header">
      <div>
        <h2>历史记录</h2>
        <p>查看分析结果、完整评估、人工审阅和方法学习动作。</p>
      </div>
    </header>

    <el-card
      v-loading="loading"
      shadow="never"
      class="history-card"
    >
      <el-tabs v-model="activeTab">
        <el-tab-pane
          label="分析历史"
          name="analysis"
        >
          <div class="analysis-layout">
            <div class="list-panel">
              <el-table
                :data="analysisRecords"
                height="640"
                highlight-current-row
                @current-change="selectAnalysis"
              >
                <el-table-column
                  prop="query"
                  label="查询"
                  min-width="220"
                  show-overflow-tooltip
                />
                <el-table-column
                  prop="task_family"
                  label="方法家族"
                  width="150"
                />
                <el-table-column
                  label="评估"
                  width="100"
                >
                  <template #default="{ row }">
                    <el-tag :type="row.evaluation_passed ? 'success' : 'danger'">
                      {{ row.evaluation_passed ? '通过' : '未通过' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column
                  label="得分"
                  width="100"
                >
                  <template #default="{ row }">
                    {{ formatScore(row.evaluation_score || 0) }}
                  </template>
                </el-table-column>
                <el-table-column
                  prop="review_status"
                  label="审阅状态"
                  width="130"
                />
              </el-table>
            </div>

            <div
              v-loading="detailLoading"
              class="detail-panel"
            >
              <el-empty
                v-if="!selectedRecord"
                description="请选择一条分析记录"
              />

              <template v-else>
                <div class="detail-header">
                  <div>
                    <h3>{{ selectedRecord.query }}</h3>
                    <p>{{ selectedRecord.intent }} / {{ selectedRecord.task_family || 'general' }}</p>
                  </div>
                  <div class="detail-tags">
                    <el-tag :type="selectedRecord.status === 'completed' ? 'success' : 'warning'">
                      {{ selectedRecord.status }}
                    </el-tag>
                    <el-tag :type="selectedEvaluation?.passed ? 'success' : 'danger'">
                      {{ formatPassed(selectedEvaluation) }}
                    </el-tag>
                  </div>
                </div>

                <div class="detail-summary">
                  <div>
                    <span>评估得分</span>
                    <strong>{{ formatScore(selectedRecord.evaluation_score || 0) }}</strong>
                  </div>
                  <div>
                    <span>轨迹</span>
                    <strong>{{ selectedRecord.trajectory_id || '无' }}</strong>
                  </div>
                  <div>
                    <span>步骤数</span>
                    <strong>{{ selectedRecord.steps_count }}</strong>
                  </div>
                  <div>
                    <span>审阅状态</span>
                    <strong>{{ selectedRecord.review_status }}</strong>
                  </div>
                </div>

                <section class="detail-section">
                  <h4>结果摘要</h4>
                  <p>{{ selectedRecord.result_summary || '暂无结果摘要' }}</p>
                </section>

                <section
                  v-if="selectedEvaluation"
                  class="detail-section"
                >
                  <h4>评估详情</h4>
                  <p>{{ selectedEvaluation.summary }}</p>

                  <div class="metric-grid">
                    <div>
                      <span>Artifact</span>
                      <strong>{{ formatScore(selectedEvaluation.report_json.score_breakdown?.artifact_score || 0) }}</strong>
                    </div>
                    <div>
                      <span>Statistical</span>
                      <strong>{{ formatScore(selectedEvaluation.report_json.score_breakdown?.statistical_score || 0) }}</strong>
                    </div>
                    <div>
                      <span>Process</span>
                      <strong>{{ formatScore(selectedEvaluation.report_json.score_breakdown?.process_score || 0) }}</strong>
                    </div>
                    <div>
                      <span>Report</span>
                      <strong>{{ formatScore(selectedEvaluation.report_json.score_breakdown?.report_score || 0) }}</strong>
                    </div>
                  </div>

                  <div
                    v-if="selectedEvaluation.report_json.hard_failures?.length"
                    class="detail-block"
                  >
                    <h5>硬失败原因</h5>
                    <ul>
                      <li
                        v-for="item in selectedEvaluation.report_json.hard_failures"
                        :key="item"
                      >
                        {{ item }}
                      </li>
                    </ul>
                  </div>

                  <div
                    v-if="selectedEvaluation.report_json.metric_assertions?.length"
                    class="detail-block"
                  >
                    <h5>指标断言</h5>
                    <el-table
                      :data="selectedEvaluation.report_json.metric_assertions"
                      size="small"
                      max-height="240"
                    >
                      <el-table-column
                        prop="metric"
                        label="指标"
                        min-width="180"
                      />
                      <el-table-column
                        prop="expected"
                        label="期望"
                        min-width="120"
                      />
                      <el-table-column
                        prop="actual"
                        label="实际"
                        min-width="120"
                      />
                      <el-table-column
                        label="结果"
                        width="80"
                      >
                        <template #default="{ row }">
                          <el-tag :type="row.passed ? 'success' : 'danger'">
                            {{ row.passed ? '通过' : '失败' }}
                          </el-tag>
                        </template>
                      </el-table-column>
                    </el-table>
                  </div>

                  <div
                    v-if="selectedEvaluation.report_json.findings?.length"
                    class="detail-block"
                  >
                    <h5>评估发现</h5>
                    <ul>
                      <li
                        v-for="item in selectedEvaluation.report_json.findings"
                        :key="`${item.code}_${item.message}`"
                      >
                        [{{ item.severity }}] {{ item.message }}
                      </li>
                    </ul>
                  </div>
                </section>

                <section
                  v-if="selectedEvaluation"
                  class="detail-section"
                >
                  <h4>评估审阅</h4>
                  <div class="review-grid">
                    <el-select v-model="reviewForm.review_status">
                      <el-option
                        label="确认正确"
                        value="confirmed"
                      />
                      <el-option
                        label="存在误判"
                        value="disputed"
                      />
                      <el-option
                        label="需要跟进"
                        value="needs_followup"
                      />
                      <el-option
                        label="未审阅"
                        value="unreviewed"
                      />
                    </el-select>

                    <el-select v-model="reviewForm.review_label">
                      <el-option
                        label="correct"
                        value="correct"
                      />
                      <el-option
                        label="false_positive"
                        value="false_positive"
                      />
                      <el-option
                        label="false_negative"
                        value="false_negative"
                      />
                      <el-option
                        label="metric_mismatch"
                        value="metric_mismatch"
                      />
                      <el-option
                        label="report_mismatch"
                        value="report_mismatch"
                      />
                    </el-select>
                  </div>

                  <el-input
                    v-model="reviewForm.review_comment"
                    type="textarea"
                    :rows="3"
                    placeholder="补充说明审阅意见"
                  />

                  <div class="detail-actions">
                    <el-button
                      type="primary"
                      @click="submitReview"
                    >
                      保存审阅
                    </el-button>
                    <el-button @click="handleRerun">
                      重新运行
                    </el-button>
                    <el-button
                      type="warning"
                      plain
                      @click="handlePromoteVariant"
                    >
                      学习为新变体
                    </el-button>
                    <el-button
                      v-if="selectedEvaluation.associated_skill"
                      @click="openMethods"
                    >
                      查看关联方法
                    </el-button>
                  </div>
                </section>
              </template>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane
          label="对话历史"
          name="conversations"
        >
          <el-table
            :data="conversations"
            stripe
          >
            <el-table-column
              prop="title"
              label="标题"
              min-width="220"
            />
            <el-table-column
              prop="message_count"
              label="消息数"
              width="100"
            />
            <el-table-column
              prop="created_at"
              label="创建时间"
              min-width="180"
            />
            <el-table-column
              prop="updated_at"
              label="更新时间"
              min-width="180"
            />
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<style scoped>
.history-view {
  min-height: calc(100vh - 60px);
  padding: 24px;
  background: linear-gradient(180deg, #f7faf8 0%, #eef3f1 100%);
}

.page-header {
  max-width: 1500px;
  margin: 0 auto 18px;
}

.page-header h2 {
  margin: 0 0 8px;
  color: #163126;
}

.page-header p {
  margin: 0;
  color: #5f6c76;
}

.history-card {
  max-width: 1500px;
  margin: 0 auto;
  border-radius: 20px;
}

.analysis-layout {
  display: grid;
  grid-template-columns: minmax(420px, 0.95fr) minmax(0, 1.2fr);
  gap: 16px;
}

.list-panel,
.detail-panel {
  min-width: 0;
}

.detail-panel {
  padding: 6px 4px 6px 8px;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  gap: 14px;
}

.detail-header h3 {
  margin: 0 0 6px;
}

.detail-header p {
  margin: 0;
  color: #61707b;
}

.detail-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.detail-summary {
  margin: 18px 0;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.detail-summary div,
.metric-grid div {
  padding: 12px;
  border-radius: 12px;
  background: #f5faf7;
}

.detail-summary span,
.metric-grid span {
  display: block;
  color: #6a7884;
  font-size: 12px;
}

.detail-summary strong,
.metric-grid strong {
  display: block;
  margin-top: 6px;
  color: #173327;
}

.detail-section {
  margin-top: 20px;
}

.detail-section h4,
.detail-block h5 {
  margin: 0 0 10px;
}

.detail-section p {
  margin: 0;
  line-height: 1.7;
  color: #3d4953;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.detail-block {
  margin-top: 14px;
}

.detail-block ul {
  margin: 0;
  padding-left: 18px;
  color: #4b5964;
  line-height: 1.7;
}

.review-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.detail-actions {
  margin-top: 12px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

@media (max-width: 1200px) {
  .analysis-layout {
    grid-template-columns: 1fr;
  }

  .detail-summary,
  .metric-grid,
  .review-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 700px) {
  .detail-summary,
  .metric-grid,
  .review-grid {
    grid-template-columns: 1fr;
  }
}
</style>
