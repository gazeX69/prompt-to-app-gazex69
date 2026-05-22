import { io, Socket } from 'socket.io-client'
import { ENV } from '../config/env'

class SocketService {
  private socket: Socket | null = null

  connect(): Socket {
    if (!this.socket) {
      this.socket = io(ENV.WS_URL, {
        transports: ["polling", "websocket"],
        reconnection: true,
        reconnectionAttempts: Infinity,
        reconnectionDelay: 1000,
      })

      console.log(`[Socket] Connecting to ${ENV.WS_URL}...`)

      this.socket.on('connect', () => {
        console.log(`[Socket] Connected to backend WebSocket`)
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

      this.socket.io.engine.on('upgrade', () => {
        console.log(`[Socket] Transport upgraded to ${this.socket?.io.engine.transport.name}`)
      })
    }
    return this.socket
  }

  get(): Socket {
    if (!this.socket) {
      return this.connect()
    }
    return this.socket
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect()
      this.socket = null
    }
  }
}

export const socketService = new SocketService()
