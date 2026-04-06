<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getConversations, getAnalysisHistory } from '@/services/api'
import type { Conversation, AnalysisRecord } from '@/types'

const conversations = ref<Conversation[]>([])
const analysisRecords = ref<AnalysisRecord[]>([])
const loading = ref(false)
const activeTab = ref('conversations')

onMounted(() => {
  loadData()
})

async function loadData() {
  loading.value = true
  try {
    const [convResponse, analysisResponse] = await Promise.all([
      getConversations(),
      getAnalysisHistory(),
    ])
    conversations.value = convResponse.conversations
    analysisRecords.value = analysisResponse.records
  } catch {
    ElMessage.error('加载历史记录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="history-view">
    <el-container>
      <el-header class="history-header">
        <h2>历史记录</h2>
      </el-header>
      <el-main class="history-main">
        <el-card v-loading="loading">
          <el-tabs v-model="activeTab">
            <el-tab-pane label="对话历史" name="conversations">
              <el-table :data="conversations" stripe>
                <el-table-column prop="title" label="标题" min-width="200" />
                <el-table-column label="消息数" width="100">
                  <template #default="{ row }">
                    {{ row.message_count }}
                  </template>
                </el-table-column>
                <el-table-column label="创建时间" width="180">
                  <template #default="{ row }">
                    {{ new Date(row.created_at).toLocaleString() }}
                  </template>
                </el-table-column>
                <el-table-column label="更新时间" width="180">
                  <template #default="{ row }">
                    {{ new Date(row.updated_at).toLocaleString() }}
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>
            <el-tab-pane label="分析历史" name="analysis">
              <el-table :data="analysisRecords" stripe>
                <el-table-column prop="query" label="查询" min-width="200" show-overflow-tooltip />
                <el-table-column prop="intent" label="意图" width="120" />
                <el-table-column prop="status" label="状态" width="100">
                  <template #default="{ row }">
                    <el-tag :type="row.status === 'completed' ? 'success' : 'warning'">
                      {{ row.status }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="steps_count" label="步骤数" width="80" />
                <el-table-column label="创建时间" width="180">
                  <template #default="{ row }">
                    {{ new Date(row.created_at).toLocaleString() }}
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </el-main>
    </el-container>
  </div>
</template>

<style scoped>
.history-view {
  min-height: 100vh;
  background-color: #f5f7fa;
}

.history-header {
  display: flex;
  align-items: center;
  background-color: white;
  border-bottom: 1px solid #e4e7ed;
  padding: 0 24px;
}

.history-header h2 {
  font-size: 20px;
  color: #303133;
}

.history-main {
  padding: 24px;
}
</style>
