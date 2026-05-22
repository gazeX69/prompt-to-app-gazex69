import http from 'http';
import { eventBus } from '../events/RuntimeEventBus.js';
import { RuntimeEventType, RuntimeEvent } from '../types/events.js';

export class PreviewDetector {
  private currentPort: number | null = null;
  private checkInterval: NodeJS.Timeout | null = null;
  private isReady: boolean = false;

  constructor() {
    this.setupListeners();
  }

  private setupListeners() {
    eventBus.onEvent(RuntimeEventType.COMMAND_STDOUT, (event: RuntimeEvent) => {
      if (this.isReady) return;
      
      const chunk = event.payload.chunk;
      if (!chunk) return;
      // Strip ANSI escape codes
      const cleanChunk = chunk.replace(/\x1B\[[0-9;]*[a-zA-Z]/g, '');
      
      // Vite output: Local:   http://localhost:5173/
      // or Local:   http://127.0.0.1:5173/
      const match = cleanChunk.match(/http:\/\/(localhost|127\.0\.0\.1):(\d+)/);
      if (match && match[2]) {
        const port = parseInt(match[2], 10);
        if (!this.currentPort) {
          this.currentPort = port;
          eventBus.emitEvent(RuntimeEventType.DEVSERVER_STARTED, { port });
          this.startHealthCheck(port);
        }
      }
    });

    eventBus.onEvent(RuntimeEventType.SESSION_COMPLETED, () => {
      this.reset();
    });

    eventBus.onEvent(RuntimeEventType.SESSION_FAILED, () => {
      this.reset();
    });
  }

  private startHealthCheck(port: number) {
    if (this.checkInterval) clearInterval(this.checkInterval);

    let attempts = 0;
    this.checkInterval = setInterval(() => {
      attempts++;
      if (attempts > 30) {
        // Stop checking after 30 attempts
        this.reset();
        return;
      }

      const req = http.get(`http://127.0.0.1:${port}`, (res) => {
        if (res.statusCode === 200 || res.statusCode === 404 || res.statusCode === 500) {
          // As long as the HTTP server responds, Vite is up
          this.isReady = true;
          this.reset();
          eventBus.emitEvent(RuntimeEventType.PREVIEW_READY, { port, url: `http://localhost:${port}` });
        }
      });

      req.on('error', () => {
        // Still waiting for it to be ready
      });
      
      req.end();
    }, 1000);
  }

  private reset() {
    if (this.checkInterval) {
      clearInterval(this.checkInterval);
      this.checkInterval = null;
    }
    this.currentPort = null;
    this.isReady = false;
  }
}

export const previewDetector = new PreviewDetector();
