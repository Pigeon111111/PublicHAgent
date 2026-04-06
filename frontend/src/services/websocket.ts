import type { WebSocketMessage } from '@/types'

type MessageHandler = (message: WebSocketMessage) => void

let ws: WebSocket | null = null
let reconnectAttempts = 0
const maxReconnectAttempts = 5
const reconnectDelay = 3000
let heartbeatInterval: number | null = null
let messageHandler: MessageHandler | null = null

export function connectWebSocket(sessionId: string, handler: MessageHandler): Promise<void> {
  return new Promise((resolve, reject) => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/ws/${sessionId}`

    messageHandler = handler
    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      console.log('WebSocket 连接成功')
      reconnectAttempts = 0
      startHeartbeat()
      resolve()
    }

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as WebSocketMessage
        if (messageHandler) {
          messageHandler(message)
        }
      } catch (error) {
        console.error('解析 WebSocket 消息失败:', error)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket 错误:', error)
      reject(error)
    }

    ws.onclose = () => {
      console.log('WebSocket 连接关闭')
      stopHeartbeat()
      attemptReconnect(sessionId)
    }
  })
}

function attemptReconnect(sessionId: string) {
  if (reconnectAttempts >= maxReconnectAttempts) {
    console.error('达到最大重连次数，停止重连')
    return
  }

  reconnectAttempts++
  console.log(`尝试重连 (${reconnectAttempts}/${maxReconnectAttempts})...`)

  setTimeout(() => {
    if (messageHandler) {
      connectWebSocket(sessionId, messageHandler).catch(console.error)
    }
  }, reconnectDelay)
}

function startHeartbeat() {
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
  stopHeartbeat()
  if (ws) {
    ws.close()
    ws = null
  }
  messageHandler = null
}

export function sendMessage(message: Record<string, unknown>) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      ...message,
      timestamp: new Date().toISOString(),
    }))
  } else {
    console.error('WebSocket 未连接')
  }
}

export function interruptExecution() {
  sendMessage({ type: 'interrupt' })
}

export function isConnected(): boolean {
  return ws !== null && ws.readyState === WebSocket.OPEN
}
