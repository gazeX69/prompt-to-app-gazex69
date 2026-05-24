import { io, Socket } from 'socket.io-client'
import { ENV } from '../config/env'

class SocketService {
  private socket: Socket | null = null

  connect(): Socket {
    if (!this.socket) {
      console.log(`[Socket] Creating singleton connection to ${ENV.WS_URL}...`)
      this.socket = io(ENV.WS_URL, {
        transports: ["websocket"],
        reconnection: true,
        reconnectionAttempts: Infinity,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
      })

      this.socket.on('connect', () => {
        console.log(`[Socket] Connected (id=${this.socket?.id})`)
      })

      this.socket.on('disconnect', (reason) => {
        console.warn(`[Socket] Disconnected: ${reason}`)
      })

      this.socket.on('connect_error', (error) => {
        console.error(`[Socket] Connection error:`, error.message)
      })

      this.socket.io.on('reconnect_attempt', (attempt) => {
        console.log(`[Socket] Reconnecting (attempt ${attempt})...`)
      })

      this.socket.io.on('reconnect', () => {
        console.log(`[Socket] Successfully reconnected!`)
      })
    }
    return this.socket
  }

  get(): Socket | null {
    return this.socket
  }

  isConnected(): boolean {
    return this.socket?.connected ?? false
  }

  /** Only for app teardown — DO NOT call on component unmount */
  destroy() {
    if (this.socket) {
      this.socket.removeAllListeners()
      this.socket.disconnect()
      this.socket = null
    }
  }
}

export const socketService = new SocketService()
