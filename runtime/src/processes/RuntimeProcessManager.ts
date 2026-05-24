import { execa, type Subprocess } from 'execa';
import kill from 'tree-kill';
import { eventBus } from '../events/RuntimeEventBus.js';
import { RuntimeEventType } from '../types/events.js';
import { allocatePort, type PortAllocationResult } from '../network/PortPreflight.js';
import { previewDetector } from '../preview/PreviewDetector.js';
import { classifyProcessFailure, createRuntimeError } from '../errors/RuntimeErrors.js';

export interface ProcessOptions {
  command: string;
  args: string[];
  cwd?: string;
  env?: Record<string, string>;
  lifecycle?: {
    requestedPort?: number;
    selectedPort?: number;
    fallbackUsed?: boolean;
  };
}

export interface DevServerOptions {
  cwd: string;
  requestedPort?: number;
  autoIncrementPorts?: boolean;
  maxPortAttempts?: number;
  healthTimeoutMs?: number;
}

export interface RuntimeSession {
  id: string;
  requestedPort?: number;
  selectedPort?: number;
  fallbackUsed?: boolean;
  portAllocation?: PortAllocationResult;
  state: 'PREPARING' | 'CHECKING_PORTS' | 'STARTING' | 'HEALTHCHECK' | 'READY' | 'FAILED';
}

export class RuntimeProcessManager {
  private activeProcesses: Map<string, Subprocess> = new Map();
  private runtimeSessions: Map<string, RuntimeSession> = new Map();

  constructor() {
    eventBus.onEvent(RuntimeEventType.RUNTIME_READY, (event) => {
      const id = event.payload.id;
      if (!id) return;
      const session = this.runtimeSessions.get(id);
      if (session) session.state = 'READY';
    });
    eventBus.onEvent(RuntimeEventType.RUNTIME_HEALTHCHECK_FAILED, (event) => {
      const id = event.payload.id;
      if (!id) return;
      const session = this.runtimeSessions.get(id);
      if (session) session.state = 'FAILED';
    });
  }

  public async spawnCommand(id: string, options: ProcessOptions): Promise<void> {
    const { command, args, cwd, env } = options;
    
    // Convert 'npm' to 'npm.cmd' on Windows to prevent spawn issues
    const isWindows = process.platform === 'win32';
    const cmd = (isWindows && command === 'npm') ? 'npm.cmd' : command;
    let stderrBuffer = '';

    eventBus.emitEvent(RuntimeEventType.COMMAND_STARTED, { id, cmd, args, cwd });

    try {
      const childProcess = execa(cmd, args, {
        cwd: cwd || process.cwd(),
        env: { ...process.env, ...env },
        windowsHide: true,
        stripFinalNewline: false,
      });

      this.activeProcesses.set(id, childProcess);
      eventBus.emitLifecycleEvent('runtime.spawn.started', {
        workspaceId: id,
        sessionId: id,
        requestedPort: options.lifecycle?.requestedPort,
        selectedPort: options.lifecycle?.selectedPort,
        fallbackUsed: options.lifecycle?.fallbackUsed,
        processPid: childProcess.pid,
        message: `Runtime spawn started${options.lifecycle?.selectedPort ? ` on port ${options.lifecycle.selectedPort}` : ''}`,
      });

      if (childProcess.stdout) {
        childProcess.stdout.on('data', (data: Buffer) => {
          const chunk = data.toString('utf-8');
          eventBus.emitEvent(RuntimeEventType.COMMAND_STDOUT, { id, chunk });
        });
      }

      if (childProcess.stderr) {
        childProcess.stderr.on('data', (data: Buffer) => {
          const chunk = data.toString('utf-8');
          stderrBuffer += chunk;
          eventBus.emitEvent(RuntimeEventType.COMMAND_STDERR, { id, chunk });
        });
      }

      const result = await childProcess;
      
      this.activeProcesses.delete(id);
      eventBus.emitEvent(RuntimeEventType.COMMAND_COMPLETED, { 
        id, 
        exitCode: result.exitCode, 
        success: result.exitCode === 0 
      });

    } catch (error: any) {
      this.activeProcesses.delete(id);
      const session = this.runtimeSessions.get(id);
      if (session && session.state !== 'READY') {
        session.state = 'FAILED';
        const code = classifyProcessFailure(error.exitCode, stderrBuffer || error.stderr);
        const runtimeError = createRuntimeError(
          code,
          code === 'RUNTIME_DEPENDENCY_MISSING'
            ? 'Runtime process failed because a dependency is missing'
            : 'Runtime process crashed before readiness',
          {
            exitCode: error.exitCode ?? 1,
            command: cmd,
            args,
            cwd: cwd || process.cwd(),
          },
        );
        eventBus.emitLifecycleEvent('runtime.crashed', {
          workspaceId: id,
          sessionId: id,
          requestedPort: options.lifecycle?.requestedPort,
          selectedPort: options.lifecycle?.selectedPort,
          fallbackUsed: options.lifecycle?.fallbackUsed,
          error: runtimeError,
          message: runtimeError.message,
        });
        eventBus.emitEvent(RuntimeEventType.RUNTIME_SPAWN_FAILED, {
          id,
          error: runtimeError,
          exitCode: error.exitCode ?? 1,
        });
      }
      eventBus.emitEvent(RuntimeEventType.COMMAND_COMPLETED, { 
        id, 
        exitCode: error.exitCode ?? 1, 
        success: false,
        error: error.message
      });
    }
  }

