import fs from 'fs/promises';
import fsSync from 'fs';
import path from 'path';
import { eventBus } from '../events/RuntimeEventBus.js';
import { RuntimeEventType } from '../types/events.js';

export class TemplateRegistry {
  public async scaffold(templateId: string, targetDir: string): Promise<void> {
    if (templateId === 'vite-react-ts' || templateId === 'react-vite-ts') {
      await this.scaffoldViteReactTs(targetDir);
      eventBus.emitEvent(RuntimeEventType.TEMPLATE_CREATED, { templateId, targetDir });
    } else {
      throw new Error(`Template ${templateId} not found`);
    }
  }

  private async scaffoldViteReactTs(targetDir: string) {
    const candidates = [
      path.resolve(process.cwd(), '..', 'templates', 'react-vite-ts'),
      path.resolve(process.cwd(), 'templates', 'react-vite-ts'),
    ];
    const source = candidates.find(asyncCandidateExists);
    if (!source) {
      throw new Error(`Canonical react-vite-ts template not found in ${candidates.join(', ')}`);
    }

    await fs.mkdir(targetDir, { recursive: true });
    await fs.cp(source, targetDir, { recursive: true, force: true });
  }
}

function asyncCandidateExists(candidate: string): boolean {
  try {
    fsSync.accessSync(candidate);
    return true;
  } catch {
    return false;
  }
}

export const templateRegistry = new TemplateRegistry();
