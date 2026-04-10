<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getConfig,
  updateAgentConfig,
  updateSandboxConfig,
  getSkills,
  enableSkill,
  disableSkill,
  deleteSkill,
  setApiKey,
  getApiKey,
  listCustomModels,
  createCustomModel,
  updateCustomModel,
  deleteCustomModel,
  setModelSelection,
  getModelSelection,
  getAvailableModels,
} from '@/services/api'
import type { FullConfig, AgentConfig, SandboxConfig, CustomModel, AvailableModel, CustomModelCreate } from '@/types'

const config = ref<FullConfig | null>(null)
const loading = ref(false)
const saving = ref(false)
const agentForm = ref<AgentConfig>({
  max_iterations: 10,
  reflection_attempts: 3,
})
const sandboxForm = ref<SandboxConfig>({
  enabled: true,
  memory_limit: '512m',
  cpu_limit: '1.0',
  timeout: 60,
  network_disabled: true,
})

const activeTab = ref('agent')
const skills = ref<Array<{ name: string; description: string; enabled: boolean }>>([])
const skillsLoading = ref(false)

const modelProviders = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'longcat', label: 'LongCat' },
  { value: 'custom', label: '自定义' },
]

const selectedProvider = ref('openai')
const apiKeyInput = ref('')
const apiKeyStatus = ref<{ has_key: boolean; masked_key: string | null }>({ has_key: false, masked_key: null })

// 自定义模型相关
const customModels = ref<Record<string, CustomModel>>({})
const customModelsLoading = ref(false)
const showModelDialog = ref(false)
const editingModelName = ref<string | null>(null)
const modelForm = ref<CustomModelCreate>({
  model_name: '',
  name: '',
  model_id: '',
  base_url: '',
  api_key: '',
  max_tokens: 4096,
  temperature: 0.7,
  supports_streaming: true,
  supports_function_calling: true,
})

// 模型选择相关
const availableModels = ref<AvailableModel[]>([])
const modelSelection = ref({ planner_model: 'gpt-4o', executor_model: 'gpt-4o-mini' })
const modelsLoading = ref(false)

const plannerModelOptions = computed(() => {
  if (!availableModels.value || !Array.isArray(availableModels.value)) {
    return []
  }
  return availableModels.value.map(m => ({
    value: m.type === 'custom' ? m.model_name! : m.model_id,
    label: `${m.name} (${m.provider})`,
    type: m.type,
  }))
})

const executorModelOptions = computed(() => plannerModelOptions.value)

