import { ref } from 'vue'

/**
 * WebSocket lifecycle composable for real-time chat.
 *
 * Manages connection, exponential-backoff reconnection, and
 * a simple `send()` helper for typed JSON frames.
 *
 * The caller must wire up ``onmessage`` handling against the returned
 * ``WebSocket`` instance (or use the public ``send`` helper together
 * with a store-level message handler).
 */
export function useWebSocket() {
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectAttempts = 0
  const connected = ref(false)

  function getUrl(): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.host}/api/v1/ws`
  }

  function scheduleReconnect(): void {
    if (reconnectTimer) return
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000)
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      reconnectAttempts++
      connect()
    }, delay)
  }

  function connect(): void {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return
    ws = new WebSocket(getUrl())

    ws.onopen = () => {
      connected.value = true
      reconnectAttempts = 0
    }

    ws.onclose = () => {
      connected.value = false
      ws = null
      scheduleReconnect()
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  function disconnect(): void {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws) {
      ws.onclose = null // prevent reconnect
      ws.close()
      ws = null
    }
    connected.value = false
    reconnectAttempts = 0
  }

  function send(type: string, payload: Record<string, unknown>, id?: string): void {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type, payload, ...(id ? { id } : {}) }))
    }
  }

  return { ws, connected, connect, disconnect, send }
}
