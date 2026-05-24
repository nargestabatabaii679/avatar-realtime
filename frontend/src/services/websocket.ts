import { io, type Socket } from 'socket.io-client'
import type { WSJobProgressEvent, WSConversationEvent, WSSystemEvent } from '@/types'

const WS_URL = import.meta.env.VITE_WS_URL ?? '/'

type EventHandler<T> = (data: T) => void
type UnsubscribeFn = () => void

class WebSocketService {
  private socket: Socket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 10
  private reconnectDelay = 1000
  private isConnecting = false
  private jobHandlers = new Map<string, Set<EventHandler<WSJobProgressEvent>>>()
  private conversationHandlers = new Map<string, Set<EventHandler<WSConversationEvent>>>()
  private systemHandlers = new Set<EventHandler<WSSystemEvent>>()
  private connectHandlers = new Set<() => void>()
  private disconnectHandlers = new Set<() => void>()

  connect(token: string): void {
    if (this.socket?.connected || this.isConnecting) return
    this.isConnecting = true

    this.socket = io(WS_URL, {
      auth: { token },
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: this.maxReconnectAttempts,
      reconnectionDelay: this.reconnectDelay,
      reconnectionDelayMax: 10000,
      timeout: 20000,
    })

    this.socket.on('connect', () => {
      this.isConnecting = false
      this.reconnectAttempts = 0
      if (import.meta.env.DEV) {
        console.debug('[WS] Connected:', this.socket?.id)
      }
      this.connectHandlers.forEach((h) => h())
    })

    this.socket.on('disconnect', (reason) => {
      if (import.meta.env.DEV) {
        console.debug('[WS] Disconnected:', reason)
      }
      this.disconnectHandlers.forEach((h) => h())
    })

    this.socket.on('connect_error', (error) => {
      this.isConnecting = false
      console.warn('[WS] Connection error:', error.message)
    })

    // Job progress events
    this.socket.on('job_progress', (data: WSJobProgressEvent) => {
      const handlers = this.jobHandlers.get(data.job_id)
      if (handlers) {
        handlers.forEach((h) => h(data))
      }
      // Also trigger 'all' handlers
      const allHandlers = this.jobHandlers.get('*')
      if (allHandlers) {
        allHandlers.forEach((h) => h(data))
      }
    })

    // Conversation events
    this.socket.on('conversation_message', (data: WSConversationEvent) => {
      const handlers = this.conversationHandlers.get(data.conversation_id)
      if (handlers) {
        handlers.forEach((h) => h(data))
      }
    })

    // System events
    this.socket.on('system_alert', (data: WSSystemEvent) => {
      this.systemHandlers.forEach((h) => h(data))
    })
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect()
      this.socket = null
    }
    this.isConnecting = false
  }

  get isConnected(): boolean {
    return this.socket?.connected ?? false
  }

  // Job progress subscriptions
  subscribeToJob(jobId: string, handler: EventHandler<WSJobProgressEvent>): UnsubscribeFn {
    if (!this.jobHandlers.has(jobId)) {
      this.jobHandlers.set(jobId, new Set())
    }
    this.jobHandlers.get(jobId)!.add(handler)

    // Emit join event
    this.socket?.emit('subscribe_job', { job_id: jobId })

    return () => {
      const handlers = this.jobHandlers.get(jobId)
      if (handlers) {
        handlers.delete(handler)
        if (handlers.size === 0) {
          this.jobHandlers.delete(jobId)
          this.socket?.emit('unsubscribe_job', { job_id: jobId })
        }
      }
    }
  }

  // Subscribe to all job events
  subscribeToAllJobs(handler: EventHandler<WSJobProgressEvent>): UnsubscribeFn {
    if (!this.jobHandlers.has('*')) {
      this.jobHandlers.set('*', new Set())
    }
    this.jobHandlers.get('*')!.add(handler)
    return () => {
      const handlers = this.jobHandlers.get('*')
      if (handlers) {
        handlers.delete(handler)
      }
    }
  }

  // Conversation subscriptions
  subscribeToConversation(
    conversationId: string,
    handler: EventHandler<WSConversationEvent>
  ): UnsubscribeFn {
    if (!this.conversationHandlers.has(conversationId)) {
      this.conversationHandlers.set(conversationId, new Set())
    }
    this.conversationHandlers.get(conversationId)!.add(handler)
    this.socket?.emit('join_conversation', { conversation_id: conversationId })

    return () => {
      const handlers = this.conversationHandlers.get(conversationId)
      if (handlers) {
        handlers.delete(handler)
        if (handlers.size === 0) {
          this.conversationHandlers.delete(conversationId)
          this.socket?.emit('leave_conversation', { conversation_id: conversationId })
        }
      }
    }
  }

  // System events
  subscribeToSystemEvents(handler: EventHandler<WSSystemEvent>): UnsubscribeFn {
    this.systemHandlers.add(handler)
    return () => this.systemHandlers.delete(handler)
  }

  // Connection state handlers
  onConnect(handler: () => void): UnsubscribeFn {
    this.connectHandlers.add(handler)
    return () => this.connectHandlers.delete(handler)
  }

  onDisconnect(handler: () => void): UnsubscribeFn {
    this.disconnectHandlers.add(handler)
    return () => this.disconnectHandlers.delete(handler)
  }

  // Emit events
  emit(event: string, data?: unknown): void {
    this.socket?.emit(event, data)
  }

  // Send audio chunk for realtime conversation
  sendAudioChunk(chunk: ArrayBuffer): void {
    this.socket?.emit('audio_chunk', chunk)
  }
}

// Singleton instance
export const wsService = new WebSocketService()
export default wsService
