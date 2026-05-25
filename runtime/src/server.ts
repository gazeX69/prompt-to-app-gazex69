import express from 'express';
import cors from 'cors';
import { workspaceManager } from './workspace/WorkspaceManager.js';
import { templateRegistry } from './templates/TemplateRegistry.js';
import { processManager } from './processes/RuntimeProcessManager.js';
import { previewDetector } from './preview/PreviewDetector.js';
import { eventBus } from './events/RuntimeEventBus.js';
import { RuntimeEventType, RuntimeEvent } from './types/events.js';
import { createRuntimeError } from './errors/RuntimeErrors.js';

const app = express();
app.use(cors());
app.use(express.json());

// Server-Sent Events for Python Backend to consume raw execution logs
app.get('/runtime/events', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();

  const listener = (event: RuntimeEvent) => {
    res.write(`data: ${JSON.stringify(event)}\n\n`);
  };

  eventBus.onEvent('*', listener);

  req.on('close', () => {
    eventBus.offEvent('*', listener);
  });
});

app.post('/runtime/workspace/create', async (req, res) => {
  try {
    const workspace = await workspaceManager.createWorkspace();
    // Scaffold template implicitly for now, or we can make it a parameter
    await templateRegistry.scaffold('vite-react-ts', workspace.path);
    res.json(workspace);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/runtime/command/run', async (req, res) => {
  const { id, command, args, cwd } = req.body;
  if (!id || !command || !args) {
    return res.status(400).json({ error: 'Missing id, command, or args' });
  }
  
  // Don't await here; let it run and emit events
  processManager.spawnCommand(id, { command, args, cwd }).catch(console.error);
  res.json({ status: 'started', id });
});

app.post('/runtime/dev/start', async (req, res) => {
  const { id, cwd, port, autoIncrementPorts, maxPortAttempts, healthTimeoutMs } = req.body;
  if (!id || !cwd) {
    return res.status(400).json({ error: 'Missing id or cwd' });
  }

  try {
    const session = await processManager.startDevServer(id, {
      cwd,
      requestedPort: Number.isFinite(Number(port)) ? Number(port) : undefined,
      autoIncrementPorts: autoIncrementPorts !== false,
      maxPortAttempts: Number.isFinite(Number(maxPortAttempts)) ? Number(maxPortAttempts) : undefined,
      healthTimeoutMs: Number.isFinite(Number(healthTimeoutMs)) ? Number(healthTimeoutMs) : undefined,
    });
    res.json({ status: 'dev_server_starting', id, session });
  } catch (err: any) {
    const code = err.code === 'RUNTIME_PORT_CONFLICT' ? 'RUNTIME_PORT_CONFLICT' : 'RUNTIME_PROCESS_CRASH';
    res.status(409).json({
      error: createRuntimeError(code, err.message || 'Runtime launch failed', {
        attempts: err.attempts || [],
      }),
    });
  }
});

app.post('/runtime/dev/stop', async (req, res) => {
  const { id } = req.body;
  const success = await processManager.killCommand(id);
  res.json({ status: 'stopped', success });
});

app.get('/runtime/processes', (req, res) => {
  const activeIds = processManager.getActiveProcessIds();
  res.json({ activeIds, sessions: processManager.getRuntimeSessions() });
});

app.get('/runtime/preview/:sessionId', (req, res) => {
  // Dummy endpoint for now since preview logic will just emit PREVIEW_READY
  res.json({ status: 'unsupported_in_phase1' });
});

app.get('/runtime/health', (req, res) => {
  res.json({ status: 'ok', service: 'runtime', npm: 'available', node: 'available' });
});

const PORT = Number(process.env.PORT || process.env.RUNTIME_PORT || 3001);
app.listen(PORT, () => {
  console.log(`Node Runtime Sandbox listening on port ${PORT}`);
});
