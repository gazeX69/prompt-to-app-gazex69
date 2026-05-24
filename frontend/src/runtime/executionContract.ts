import contract from './execution_contract.json'

export const EXECUTION_CONTRACT = contract

export type ExecutionState = (typeof contract.states)[number]
export type RuntimeErrorCode = keyof typeof contract.errorCodes

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
