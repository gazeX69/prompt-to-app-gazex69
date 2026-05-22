import { nanoid } from 'nanoid';
import fs from 'fs/promises';
import path from 'path';
import { eventBus } from '../events/RuntimeEventBus.js';
import { RuntimeEventType, RuntimeEvent } from '../types/events.js';

export class WorkspaceManager {
  private baseDir: string;
  private currentWorkspaceId: string | null = null;
  private currentWorkspacePath: string | null = null;

  constructor(baseDir: string) {
    this.baseDir = baseDir;
    this.initEventLogging();
  }

  private initEventLogging() {
    eventBus.onEvent('*', async (event: RuntimeEvent) => {
      if (!this.currentWorkspacePath) return;

      const worklogPath = path.join(this.currentWorkspacePath, 'WORKLOG.md');
      const timestamp = new Date(event.timestamp).toISOString();
      // Avoid writing massive stringified buffers
      let safePayload = event.payload;
      if (typeof safePayload === 'object' && safePayload !== null) {
        const payloadStr = JSON.stringify(safePayload);
        if (payloadStr.length > 500) {
          safePayload = { ...safePayload, _truncated: true, chunk: typeof safePayload.chunk === 'string' ? safePayload.chunk.substring(0, 100) + '...' : undefined };
        }
      }
      
      const logEntry = `- [${timestamp}] **${event.type}**: ${JSON.stringify(safePayload)}\n`;

      try {
        await fs.appendFile(worklogPath, logEntry);
      } catch (err) {
        console.error('Failed to write to WORKLOG.md', err);
      }

      if (event.type === RuntimeEventType.SESSION_FAILED || event.payload?.error) {
        const errorLogPath = path.join(this.currentWorkspacePath, 'ERROR_LOG.md');
        const errorEntry = `- [${timestamp}] **${event.type}**: ${JSON.stringify(safePayload)}\n`;
        try {
          await fs.appendFile(errorLogPath, errorEntry);
        } catch (err) {
          console.error('Failed to write to ERROR_LOG.md', err);
        }
      }
    });
  }

  public async createWorkspace(): Promise<{ id: string; path: string }> {
    const id = nanoid(10);
    const workspacePath = path.resolve(this.baseDir, id);

    // Path Guard: prevent directory traversal outside of the base directory
    if (!workspacePath.startsWith(path.resolve(this.baseDir))) {
      throw new Error(`Path violation: Attempted to create workspace outside of ${this.baseDir}`);
    }

    await fs.mkdir(workspacePath, { recursive: true });

    this.currentWorkspaceId = id;
    this.currentWorkspacePath = workspacePath;

    // Generate Governance files
    await this.generateGovernanceFiles(workspacePath, id);

    eventBus.emitEvent(RuntimeEventType.SESSION_STARTED, { workspaceId: id, workspacePath });

    return { id, path: workspacePath };
  }

  private async generateGovernanceFiles(workspacePath: string, id: string) {
    const files = {
      'README.md': `# Workspace ${id}\n\nAuto-generated runtime workspace.`,
      'TASK.md': `# Task Tracking\n\n- [ ] Initial scaffolding`,
      'PLAN.md': `# Execution Plan\n\n1. Scaffold template\n2. Install dependencies\n3. Start dev server`,
      'ARCHITECTURE_MAP.md': `# Architecture Map\n\nEmpty map.`,
      'ERROR_LOG.md': `# Error Log\n\n`,
      'WORKLOG.md': `# Work Log\n\n`,
    };

    for (const [filename, content] of Object.entries(files)) {
      await fs.writeFile(path.join(workspacePath, filename), content);
    }
  }

  public getCurrentWorkspacePath(): string | null {
    return this.currentWorkspacePath;
  }
}

const workspacesDir = path.join(process.cwd(), '..', 'workspaces');
export const workspaceManager = new WorkspaceManager(workspacesDir);
