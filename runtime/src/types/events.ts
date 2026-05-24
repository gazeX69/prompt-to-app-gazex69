export enum RuntimeEventType {
  SESSION_STARTED = 'SESSION_STARTED',
  TEMPLATE_CREATED = 'TEMPLATE_CREATED',
  COMMAND_STARTED = 'COMMAND_STARTED',
  COMMAND_STDOUT = 'COMMAND_STDOUT',
  COMMAND_STDERR = 'COMMAND_STDERR',
  COMMAND_COMPLETED = 'COMMAND_COMPLETED',
  DEVSERVER_STARTED = 'DEVSERVER_STARTED',
  PREVIEW_READY = 'PREVIEW_READY',
  RUNTIME_PORT_CONFLICT = 'RUNTIME_PORT_CONFLICT',
  RUNTIME_HEALTHCHECK_STARTED = 'RUNTIME_HEALTHCHECK_STARTED',
  RUNTIME_HEALTHCHECK_FAILED = 'RUNTIME_HEALTHCHECK_FAILED',
  RUNTIME_READY = 'RUNTIME_READY',
  RUNTIME_SPAWN_FAILED = 'RUNTIME_SPAWN_FAILED',
  RUNTIME_LIFECYCLE = 'RUNTIME_LIFECYCLE',
  SESSION_FAILED = 'SESSION_FAILED',
  SESSION_COMPLETED = 'SESSION_COMPLETED',
}

export interface RuntimeEvent {
  type: RuntimeEventType;
  payload: any;
  timestamp: number;
}

export type RuntimeLifecycleEventType =
  | 'runtime.spawn.started'
  | 'runtime.spawn.failed'
  | 'runtime.port.conflict'
  | 'runtime.healthcheck.started'
  | 'runtime.healthcheck.failed'
  | 'runtime.ready'
  | 'runtime.crashed';

export interface RuntimeLifecycleEvent {
  type: RuntimeLifecycleEventType;
  timestamp: number;
  workspaceId?: string;
  sessionId?: string;
  requestedPort?: number;
  selectedPort?: number;
  fallbackUsed?: boolean;
  processPid?: number;
  error?: unknown;
  message: string;
}