onMounted(() => {
  loadConfig()
  loadSkills()
  loadCustomModels()
  loadModelSelection()
  loadAvailableModels()
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

async function loadSkills() {
  skillsLoading.value = true
  try {
    const result = await getSkills()
    skills.value = result.skills || []
  } catch {
    ElMessage.error('加载 Skills 失败')
  } finally {
    skillsLoading.value = false
  }
}

async function handleToggleSkill(skill: { name: string; enabled: boolean }) {
  try {
    if (skill.enabled) {
      await disableSkill(skill.name)
      skill.enabled = false
      ElMessage.success(`Skill ${skill.name} 已禁用`)
    } else {
      await enableSkill(skill.name)
      skill.enabled = true
      ElMessage.success(`Skill ${skill.name} 已启用`)
    }
  } catch {
    ElMessage.error('操作失败')
  }
}

async function handleDeleteSkill(skill: { name: string }) {
  try {
    await ElMessageBox.confirm(`确定要删除 Skill "${skill.name}" 吗？`, '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await deleteSkill(skill.name)
    ElMessage.success(`Skill ${skill.name} 已删除`)
    loadSkills()
  } catch {
    // 用户取消或删除失败
  }
}

async function loadApiKeyStatus() {
  try {
    const result = await getApiKey(selectedProvider.value)
    apiKeyStatus.value = result
  } catch {
    apiKeyStatus.value = { has_key: false, masked_key: null }
  }
}

async function handleSaveApiKey() {
  if (!apiKeyInput.value.trim()) {
    ElMessage.warning('请输入 API Key')
    return
  }
  try {
    await setApiKey(selectedProvider.value, apiKeyInput.value)
    ElMessage.success('API Key 保存成功')
    apiKeyInput.value = ''
    loadApiKeyStatus()
  } catch {
    ElMessage.error('保存 API Key 失败')
  }
}

function handleProviderChange() {
  loadApiKeyStatus()
}

// 自定义模型管理
async function loadCustomModels() {
  customModelsLoading.value = true
  try {
    const result = await listCustomModels()
    customModels.value = result.models || {}
  } catch {
    ElMessage.error('加载自定义模型失败')
  } finally {
    customModelsLoading.value = false
  }
}

async function loadAvailableModels() {
  modelsLoading.value = true
  try {
    const result = await getAvailableModels()
    availableModels.value = Array.isArray(result.models) ? result.models : []
  } catch {
    availableModels.value = []
    ElMessage.error('加载可用模型失败')
  } finally {
    modelsLoading.value = false
  }
}

async function loadModelSelection() {
  try {
    const result = await getModelSelection()
    modelSelection.value = {
      planner_model: result.planner_model,
      executor_model: result.executor_model,
    }
  } catch {
    // 使用默认值
  }
}

function openCreateModelDialog() {
  editingModelName.value = null
  modelForm.value = {
    model_name: '',
    name: '',
    model_id: '',
    base_url: '',
    api_key: '',
    max_tokens: 4096,
    temperature: 0.7,
    supports_streaming: true,
    supports_function_calling: true,
  }
  showModelDialog.value = true
}

function openEditModelDialog(modelName: string, model: CustomModel) {
  editingModelName.value = modelName
  modelForm.value = {
    model_name: modelName,
    name: model.name,
    model_id: model.model_id,
    base_url: model.base_url,
    api_key: '',
    max_tokens: model.max_tokens,
    temperature: model.temperature,
    supports_streaming: model.supports_streaming,
    supports_function_calling: model.supports_function_calling,
  }
  showModelDialog.value = true
}

async function handleSaveModel() {
  if (!modelForm.value.model_name.trim()) {
    ElMessage.warning('请输入模型标识名称')
    return
  }
  if (!modelForm.value.name.trim()) {
    ElMessage.warning('请输入模型显示名称')
    return
  }
  if (!modelForm.value.model_id.trim()) {
    ElMessage.warning('请输入模型 ID')
    return
  }
  if (!modelForm.value.base_url.trim()) {
    ElMessage.warning('请输入 Base URL')
    return
  }

  try {
    if (editingModelName.value) {
      const updateData: Record<string, unknown> = {
        name: modelForm.value.name,
        model_id: modelForm.value.model_id,
        base_url: modelForm.value.base_url,
        max_tokens: modelForm.value.max_tokens,
        temperature: modelForm.value.temperature,
        supports_streaming: modelForm.value.supports_streaming,
        supports_function_calling: modelForm.value.supports_function_calling,
      }
      if (modelForm.value.api_key) {
        updateData.api_key = modelForm.value.api_key
      }
      await updateCustomModel(editingModelName.value, updateData)
      ElMessage.success('模型更新成功')
    } else {
      await createCustomModel(modelForm.value)
      ElMessage.success('模型创建成功')
    }
    showModelDialog.value = false
    loadCustomModels()
    loadAvailableModels()
  } catch (error) {
    ElMessage.error(editingModelName.value ? '更新模型失败' : '创建模型失败')
  }
}

async function handleDeleteModel(modelName: string) {
  try {
    await ElMessageBox.confirm(`确定要删除模型 "${modelName}" 吗？`, '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await deleteCustomModel(modelName)
    ElMessage.success('模型删除成功')
    loadCustomModels()
    loadAvailableModels()
  } catch {
    // 用户取消或删除失败
  }
}

async function handleModelSelectionChange() {
  try {
    await setModelSelection('planner', modelSelection.value.planner_model)
    await setModelSelection('executor', modelSelection.value.executor_model)
    ElMessage.success('模型选择已保存')
  } catch {
    ElMessage.error('保存模型选择失败')
  }
}
</script>

<template>
  <div class="settings-view">
    <el-container>
      <el-main
        v-loading="loading"
        class="settings-main"
      >
        <el-tabs
          v-model="activeTab"
          type="border-card"
        >
          <el-tab-pane
            label="Agent 配置"
            name="agent"
          >
            <el-card>
              <template #header>
                <span>Agent 配置</span>
              </template>
              <el-form
                :model="agentForm"
                label-width="120px"
              >
                <el-form-item label="最大迭代次数">
                  <el-input-number
                    v-model="agentForm.max_iterations"
                    :min="1"
                    :max="50"
                  />
                </el-form-item>
                <el-form-item label="反思尝试次数">
                  <el-input-number
                    v-model="agentForm.reflection_attempts"
                    :min="1"
                    :max="10"
                  />
                </el-form-item>
                <el-form-item>
                  <el-button
                    type="primary"
                    :loading="saving"
                    @click="saveAgentConfig"
                  >
                    保存配置
                  </el-button>
                </el-form-item>
              </el-form>
            </el-card>
          </el-tab-pane>

          <el-tab-pane
            label="模型配置"
            name="model"
          >
            <el-row :gutter="20">
              <el-col :span="12">
                <el-card>
                  <template #header>
                    <span>模型 API Key 配置</span>
                  </template>
                  <el-form label-width="120px">
                    <el-form-item label="选择提供商">
                      <el-select
                        v-model="selectedProvider"
                        @change="handleProviderChange"
                      >
                        <el-option
                          v-for="provider in modelProviders"
                          :key="provider.value"
                          :label="provider.label"
                          :value="provider.value"
                        />
                      </el-select>
                    </el-form-item>
                    <el-form-item label="当前状态">
                      <el-tag
                        v-if="apiKeyStatus.has_key"
                        type="success"
                      >
                        已配置 ({{ apiKeyStatus.masked_key }})
                      </el-tag>
                      <el-tag
                        v-else
                        type="info"
                      >
                        未配置
                      </el-tag>
                    </el-form-item>
                    <el-form-item label="API Key">
                      <el-input
                        v-model="apiKeyInput"
                        type="password"
                        placeholder="请输入 API Key"
                        show-password
                        style="width: 300px"
                      />
                    </el-form-item>
                    <el-form-item>
                      <el-button
                        type="primary"
                        @click="handleSaveApiKey"
                      >
                        保存 API Key
                      </el-button>
                    </el-form-item>
                  </el-form>
                </el-card>
              </el-col>
              <el-col :span="12">
                <el-card>
                  <template #header>
                    <div class="card-header">
                      <span>自定义模型</span>
                      <el-button
                        type="primary"
                        size="small"
                        @click="openCreateModelDialog"
                      >
                        添加模型
                      </el-button>
                    </div>
                  </template>
                  <el-table
                    v-loading="customModelsLoading"
                    :data="Object.entries(customModels).map(([key, val]) => ({ model_key: key, ...val }))"
                    max-height="300"
                  >
                    <el-table-column
                      prop="model_key"
                      label="标识名称"
                      width="120"
                    />
                    <el-table-column
                      prop="model_id"
                      label="模型 ID"
                      width="150"
                    />
                    <el-table-column
                      prop="base_url"
                      label="Base URL"
                      show-overflow-tooltip
                    />
                    <el-table-column
                      label="API Key"
                      width="100"
                    >
                      <template #default="{ row }">
                        <el-tag
                          :type="row.has_api_key ? 'success' : 'warning'"
                          size="small"
                        >
                          {{ row.has_api_key ? '已配置' : '未配置' }}
                        </el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column
                      label="操作"
                      width="150"
                    >
                      <template #default="{ row }">
                        <el-button
                          type="primary"
                          size="small"
                          link
                          @click="openEditModelDialog(row.model_key, row)"
                        >
                          编辑
                        </el-button>
                        <el-button
                          type="danger"
                          size="small"
                          link
                          @click="handleDeleteModel(row.model_key)"
                        >
                          删除
                        </el-button>
                      </template>
                    </el-table-column>
                  </el-table>
                </el-card>
              </el-col>
            </el-row>
          </el-tab-pane>

          <el-tab-pane
            label="模型选择"
            name="selection"
          >
            <el-card v-loading="modelsLoading">
              <template #header>
                <span>Agent 模型选择</span>
              </template>
              <el-form label-width="120px">
                <el-form-item label="Planner 模型">
                  <el-select
                    v-model="modelSelection.planner_model"
                    style="width: 300px"
                    @change="handleModelSelectionChange"
                  >
                    <el-option-group label="预设模型">
                      <el-option
                        v-for="opt in plannerModelOptions.filter(o => o.type === 'preset')"
                        :key="opt.value"
                        :label="opt.label"
                        :value="opt.value"
                      />
                    </el-option-group>
                    <el-option-group
                      v-if="plannerModelOptions.some(o => o.type === 'custom')"
                      label="自定义模型"
                    >
                      <el-option
                        v-for="opt in plannerModelOptions.filter(o => o.type === 'custom')"
                        :key="opt.value"
                        :label="opt.label"
                        :value="opt.value"
                      />
                    </el-option-group>
                  </el-select>
                </el-form-item>
                <el-form-item label="Executor 模型">
                  <el-select
                    v-model="modelSelection.executor_model"
                    style="width: 300px"
                    @change="handleModelSelectionChange"
                  >
                    <el-option-group label="预设模型">
                      <el-option
                        v-for="opt in executorModelOptions.filter(o => o.type === 'preset')"
                        :key="opt.value"
                        :label="opt.label"
                        :value="opt.value"
                      />
                    </el-option-group>
                    <el-option-group
                      v-if="executorModelOptions.some(o => o.type === 'custom')"
                      label="自定义模型"
                    >
                      <el-option
                        v-for="opt in executorModelOptions.filter(o => o.type === 'custom')"
                        :key="opt.value"
                        :label="opt.label"
                        :value="opt.value"
                      />
                    </el-option-group>
                  </el-select>
                </el-form-item>
              </el-form>
            </el-card>
          </el-tab-pane>

          <el-tab-pane
            label="Skill 管理"
            name="skills"
          >
            <el-card v-loading="skillsLoading">
              <template #header>
                <div class="card-header">
                  <span>Skills 管理</span>
                  <el-button
                    type="primary"
                    size="small"
                    @click="loadSkills"
                  >
                    刷新
                  </el-button>
                </div>
              </template>
              <el-table
                :data="skills"
                style="width: 100%"
              >
                <el-table-column
                  prop="name"
                  label="名称"
                  width="200"
                />
                <el-table-column
                  prop="description"
                  label="描述"
                />
                <el-table-column
                  label="状态"
                  width="100"
                >
                  <template #default="{ row }">
                    <el-tag :type="row.enabled ? 'success' : 'info'">
                      {{ row.enabled ? '已启用' : '已禁用' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column
                  label="操作"
                  width="200"
                >
                  <template #default="{ row }">
                    <el-button
                      :type="row.enabled ? 'warning' : 'success'"
                      size="small"
                      @click="handleToggleSkill(row)"
                    >
                      {{ row.enabled ? '禁用' : '启用' }}
                    </el-button>
                    <el-button
                      type="danger"
                      size="small"
                      @click="handleDeleteSkill(row)"
                    >
                      删除
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>
          </el-tab-pane>

          <el-tab-pane
            label="沙箱配置"
            name="sandbox"
          >
            <el-card>
              <template #header>
                <span>沙箱配置</span>
              </template>
              <el-form
                :model="sandboxForm"
                label-width="120px"
              >
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
                  <el-input-number
                    v-model="sandboxForm.timeout"
                    :min="10"
                    :max="600"
                  />
                </el-form-item>
                <el-form-item label="禁用网络">
                  <el-switch v-model="sandboxForm.network_disabled" />
                </el-form-item>
                <el-form-item>
                  <el-button
                    type="primary"
                    :loading="saving"
                    @click="saveSandboxConfig"
                  >
                    保存配置
                  </el-button>
                </el-form-item>
              </el-form>
            </el-card>
          </el-tab-pane>

          <el-tab-pane
            v-if="config"
            label="系统信息"
            name="info"
          >
            <el-card>
              <template #header>
                <span>系统信息</span>
              </template>
              <el-descriptions
                :column="2"
                border
              >
                <el-descriptions-item label="应用名称">
                  {{ config.app.name }}
                </el-descriptions-item>
                <el-descriptions-item label="版本">
                  {{ config.app.version }}
                </el-descriptions-item>
                <el-descriptions-item label="API 地址">
                  {{ config.api.host }}:{{ config.api.port }}
                </el-descriptions-item>
                <el-descriptions-item label="WebSocket 路径">
                  {{ config.api.websocket_path }}
                </el-descriptions-item>
                <el-descriptions-item label="记忆提供者">
                  {{ config.memory.provider }}
                </el-descriptions-item>
                <el-descriptions-item label="向量存储">
                  {{ config.memory.vector_store }}
                </el-descriptions-item>
              </el-descriptions>
            </el-card>
          </el-tab-pane>
        </el-tabs>
      </el-main>
    </el-container>

    <!-- 自定义模型编辑对话框 -->
    <el-dialog
      v-model="showModelDialog"
      :title="editingModelName ? '编辑模型' : '添加自定义模型'"
      width="500px"
    >
      <el-form
        :model="modelForm"
        label-width="120px"
      >
        <el-form-item
          v-if="!editingModelName"
          label="标识名称"
        >
          <el-input
            v-model="modelForm.model_name"
            placeholder="唯一标识，如 my-gpt4"
          />
        </el-form-item>
        <el-form-item label="显示名称">
          <el-input
            v-model="modelForm.name"
            placeholder="如 My GPT-4"
          />
        </el-form-item>
        <el-form-item label="模型 ID">
          <el-input
            v-model="modelForm.model_id"
            placeholder="如 gpt-4o"
          />
        </el-form-item>
        <el-form-item label="Base URL">
          <el-input
            v-model="modelForm.base_url"
            placeholder="如 https://api.openai.com/v1"
          />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input
            v-model="modelForm.api_key"
            type="password"
            placeholder="可选，留空则使用全局配置"
            show-password
          />
        </el-form-item>
        <el-form-item label="最大 Token">
          <el-input-number
            v-model="modelForm.max_tokens"
            :min="256"
            :max="128000"
          />
        </el-form-item>
        <el-form-item label="温度">
          <el-slider
            v-model="modelForm.temperature"
            :min="0"
            :max="2"
            :step="0.1"
            show-input
          />
        </el-form-item>
        <el-form-item label="支持流式">
          <el-switch v-model="modelForm.supports_streaming" />
        </el-form-item>
        <el-form-item label="支持函数调用">
          <el-switch v-model="modelForm.supports_function_calling" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showModelDialog = false">
          取消
        </el-button>
        <el-button
          type="primary"
          @click="handleSaveModel"
        >
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.settings-view {
  min-height: calc(100vh - 60px);
  background-color: #f5f7fa;
}

.settings-main {
  padding: 24px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
