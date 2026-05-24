import http from 'http';
import { eventBus } from '../events/RuntimeEventBus.js';
import { RuntimeEventType, RuntimeEvent } from '../types/events.js';
import { createRuntimeError } from '../errors/RuntimeErrors.js';

export class PreviewDetector {
  private currentPort: number | null = null;
  private checkInterval: NodeJS.Timeout | null = null;
  private isReady: boolean = false;
  private activeSessionId: string | null = null;
  private activeRequestedPort: number | undefined;
  private activeFallbackUsed: boolean | undefined;
  private sessionMetadata: Map<string, { requestedPort?: number; fallbackUsed?: boolean }> = new Map();

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
          eventBus.emitEvent(RuntimeEventType.DEVSERVER_STARTED, { id: event.payload.id, port });
          this.startHealthCheck(port, event.payload.id);
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

  public registerSessionMetadata(id: string, metadata: { requestedPort?: number; fallbackUsed?: boolean }) {
    this.sessionMetadata.set(id, metadata);
  }

  public startHealthCheck(
    port: number,
    id?: string,
    timeoutMs = 30000,
    metadata: { requestedPort?: number; fallbackUsed?: boolean } = {},
  ) {
    if (this.checkInterval) clearInterval(this.checkInterval);

    this.currentPort = port;
    this.activeSessionId = id || null;
    const registeredMetadata = id ? this.sessionMetadata.get(id) : undefined;
    this.activeRequestedPort = metadata.requestedPort ?? registeredMetadata?.requestedPort;
    this.activeFallbackUsed = metadata.fallbackUsed ?? registeredMetadata?.fallbackUsed;
    eventBus.emitEvent(RuntimeEventType.RUNTIME_HEALTHCHECK_STARTED, { id, port, timeoutMs });
    eventBus.emitLifecycleEvent('runtime.healthcheck.started', {
      workspaceId: id,
      sessionId: id,
      requestedPort: this.activeRequestedPort,
      selectedPort: port,
      fallbackUsed: this.activeFallbackUsed,
      message: `Runtime healthcheck started on port ${port}`,
    });

    let attempts = 0;
    const maxAttempts = Math.max(1, Math.ceil(timeoutMs / 1000));
    this.checkInterval = setInterval(() => {
      attempts++;
      if (attempts > maxAttempts) {
        const runtimeError = createRuntimeError(
          'RUNTIME_HEALTH_TIMEOUT',
          `Runtime health check timed out on port ${port}`,
          { port, timeoutMs, attempts },
        );
        eventBus.emitEvent(RuntimeEventType.RUNTIME_HEALTHCHECK_FAILED, {
          id: this.activeSessionId,
          port,
          error: runtimeError,
          code: 'RUNTIME_HEALTH_TIMEOUT',
          message: `Runtime health check timed out on port ${port}`,
          timeoutMs,
        });
        eventBus.emitLifecycleEvent('runtime.healthcheck.failed', {
          workspaceId: this.activeSessionId || undefined,
          sessionId: this.activeSessionId || undefined,
          requestedPort: this.activeRequestedPort,
          selectedPort: port,
          fallbackUsed: this.activeFallbackUsed,
          error: runtimeError,
          message: runtimeError.message,
        });
        this.reset();
        return;
      }

      const req = http.get(`http://127.0.0.1:${port}`, (res) => {
        res.resume();
        if (res.statusCode === 200 || res.statusCode === 404 || res.statusCode === 500) {
          // As long as the HTTP server responds, Vite is up
          this.isReady = true;
          eventBus.emitEvent(RuntimeEventType.RUNTIME_READY, {
            id: this.activeSessionId,
            port,
            url: `http://localhost:${port}`,
            statusCode: res.statusCode,
          });
          eventBus.emitLifecycleEvent('runtime.ready', {
            workspaceId: this.activeSessionId || undefined,
            sessionId: this.activeSessionId || undefined,
            requestedPort: this.activeRequestedPort,
            selectedPort: port,
            fallbackUsed: this.activeFallbackUsed,
            message: `Runtime ready on port ${port}`,
          });
          eventBus.emitEvent(RuntimeEventType.PREVIEW_READY, {
            id: this.activeSessionId,
            port,
            url: `http://localhost:${port}`,
          });
          this.reset();
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
    this.activeRequestedPort = undefined;
    this.activeFallbackUsed = undefined;
  }
}

export const previewDetector = new PreviewDetector();
