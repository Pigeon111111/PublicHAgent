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

export interface EvaluationScoreBreakdown {
  artifact_score: number
  statistical_score: number
  process_score: number
  report_score: number
}

export interface EvaluationFinding {
  severity: 'info' | 'warning' | 'error'
  category: string
  code: string
  message: string
  details?: Record<string, unknown>
}

export interface MetricAssertion {
  metric: string
  expected: unknown
  actual: unknown
  passed: boolean
  tolerance?: string
}

export interface EvaluationReportSummary {
  id?: string
  task_family: string
  passed: boolean
  final_score: number
  summary: string
  hard_failures?: string[]
  score_breakdown?: Partial<EvaluationScoreBreakdown>
  review_status?: string
}

export interface EvaluationReport {
  id: string
  analysis_record_id: string
  session_id?: string | null
  trajectory_id: string
  task_family: string
  final_score: number
  passed: boolean
  summary: string
  report_json: {
    evaluator_version?: string
    task_family?: string
    passed?: boolean
    final_score?: number
    score_breakdown?: EvaluationScoreBreakdown
    supported_checks?: string[]
    hard_failures?: string[]
    findings?: EvaluationFinding[]
    metric_assertions?: MetricAssertion[]
    summary?: string
    artifact_paths?: Record<string, string>
  }
  review_status: 'unreviewed' | 'confirmed' | 'disputed' | 'needs_followup'
  review_label: '' | 'correct' | 'false_positive' | 'false_negative' | 'metric_mismatch' | 'report_mismatch'
  review_comment: string
  reviewed_by: string
  associated_skill: string
  created_at: string
  updated_at: string
}

export interface EvaluationReview {
  review_status: 'unreviewed' | 'confirmed' | 'disputed' | 'needs_followup'
  review_label: 'correct' | 'false_positive' | 'false_negative' | 'metric_mismatch' | 'report_mismatch'
  review_comment?: string
  reviewed_by?: string
}

export interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  evaluation_report?: EvaluationReportSummary
  task_family?: string
  evaluation_score?: number
  analysis_id?: string
  trajectory_id?: string
}

export interface TaskEvent {
  id: string
  type: 'status' | 'progress' | 'agent' | 'error'
  title: string
  message: string
  timestamp: string
  progress?: number
  stage?: string
  details?: Record<string, unknown>
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
  session_id?: string | null
  conversation_id?: string | null
  query: string
  intent: string
  status: string
  result_summary: string
  created_at: string
  updated_at: string
  steps_count: number
  trajectory_id: string
  evaluation_id: string
  task_family: string
  evaluation_score: number
  evaluation_passed: boolean
  evaluation_summary: string
  review_status: 'unreviewed' | 'confirmed' | 'disputed' | 'needs_followup'
}

export interface AnalysisDetailResponse {
  record: AnalysisRecord
  evaluation: EvaluationReport | null
}

export interface AnalysisHistoryResponse {
  records: AnalysisRecord[]
  total: number
}

export interface MethodFamilySummary {
  family: string
  title: string
  description: string
  variant_count: number
  active_count: number
  enabled_count: number
  recent_usage_count: number
  success_rate: number
  average_confidence: number
  preferred_variant: string
  match_score?: number
}

export interface MethodVariant {
  name: string
  description: string
  enabled: boolean
  category: string
  analysis_domain: string
  method_family: string
  method_variant: string
  process_signature: string
  input_schema_signature: string
  verifier_family: string
  provenance_trajectory_id: string
  confidence_score: number
  lifecycle_state: 'active' | 'candidate' | 'deprecated' | 'legacy'
  last_used_at: string
  usage_count: number
  verifier_pass_rate: number
  capability: string
  limitations: string[]
  applicable_scenarios: string[]
  is_preferred: boolean
  recent_evaluations: EvaluationReport[]
}

export interface PreferredVariantState {
  user_id: string
  family: string
  preferred_variant: string
  updated_at: string
}

export interface MethodFamilyListResponse {
  families: MethodFamilySummary[]
  total: number
}

export interface MethodVariantListResponse {
  family: string
  preferred_variant: string
  variants: MethodVariant[]
  total: number
}

export interface RerunResponse {
  analysis_id: string
  session_id: string
  query: string
  resume_available: boolean
}

export type MessageType = 'user' | 'agent' | 'status' | 'progress' | 'error' | 'interrupt' | 'resume'

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
  evaluation_report: EvaluationReportSummary
  task_family: string
  evaluation_score: number
  analysis_id: string
  trajectory_id: string
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

export interface InterruptMessage extends Partial<BaseMessage> {
  type: 'interrupt'
}

export interface ResumeMessage extends Partial<BaseMessage> {
  type: 'resume'
}

export interface CheckpointStatus {
  available: boolean
  resumable: boolean
  next_nodes: string[]
  created_at: string | null
  config: Record<string, unknown>
  summary: Record<string, unknown>
}

export interface SessionStatusResponse {
  session_id: string
  user_id: string
  status: string
  interrupted: boolean
  running: boolean
  last_error: string | null
  conversation_id?: string | null
  current_analysis_id?: string | null
  events: TaskEvent[]
  connection: Record<string, unknown> | null
  checkpoint: CheckpointStatus
}

export type WebSocketMessage =
  | UserMessage
  | AgentMessage
  | StatusMessage
  | ProgressMessage
  | ErrorMessage
  | InterruptMessage
  | ResumeMessage

export interface AppConfig {
  name: string
  version: string
  debug: boolean
}

export interface AgentConfig {
  max_iterations: number
  reflection_attempts: number
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
