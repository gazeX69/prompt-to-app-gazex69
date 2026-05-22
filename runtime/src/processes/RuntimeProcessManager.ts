import { execa, type Subprocess } from 'execa';
import kill from 'tree-kill';
import { eventBus } from '../events/RuntimeEventBus.js';
import { RuntimeEventType } from '../types/events.js';

export interface ProcessOptions {
  command: string;
  args: string[];
  cwd?: string;
  env?: Record<string, string>;
}

export class RuntimeProcessManager {
  private activeProcesses: Map<string, Subprocess> = new Map();

  constructor() {}

  public async spawnCommand(id: string, options: ProcessOptions): Promise<void> {
    const { command, args, cwd, env } = options;
    
    // Convert 'npm' to 'npm.cmd' on Windows to prevent spawn issues
    const isWindows = process.platform === 'win32';
    const cmd = (isWindows && command === 'npm') ? 'npm.cmd' : command;

    eventBus.emitEvent(RuntimeEventType.COMMAND_STARTED, { id, cmd, args, cwd });

    try {
      const childProcess = execa(cmd, args, {
        cwd: cwd || process.cwd(),
        env: { ...process.env, ...env },
        windowsHide: true,
        stripFinalNewline: false,
      });

      this.activeProcesses.set(id, childProcess);

      if (childProcess.stdout) {
        childProcess.stdout.on('data', (data: Buffer) => {
          const chunk = data.toString('utf-8');
          eventBus.emitEvent(RuntimeEventType.COMMAND_STDOUT, { id, chunk });
        });
      }

      if (childProcess.stderr) {
        childProcess.stderr.on('data', (data: Buffer) => {
          const chunk = data.toString('utf-8');
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
      eventBus.emitEvent(RuntimeEventType.COMMAND_COMPLETED, { 
        id, 
        exitCode: error.exitCode ?? 1, 
        success: false,
        error: error.message
      });
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

  public async killAll(): Promise<void> {
    const promises = Array.from(this.activeProcesses.keys()).map(id => this.killCommand(id));
    await Promise.all(promises);
  }
}

export const processManager = new RuntimeProcessManager();
