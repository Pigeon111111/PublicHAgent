import type { SessionStatusResponse, WebSocketMessage } from '@/types'

type MessageHandler = (message: WebSocketMessage) => void
type ConnectionHandler = (connected: boolean) => void

let ws: WebSocket | null = null
let reconnectAttempts = 0
const maxReconnectAttempts = 5
const reconnectDelay = 3000
let heartbeatInterval: number | null = null
let messageHandler: MessageHandler | null = null
let connectionHandler: ConnectionHandler | null = null
let manualClose = false

function buildWebSocketUrl(sessionId: string): string {
  const configuredUrl = import.meta.env.VITE_WS_BASE_URL as string | undefined
  if (configuredUrl) {
    return `${configuredUrl.replace(/\/$/, '')}/ws/${sessionId}`
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/ws/${sessionId}`
}

function buildHttpUrl(path: string): string {
  const configuredApiUrl = import.meta.env.VITE_API_BASE_URL as string | undefined
  if (configuredApiUrl) {
    return `${configuredApiUrl.replace(/\/$/, '')}${path}`
  }

  const configuredWsUrl = import.meta.env.VITE_WS_BASE_URL as string | undefined
  if (configuredWsUrl) {
    return `${configuredWsUrl.replace(/^ws/, 'http').replace(/\/$/, '')}${path}`
  }

  return `${window.location.origin}${path}`
}

export function connectWebSocket(
  sessionId: string,
  handler: MessageHandler,
  onConnectionChange?: ConnectionHandler,
): Promise<void> {
  return new Promise((resolve, reject) => {
    manualClose = false
    messageHandler = handler
    connectionHandler = onConnectionChange || null

    if (ws && ws.readyState === WebSocket.OPEN) {
      resolve()
      return
    }

    ws = new WebSocket(buildWebSocketUrl(sessionId))

    ws.onopen = () => {
      reconnectAttempts = 0
      connectionHandler?.(true)
      startHeartbeat()
      resolve()
    }

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as WebSocketMessage
        messageHandler?.(message)
      } catch (error) {
        console.error('解析 WebSocket 消息失败:', error)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket 错误:', error)
      reject(error)
    }

    ws.onclose = () => {
      stopHeartbeat()
      connectionHandler?.(false)
      ws = null
      if (!manualClose) {
        attemptReconnect(sessionId)
      }
    }
  })
}

function attemptReconnect(sessionId: string) {
  if (reconnectAttempts >= maxReconnectAttempts) {
    console.error('达到最大重连次数，停止重连')
    return
  }

  reconnectAttempts += 1
  window.setTimeout(() => {
    if (messageHandler && !manualClose) {
      connectWebSocket(sessionId, messageHandler, connectionHandler || undefined).catch(console.error)
    }
  }, reconnectDelay)
}

function startHeartbeat() {
  stopHeartbeat()
  heartbeatInterval = window.setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping' }))
    }
  }, 30000)
}

function stopHeartbeat() {
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval)
    heartbeatInterval = null
  }
}

export function disconnectWebSocket() {
  manualClose = true
  stopHeartbeat()
  if (ws) {
    ws.close()
    ws = null
  }
  messageHandler = null
  connectionHandler = null
}

export function sendMessage(message: Record<string, unknown>): boolean {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      ...message,
      timestamp: new Date().toISOString(),
    }))
    return true
  }

  console.error('WebSocket 未连接')
  return false
}

export function interruptExecution(): boolean {
  return sendMessage({ type: 'interrupt' })
}

export function resumeExecution(): boolean {
  return sendMessage({ type: 'resume' })
}

export async function fetchSessionStatus(sessionId: string): Promise<SessionStatusResponse | null> {
  const response = await fetch(buildHttpUrl(`/ws/${sessionId}/status`))
  if (!response.ok) {
    return null
  }
  return await response.json() as SessionStatusResponse
}

export function isConnected(): boolean {
  return ws !== null && ws.readyState === WebSocket.OPEN
}
