import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Message, Conversation, FileInfo, AnalysisResult, ChartData, TaskEvent } from '@/types'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<Message[]>([])
  const currentConversation = ref<Conversation | null>(null)
  const conversations = ref<Conversation[]>([])
  const isConnected = ref(false)
  const isProcessing = ref(false)
  const currentProgress = ref(0)
  const currentStage = ref('')
  const streamingContent = ref('')
  const taskEvents = ref<TaskEvent[]>([])
  const lastError = ref('')
  const interruptRequested = ref(false)

  const messageCount = computed(() => messages.value.length)

  function addMessage(message: Message) {
    messages.value.push(message)
    if (currentConversation.value) {
      currentConversation.value.messages.push(message)
      currentConversation.value.message_count = currentConversation.value.messages.length
    }
  }

  function clearMessages() {
    messages.value = []
    streamingContent.value = ''
    taskEvents.value = []
    lastError.value = ''
    interruptRequested.value = false
  }

  function setConnected(connected: boolean) {
    isConnected.value = connected
  }

  function setProcessing(processing: boolean) {
    isProcessing.value = processing
    if (!processing) {
      currentProgress.value = 0
      currentStage.value = ''
      interruptRequested.value = false
    }
  }

  function updateProgress(progress: number, stage: string) {
    currentProgress.value = progress
    currentStage.value = stage
  }

  function addTaskEvent(event: TaskEvent) {
    taskEvents.value.push(event)
    if (taskEvents.value.length > 200) {
      taskEvents.value = taskEvents.value.slice(-200)
    }
  }

  function clearTaskEvents() {
    taskEvents.value = []
    lastError.value = ''
  }

  function setLastError(error: string) {
    lastError.value = error
  }

  function setInterruptRequested(requested: boolean) {
    interruptRequested.value = requested
  }

  function appendStreamContent(content: string) {
    streamingContent.value += content
  }

  function clearStreamContent() {
    streamingContent.value = ''
  }

  function setCurrentConversation(conversation: Conversation | null) {
    currentConversation.value = conversation
    messages.value = conversation?.messages || []
  }

  function setConversations(list: Conversation[]) {
    conversations.value = list
  }

  return {
    messages,
    currentConversation,
    conversations,
    isConnected,
    isProcessing,
    currentProgress,
    currentStage,
    streamingContent,
    taskEvents,
    lastError,
    interruptRequested,
    messageCount,
    addMessage,
    clearMessages,
    setConnected,
    setProcessing,
    updateProgress,
    addTaskEvent,
    clearTaskEvents,
    setLastError,
    setInterruptRequested,
    appendStreamContent,
    clearStreamContent,
    setCurrentConversation,
    setConversations,
  }
})

export const useFileStore = defineStore('file', () => {
  const files = ref<FileInfo[]>([])
  const totalFiles = ref(0)
  const uploadingFiles = ref<File[]>([])
  const uploadProgress = ref<Record<string, number>>({})

  function setFiles(fileList: FileInfo[], total: number) {
    files.value = fileList
    totalFiles.value = total
  }

  function addFile(file: FileInfo) {
    files.value.unshift(file)
    totalFiles.value++
  }

  function removeFile(fileId: string) {
    const index = files.value.findIndex(f => f.id === fileId)
    if (index !== -1) {
      files.value.splice(index, 1)
      totalFiles.value--
    }
  }

  function setUploadingFiles(fileList: File[]) {
    uploadingFiles.value = fileList
  }

  function setUploadProgress(fileId: string, progress: number) {
    uploadProgress.value[fileId] = progress
  }

  function clearUploadProgress(fileId: string) {
    delete uploadProgress.value[fileId]
  }

  return {
    files,
    totalFiles,
    uploadingFiles,
    uploadProgress,
    setFiles,
    addFile,
    removeFile,
    setUploadingFiles,
    setUploadProgress,
    clearUploadProgress,
  }
})

export const useAnalysisStore = defineStore('analysis', () => {
  const currentResult = ref<AnalysisResult | null>(null)
  const history = ref<AnalysisResult[]>([])
  const charts = ref<ChartData[]>([])
  const tables = ref<Record<string, unknown>[]>([])

  function setCurrentResult(result: AnalysisResult | null) {
    currentResult.value = result
    charts.value = result?.charts || []
    tables.value = result?.tables || []
  }

  function addChart(chart: ChartData) {
    charts.value.push(chart)
  }

  function addTable(table: Record<string, unknown>) {
    tables.value.push(table)
  }

  function clearResults() {
    currentResult.value = null
    charts.value = []
    tables.value = []
  }

  function setHistory(results: AnalysisResult[]) {
    history.value = results
  }

  return {
    currentResult,
    history,
    charts,
    tables,
    setCurrentResult,
    addChart,
    addTable,
    clearResults,
    setHistory,
  }
})
