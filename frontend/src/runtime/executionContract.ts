import contract from './execution_contract.json'

export const EXECUTION_CONTRACT = contract

export type ExecutionState = (typeof contract.states)[number]
export type RuntimeExecutionState = (typeof contract.runtimeStates)[number]
export type RuntimeErrorCode = keyof typeof contract.errorCodes

export interface StructuredRuntimeError {
  code: RuntimeErrorCode
  category?: string
  message: string
  detail: Record<string, unknown>
  severity: 'info' | 'warning' | 'error' | 'fatal'
  recoverable: boolean
  timestamp: number
  suggestedAction: string
  source?: string
  project_id?: string | null
  run_id?: string | null
}

export type RuntimeLifecycleEventType =
  | 'runtime.spawn.started'
  | 'runtime.spawn.failed'
  | 'runtime.port.conflict'
  | 'runtime.healthcheck.started'
  | 'runtime.healthcheck.failed'
  | 'runtime.ready'
  | 'runtime.crashed'

export interface RuntimeLifecycleEvent {
  type: RuntimeLifecycleEventType
  timestamp: number
  workspaceId?: string
  sessionId?: string
  requestedPort?: number
  selectedPort?: number
  fallbackUsed?: boolean
  processPid?: number
  error?: StructuredRuntimeError
  message: string
}

export function mapRuntimeLifecycleToState(event: RuntimeLifecycleEvent): RuntimeExecutionState {
  switch (event.type) {
    case 'runtime.spawn.started':
      return 'STARTING'
    case 'runtime.port.conflict':
      return event.fallbackUsed ? 'CHECKING_PORTS' : 'FAILED'
    case 'runtime.spawn.failed':
    case 'runtime.healthcheck.failed':
    case 'runtime.crashed':
      return 'FAILED'
    case 'runtime.healthcheck.started':
      return 'HEALTHCHECK'
    case 'runtime.ready':
      return 'READY'
    default:
      return 'FAILED'
  }
}

export function mapExecutionToRuntimeState(state: ExecutionState): RuntimeExecutionState | null {
  switch (state) {
    case 'IDLE':
      return 'IDLE'
    case 'INSTALLING':
      return 'INSTALLING'
    case 'BUILDING':
      return 'BUILDING'
    case 'STARTING_PREVIEW':
      return 'STARTING'
    case 'FAILED':
      return 'FAILED'
    case 'SCANNING':
    case 'PLANNING':
    case 'SCAFFOLDING':
    case 'GENERATING':
    case 'WRITING':
    case 'VALIDATING':
    case 'VERIFYING':
      return 'PREPARING'
    default:
      return null
  }
}

export function normalizeExecutionState(state: string): ExecutionState {
  const aliases = contract.legacyStateAliases as Record<string, ExecutionState>
  return aliases[state] ?? (contract.states.includes(state) ? state : 'FAILED')
}

export function isTerminalExecutionState(state: ExecutionState): boolean {
  return contract.terminalStates.includes(state)
}

export function canTransition(from: ExecutionState, to: ExecutionState): boolean {
  const transitions = contract.transitions as Record<string, ExecutionState[]>
  return transitions[from]?.includes(to) ?? false
}
