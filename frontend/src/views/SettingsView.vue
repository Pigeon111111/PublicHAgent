<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getConfig, updateAgentConfig, updateSandboxConfig } from '@/services/api'
import type { FullConfig, AgentConfig, SandboxConfig } from '@/types'

const config = ref<FullConfig | null>(null)
const loading = ref(false)
const saving = ref(false)
const agentForm = ref<AgentConfig>({
  max_iterations: 10,
  reflection_attempts: 3,
  planner_model: 'gpt-4o',
  executor_model: 'gpt-4o-mini',
})
const sandboxForm = ref<SandboxConfig>({
  enabled: true,
  memory_limit: '512m',
  cpu_limit: '1.0',
  timeout: 60,
  network_disabled: true,
})

onMounted(() => {
  loadConfig()
})

async function loadConfig() {
  loading.value = true
  try {
    config.value = await getConfig()
    agentForm.value = { ...config.value.agent }
    sandboxForm.value = { ...config.value.sandbox }
  } catch {
    ElMessage.error('加载配置失败')
  } finally {
    loading.value = false
  }
}

async function saveAgentConfig() {
  saving.value = true
  try {
    await updateAgentConfig(agentForm.value)
    ElMessage.success('Agent 配置已保存')
  } catch {
    ElMessage.error('保存配置失败')
  } finally {
    saving.value = false
  }
}

async function saveSandboxConfig() {
  saving.value = true
  try {
    await updateSandboxConfig(sandboxForm.value)
    ElMessage.success('沙箱配置已保存')
  } catch {
    ElMessage.error('保存配置失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="settings-view">
    <el-container>
      <el-header class="settings-header">
        <h2>系统设置</h2>
      </el-header>
      <el-main class="settings-main" v-loading="loading">
        <el-row :gutter="24">
          <el-col :span="12">
            <el-card>
              <template #header>
                <span>Agent 配置</span>
              </template>
              <el-form :model="agentForm" label-width="120px">
                <el-form-item label="最大迭代次数">
                  <el-input-number v-model="agentForm.max_iterations" :min="1" :max="50" />
                </el-form-item>
                <el-form-item label="反思尝试次数">
                  <el-input-number v-model="agentForm.reflection_attempts" :min="1" :max="10" />
                </el-form-item>
                <el-form-item label="规划模型">
                  <el-input v-model="agentForm.planner_model" />
                </el-form-item>
                <el-form-item label="执行模型">
                  <el-input v-model="agentForm.executor_model" />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="saveAgentConfig" :loading="saving">
                    保存配置
                  </el-button>
                </el-form-item>
              </el-form>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card>
              <template #header>
                <span>沙箱配置</span>
              </template>
              <el-form :model="sandboxForm" label-width="120px">
                <el-form-item label="启用沙箱">
                  <el-switch v-model="sandboxForm.enabled" />
                </el-form-item>
                <el-form-item label="内存限制">
                  <el-input v-model="sandboxForm.memory_limit" />
                </el-form-item>
                <el-form-item label="CPU 限制">
                  <el-input v-model="sandboxForm.cpu_limit" />
                </el-form-item>
                <el-form-item label="超时时间(秒)">
                  <el-input-number v-model="sandboxForm.timeout" :min="10" :max="600" />
                </el-form-item>
                <el-form-item label="禁用网络">
                  <el-switch v-model="sandboxForm.network_disabled" />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="saveSandboxConfig" :loading="saving">
                    保存配置
                  </el-button>
                </el-form-item>
              </el-form>
            </el-card>
          </el-col>
        </el-row>

        <el-card class="info-card" v-if="config">
          <template #header>
            <span>系统信息</span>
          </template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="应用名称">{{ config.app.name }}</el-descriptions-item>
            <el-descriptions-item label="版本">{{ config.app.version }}</el-descriptions-item>
            <el-descriptions-item label="API 地址">{{ config.api.host }}:{{ config.api.port }}</el-descriptions-item>
            <el-descriptions-item label="WebSocket 路径">{{ config.api.websocket_path }}</el-descriptions-item>
            <el-descriptions-item label="记忆提供者">{{ config.memory.provider }}</el-descriptions-item>
            <el-descriptions-item label="向量存储">{{ config.memory.vector_store }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-main>
    </el-container>
  </div>
</template>

<style scoped>
.settings-view {
  min-height: 100vh;
  background-color: #f5f7fa;
}

.settings-header {
  display: flex;
  align-items: center;
  background-color: white;
  border-bottom: 1px solid #e4e7ed;
  padding: 0 24px;
}

.settings-header h2 {
  font-size: 20px;
  color: #303133;
}

.settings-main {
  padding: 24px;
}

.info-card {
  margin-top: 24px;
}
</style>
