import { createContext, useContext, useEffect, useRef, useState, ReactNode, useCallback } from 'react'

interface WSMessage {
  job_id: string
  vendor: string
  status: string
  category?: string
  error?: string
  timestamp: string
}

interface WSContextType {
  lastMessage: WSMessage | null
  isConnected: boolean
  messages: WSMessage[]
}

const WebSocketContext = createContext<WSContextType>({ lastMessage: null, isConnected: false, messages: [] })

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null)
  const [messages, setMessages] = useState<WSMessage[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<NodeJS.Timeout>()

  const connect = useCallback(() => {
    const token = localStorage.getItem('token')
    if (!token) return
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/jobs?token=${encodeURIComponent(token)}`)

    ws.onopen = () => setIsConnected(true)
    ws.onclose = () => {
      setIsConnected(false)
      reconnectTimer.current = setTimeout(connect, 3000)
    }
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WSMessage
        setLastMessage(data)
        setMessages(prev => [data, ...prev].slice(0, 100))
      } catch {}
    }

    wsRef.current = ws
  }, [])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  return (
    <WebSocketContext.Provider value={{ lastMessage, isConnected, messages }}>
      {children}
    </WebSocketContext.Provider>
  )
}

export function useWebSocket() {
  return useContext(WebSocketContext)
}
