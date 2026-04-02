import { useState, useEffect, useRef, useCallback } from 'react'

export interface WsEvent {
  type: string
  job_id?: number
  issue_number?: number
  title?: string
  status?: string
  step?: string
  labels?: string[]
  confidence?: number
  error?: string
  timestamp: string
}

export function useWebSocket() {
  const [connected, setConnected] = useState(false)
  const [events, setEvents] = useState<WsEvent[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const ws = new WebSocket(`${protocol}//${host}/ws/events`)

    ws.onopen = () => {
      setConnected(true)
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
    }

    ws.onclose = () => {
      setConnected(false)
      // Auto-reconnect with exponential backoff
      const delay = Math.min(1000 * 2 ** Math.min(events.length, 5), 30000)
      reconnectTimeoutRef.current = setTimeout(connect, delay)
    }

    ws.onmessage = (e) => {
      try {
        const event: WsEvent = JSON.parse(e.data)
        setEvents(prev => [...prev.slice(-100), event])
      } catch {
        // Ignore non-JSON messages (pong)
      }
    }

    ws.onerror = () => {
      ws.close()
    }

    wsRef.current = ws
  }, [events.length])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { connected, events }
}
