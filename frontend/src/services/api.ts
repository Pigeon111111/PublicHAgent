import axios from 'axios'
import type {
  AgentConfig,
  AnalysisDetailResponse,
  AnalysisHistoryResponse,
  Conversation,
  ConversationListResponse,
  EvaluationReport,
  EvaluationReview,
  FileInfo,
  FileListResponse,
  FullConfig,
  MethodFamilyListResponse,
  MethodVariantListResponse,
  PreferredVariantState,
  RerunResponse,
  SandboxConfig,
} from '@/types'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.detail || error.message || '请求失败'
    return Promise.reject(new Error(message))
  },
)

export async function uploadFile(file: File): Promise<FileInfo> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await axios.post('/api/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  })
  return response.data
}

export async function uploadMultipleFiles(files: File[]): Promise<FileInfo[]> {
  const formData = new FormData()
  files.forEach((file) => formData.append('files', file))
  const response = await axios.post('/api/upload/multiple', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
  return response.data
}

export async function getFiles(page: number = 1, pageSize: number = 20, extension?: string): Promise<FileListResponse> {
  const params: Record<string, unknown> = { page, page_size: pageSize }
  if (extension) {
    params.extension = extension
  }
  return api.get('/files', { params })
}

export async function getFile(fileId: string): Promise<FileInfo> {
  return api.get(`/files/${fileId}`)
}

export async function deleteFile(fileId: string): Promise<void> {
  return api.delete(`/files/${fileId}`)
}

export async function getConversations(page: number = 1, pageSize: number = 20): Promise<ConversationListResponse> {
  return api.get('/conversations', { params: { page, page_size: pageSize } })
}

export async function getConversation(conversationId: string): Promise<Conversation> {
  return api.get(`/conversations/${conversationId}`)
}

export async function createConversation(title: string = '新对话'): Promise<Conversation> {
  return api.post('/conversations', null, { params: { title } })
}

export async function deleteConversation(conversationId: string): Promise<void> {
  return api.delete(`/conversations/${conversationId}`)
}

export async function getAnalysisHistory(page: number = 1, pageSize: number = 20): Promise<AnalysisHistoryResponse> {
  return api.get('/analysis', { params: { page, page_size: pageSize } })
}

export async function getAnalysisDetail(analysisId: string): Promise<AnalysisDetailResponse> {
  return api.get(`/analysis/${analysisId}`)
}

export async function getAnalysisEvaluation(analysisId: string): Promise<EvaluationReport> {
  return api.get(`/analysis/${analysisId}/evaluation`)
}

export async function reviewAnalysisEvaluation(analysisId: string, review: EvaluationReview): Promise<EvaluationReport> {
  return api.post(`/analysis/${analysisId}/evaluation/review`, review)
}

export async function rerunAnalysis(analysisId: string): Promise<RerunResponse> {
  return api.post(`/analysis/${analysisId}/rerun`)
}

export async function getMethodFamilies(): Promise<MethodFamilyListResponse> {
  return api.get('/method-families')
}

export async function getMethodVariants(family: string): Promise<MethodVariantListResponse> {
  return api.get(`/method-families/${family}/variants`)
}

export async function setPreferredVariant(
  family: string,
  preferredVariant: string,
  userId: string = 'default',
): Promise<{ success: boolean; preference: PreferredVariantState }> {
  return api.post(`/method-families/${family}/preferred-variant`, {
    preferred_variant: preferredVariant,
    user_id: userId,
  })
}

export async function promoteAnalysisVariant(
  analysisId: string,
): Promise<{ analysis_id: string; skill_name: string; family: string; variant: string }> {
  return api.post(`/analysis/${analysisId}/promote-variant`)
}

export async function getConfig(): Promise<FullConfig> {
  return api.get('/config')
}

export async function getAgentConfig(): Promise<AgentConfig> {
  return api.get('/config/agent')
}

export async function updateAgentConfig(config: AgentConfig): Promise<AgentConfig> {
  return api.put('/config/agent', config)
}

export async function getSandboxConfig(): Promise<SandboxConfig> {
  return api.get('/config/sandbox')
}

export async function updateSandboxConfig(config: SandboxConfig): Promise<SandboxConfig> {
  return api.put('/config/sandbox', config)
}

export interface SkillListItem {
  name: string
  description: string
  enabled: boolean
  metadata: Record<string, unknown>
  capability: Record<string, unknown>
}

export async function getSkills(): Promise<{ success: boolean; skills: SkillListItem[]; total: number }> {
  return api.get('/skills')
}

export async function getSkill(skillName: string): Promise<{ success: boolean; skill: SkillListItem }> {
  return api.get(`/skills/${skillName}`)
}

export async function enableSkill(skillName: string): Promise<{ success: boolean; message: string }> {
  return api.post(`/skills/${skillName}/enable`)
}

export async function disableSkill(skillName: string): Promise<{ success: boolean; message: string }> {
  return api.post(`/skills/${skillName}/disable`)
}

export async function deleteSkill(skillName: string): Promise<{ success: boolean; message: string }> {
  return api.delete(`/skills/${skillName}`)
}

export async function setApiKey(provider: string, apiKey: string): Promise<{ success: boolean; message: string }> {
  return api.put('/user/api-key', { provider, api_key: apiKey })
}

export async function getApiKey(provider: string): Promise<{ success: boolean; has_key: boolean; masked_key: string | null }> {
  return api.get(`/user/api-key/${provider}`)
}

export async function deleteApiKey(provider: string): Promise<{ success: boolean; message: string }> {
  return api.delete(`/user/api-key/${provider}`)
}

export interface CustomModel {
  name: string
  model_id: string
  base_url: string
  has_api_key: boolean
  max_tokens: number
  temperature: number
  supports_streaming: boolean
  supports_function_calling: boolean
}

export interface CustomModelCreate {
  model_name: string
  name: string
  model_id: string
  base_url: string
  api_key?: string
  max_tokens?: number
  temperature?: number
  supports_streaming?: boolean
  supports_function_calling?: boolean
}

export interface CustomModelUpdate {
  name?: string
  model_id?: string
  base_url?: string
  api_key?: string
  max_tokens?: number
  temperature?: number
  supports_streaming?: boolean
  supports_function_calling?: boolean
}

export interface AvailableModel {
  name: string
  model_id: string
  provider: string
  type: 'preset' | 'custom'
  model_name?: string
  base_url?: string
  has_api_key?: boolean
}

export async function listCustomModels(): Promise<{ success: boolean; models: Record<string, CustomModel>; total: number }> {
  return api.get('/user/custom-models')
}

export async function createCustomModel(data: CustomModelCreate): Promise<{ success: boolean; message: string; model: Record<string, unknown> }> {
  return api.post('/user/custom-models', data)
}

export async function getCustomModel(modelName: string): Promise<{ success: boolean; model: CustomModel }> {
  return api.get(`/user/custom-models/${modelName}`)
}

export async function updateCustomModel(modelName: string, data: CustomModelUpdate): Promise<{ success: boolean; message: string }> {
  return api.put(`/user/custom-models/${modelName}`, data)
}

export async function deleteCustomModel(modelName: string): Promise<{ success: boolean; message: string }> {
  return api.delete(`/user/custom-models/${modelName}`)
}

export async function setModelSelection(modelType: string, modelName: string): Promise<{ success: boolean; message: string }> {
  return api.put('/user/model-selection', { model_type: modelType, model_name: modelName })
}

export async function getModelSelection(): Promise<{ success: boolean; planner_model: string; executor_model: string }> {
  return api.get('/user/model-selection')
}

export async function getAvailableModels(): Promise<{ success: boolean; models: AvailableModel[]; total: number }> {
  return api.get('/user/available-models')
}

export async function healthCheck(): Promise<{ status: string; version: string }> {
  return axios.get('/health').then((response) => response.data)
}

export default api
