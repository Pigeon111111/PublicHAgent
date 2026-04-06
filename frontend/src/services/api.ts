import axios from 'axios'
import type {
  FileInfo,
  FileListResponse,
  ConversationListResponse,
  AnalysisHistoryResponse,
  FullConfig,
  AgentConfig,
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
  }
)

export async function uploadFile(file: File): Promise<FileInfo> {
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await axios.post('/api/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    timeout: 60000,
  })
  return response.data
}

export async function uploadMultipleFiles(files: File[]): Promise<FileInfo[]> {
  const formData = new FormData()
  files.forEach((file) => {
    formData.append('files', file)
  })
  
  const response = await axios.post('/api/upload/multiple', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
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

export async function getConversation(conversationId: string) {
  return api.get(`/conversations/${conversationId}`)
}

export async function createConversation(title: string = '新对话') {
  return api.post('/conversations', null, { params: { title } })
}

export async function deleteConversation(conversationId: string): Promise<void> {
  return api.delete(`/conversations/${conversationId}`)
}

export async function getAnalysisHistory(page: number = 1, pageSize: number = 20): Promise<AnalysisHistoryResponse> {
  return api.get('/analysis', { params: { page, page_size: pageSize } })
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

export async function healthCheck(): Promise<{ status: string; version: string }> {
  return axios.get('/health').then((res) => res.data)
}

export default api
