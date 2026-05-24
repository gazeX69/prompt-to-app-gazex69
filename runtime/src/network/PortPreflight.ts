import net from 'net';
import { execFile } from 'child_process';
import { promisify } from 'util';

const execFileAsync = promisify(execFile);

export interface PortConflictInfo {
  port: number;
  occupied: boolean;
  pid?: number;
  processName?: string;
}

export interface PortAllocationResult {
  requestedPort: number;
  selectedPort: number;
  fallbackUsed: boolean;
  attempts: PortConflictInfo[];
}

async function canBind(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once('error', () => resolve(false));
    server.once('listening', () => {
      server.close(() => resolve(true));
    });
    server.listen(port, '127.0.0.1');
  });
}

async function getWindowsProcessName(pid: number): Promise<string | undefined> {
  try {
    const { stdout } = await execFileAsync('tasklist', ['/FI', `PID eq ${pid}`, '/FO', 'CSV', '/NH']);
    const line = stdout.trim().split(/\r?\n/).find((entry) => entry.includes(`"${pid}"`));
    return line?.match(/^"([^"]+)"/)?.[1];
  } catch {
    return undefined;
  }
}

async function getPortOwner(port: number): Promise<Pick<PortConflictInfo, 'pid' | 'processName'>> {
  try {
    if (process.platform === 'win32') {
      const { stdout } = await execFileAsync('netstat', ['-ano', '-p', 'tcp']);
      const escapedPort = String(port).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const pattern = new RegExp(`(?:127\\.0\\.0\\.1|0\\.0\\.0\\.0|\\[::\\]|::1):${escapedPort}\\s+.*LISTENING\\s+(\\d+)`, 'i');
      const line = stdout.split(/\r?\n/).find((entry) => pattern.test(entry));
      const pid = line ? Number(line.match(pattern)?.[1]) : undefined;
      return pid ? { pid, processName: await getWindowsProcessName(pid) } : {};
    }

    const { stdout } = await execFileAsync('lsof', ['-nP', `-iTCP:${port}`, '-sTCP:LISTEN']);
    const line = stdout.trim().split(/\r?\n/)[1];
    if (!line) return {};
    const parts = line.trim().split(/\s+/);
    const pid = Number(parts[1]);
    return Number.isFinite(pid) ? { pid, processName: parts[0] } : {};
  } catch {
    return {};
  }
}

export async function inspectPort(port: number): Promise<PortConflictInfo> {
  if (await canBind(port)) {
    return { port, occupied: false };
  }
  return { port, occupied: true, ...(await getPortOwner(port)) };
}

export async function allocatePort(
  requestedPort: number,
  autoIncrement = true,
  maxAttempts = 10,
): Promise<PortAllocationResult> {
  const attempts: PortConflictInfo[] = [];
  const boundedAttempts = Math.max(1, maxAttempts);

  for (let offset = 0; offset < boundedAttempts; offset += 1) {
    const port = requestedPort + offset;
    const result = await inspectPort(port);
    attempts.push(result);
    if (!result.occupied) {
      return {
        requestedPort,
        selectedPort: port,
        fallbackUsed: port !== requestedPort,
        attempts,
      };
    }
    if (!autoIncrement) break;
  }

  throw Object.assign(new Error(`No available runtime port from ${requestedPort} within ${boundedAttempts} attempt(s)`), {
    code: 'RUNTIME_PORT_CONFLICT',
    requestedPort,
    attempts,
  });
}