  public async startDevServer(id: string, options: DevServerOptions): Promise<RuntimeSession> {
    const requestedPort = options.requestedPort ?? 5173;
    const autoIncrementPorts = options.autoIncrementPorts ?? true;
    const maxPortAttempts = options.maxPortAttempts ?? 10;
    const healthTimeoutMs = options.healthTimeoutMs ?? 30000;

    const session: RuntimeSession = {
      id,
      requestedPort,
      state: 'PREPARING',
    };
    this.runtimeSessions.set(id, session);

    try {
      session.state = 'CHECKING_PORTS';
      const allocation = await allocatePort(requestedPort, autoIncrementPorts, maxPortAttempts);
      session.selectedPort = allocation.selectedPort;
      session.fallbackUsed = allocation.fallbackUsed;
      session.portAllocation = allocation;

      const firstConflict = allocation.attempts.find((attempt) => attempt.occupied);
      if (firstConflict) {
        const runtimeError = createRuntimeError(
          'RUNTIME_PORT_CONFLICT',
          allocation.fallbackUsed
            ? `Port ${requestedPort} is occupied; using fallback port ${allocation.selectedPort}`
            : `Port ${requestedPort} is occupied`,
          {
            requestedPort,
            selectedPort: allocation.selectedPort,
            fallbackUsed: allocation.fallbackUsed,
            conflict: firstConflict,
            attempts: allocation.attempts,
          },
        );
        eventBus.emitEvent(RuntimeEventType.RUNTIME_PORT_CONFLICT, {
          id,
          error: runtimeError,
          code: runtimeError.code,
          requestedPort,
          selectedPort: allocation.selectedPort,
          fallbackUsed: allocation.fallbackUsed,
          conflict: firstConflict,
          attempts: allocation.attempts,
          message: runtimeError.message,
        });
        eventBus.emitLifecycleEvent('runtime.port.conflict', {
          workspaceId: id,
          sessionId: id,
          requestedPort,
          selectedPort: allocation.selectedPort,
          fallbackUsed: allocation.fallbackUsed,
          error: runtimeError,
          message: runtimeError.message,
        });
      }

      session.state = 'STARTING';
      previewDetector.registerSessionMetadata(id, {
        requestedPort,
        fallbackUsed: allocation.fallbackUsed,
      });
      const args = [
        'run',
        'dev',
        '--',
        '--host',
        '127.0.0.1',
        '--port',
        String(allocation.selectedPort),
        '--strictPort',
      ];
      this.spawnCommand(id, {
        command: 'npm',
        args,
        cwd: options.cwd,
        env: { PORT: String(allocation.selectedPort) },
        lifecycle: {
          requestedPort,
          selectedPort: allocation.selectedPort,
          fallbackUsed: allocation.fallbackUsed,
        },
      }).catch(() => undefined);

      session.state = 'HEALTHCHECK';
      previewDetector.startHealthCheck(allocation.selectedPort, id, healthTimeoutMs, {
        requestedPort,
        fallbackUsed: allocation.fallbackUsed,
      });
      return session;
    } catch (error: any) {
      session.state = 'FAILED';
      const runtimeError = createRuntimeError(
        error.code === 'RUNTIME_PORT_CONFLICT' ? 'RUNTIME_PORT_CONFLICT' : 'RUNTIME_PROCESS_CRASH',
        error.message || 'Runtime spawn failed',
        {
          requestedPort,
          attempts: error.attempts || [],
        },
        error.code === 'RUNTIME_PORT_CONFLICT' ? { severity: 'error', recoverable: true } : {},
      );
      eventBus.emitEvent(RuntimeEventType.RUNTIME_SPAWN_FAILED, {
        id,
        error: runtimeError,
        code: runtimeError.code,
        requestedPort,
        attempts: error.attempts || [],
        message: runtimeError.message,
      });
      if (runtimeError.code === 'RUNTIME_PORT_CONFLICT') {
        eventBus.emitLifecycleEvent('runtime.port.conflict', {
          workspaceId: id,
          sessionId: id,
          requestedPort,
          fallbackUsed: false,
          error: runtimeError,
          message: runtimeError.message,
        });
      }
      eventBus.emitLifecycleEvent('runtime.spawn.failed', {
        workspaceId: id,
        sessionId: id,
        requestedPort,
        error: runtimeError,
        message: runtimeError.message,
      });
      throw error;
    }
  }

  public killCommand(id: string): Promise<boolean> {
    return new Promise((resolve) => {
      const childProcess = this.activeProcesses.get(id);
      if (!childProcess || childProcess.pid === undefined) {
        resolve(false);
        return;
      }

      // Use tree-kill to ensure entire process tree (e.g. npm -> vite) is killed
      kill(childProcess.pid, 'SIGKILL', (err) => {
        if (err) {
          console.error(`Failed to kill process tree for ${id}:`, err);
          resolve(false);
        } else {
          this.activeProcesses.delete(id);
          resolve(true);
        }
      });
    });
  }

  public getActiveProcessIds(): string[] {
    return Array.from(this.activeProcesses.keys());
  }

  public getRuntimeSessions(): RuntimeSession[] {
    return Array.from(this.runtimeSessions.values());
  }

  public async killAll(): Promise<void> {
    const promises = Array.from(this.activeProcesses.keys()).map(id => this.killCommand(id));
    await Promise.all(promises);
  }
}

export const processManager = new RuntimeProcessManager();
