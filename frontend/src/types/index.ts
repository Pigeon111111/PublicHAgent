export interface FileInfo {
  id: string
  filename: string
  size: number
  content_type: string
  upload_time: string
  path: string
}

export interface FileListResponse {
  files: FileInfo[]
  total: number
}

export interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
}

export interface Conversation {
  id: string
  title: string
  messages: Message[]
  created_at: string
  updated_at: string
  message_count: number
}

export interface ConversationListResponse {
  conversations: Conversation[]
  total: number
}

export interface AnalysisRecord {
  id: string
  query: string
  intent: string
  status: string
  result_summary: string
  created_at: string
  steps_count: number
}

export interface AnalysisHistoryResponse {
  records: AnalysisRecord[]
  total: number
}

export type MessageType = 'user' | 'agent' | 'status' | 'progress' | 'error' | 'interrupt'

export interface BaseMessage {
  type: MessageType
  session_id: string
  timestamp: string
}

export interface UserMessage extends BaseMessage {
  type: 'user'
  content: string
  user_id: string
  context: Record<string, unknown>
}

export interface AgentMessage extends BaseMessage {
  type: 'agent'
  content: string
  intent: string
  plan: Record<string, unknown> | null
  is_streaming: boolean
  is_final: boolean
}

export interface StatusMessage extends BaseMessage {
  type: 'status'
  status: 'connected' | 'processing' | 'completed' | 'interrupted' | 'error' | 'pong'
  message: string
}

export interface ProgressMessage extends BaseMessage {
  type: 'progress'
  stage: string
  progress: number
  message: string
  details: Record<string, unknown>
}

export interface ErrorMessage extends BaseMessage {
  type: 'error'
  error_code: string
  error_message: string
  details: Record<string, unknown>
}

export type WebSocketMessage = UserMessage | AgentMessage | StatusMessage | ProgressMessage | ErrorMessage

export interface AppConfig {
  name: string
  version: string
  debug: boolean
}

export interface AgentConfig {
  max_iterations: number
  reflection_attempts: number
  planner_model: string
  executor_model: string
}

export interface SandboxConfig {
  enabled: boolean
  memory_limit: string
  cpu_limit: string
  timeout: number
  network_disabled: boolean
}

export interface MemoryConfig {
  provider: string
  vector_store: string
  embedding_model: string
  short_term_limit: number
  long_term_enabled: boolean
}

export interface APIConfig {
  host: string
  port: number
  cors_origins: string[]
  websocket_path: string
}

export interface FullConfig {
  app: AppConfig
  agent: AgentConfig
  sandbox: SandboxConfig
  memory: MemoryConfig
  api: APIConfig
}

export interface ChartData {
  title: string
  type: 'line' | 'bar' | 'scatter' | 'heatmap' | 'pie'
  data: Record<string, unknown>
  options?: Record<string, unknown>
}

export interface AnalysisResult {
  id: string
  query: string
  result: string
  charts: ChartData[]
  tables: Record<string, unknown>[]
  created_at: string
}
