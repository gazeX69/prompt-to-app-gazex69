export type RuntimeErrorCode =
  | 'RUNTIME_PORT_CONFLICT'
  | 'RUNTIME_HEALTH_TIMEOUT'
  | 'RUNTIME_PROCESS_CRASH'
  | 'RUNTIME_BUILD_FAILURE'
  | 'RUNTIME_DEPENDENCY_MISSING'
  | 'RUNTIME_DEVSERVER_UNREACHABLE';

export type RuntimeErrorSeverity = 'info' | 'warning' | 'error' | 'fatal';

export interface RuntimeErrorDetail {
  [key: string]: unknown;
}

export interface StructuredRuntimeError {
  code: RuntimeErrorCode;
  message: string;
  detail: RuntimeErrorDetail;
  severity: RuntimeErrorSeverity;
  recoverable: boolean;
  timestamp: number;
  suggestedAction: string;
}

const ERROR_DEFAULTS: Record<RuntimeErrorCode, Pick<StructuredRuntimeError, 'severity' | 'recoverable' | 'suggestedAction'>> = {
  RUNTIME_PORT_CONFLICT: {
    severity: 'warning',
    recoverable: true,
    suggestedAction: 'Use the selected fallback port or free the configured port.',
  },
  RUNTIME_HEALTH_TIMEOUT: {
    severity: 'error',
    recoverable: true,
    suggestedAction: 'Inspect runtime logs, then retry the dev server launch.',
  },
  RUNTIME_PROCESS_CRASH: {
    severity: 'fatal',
    recoverable: true,
    suggestedAction: 'Inspect stderr for the process crash reason before retrying.',
  },
  RUNTIME_BUILD_FAILURE: {
    severity: 'error',
    recoverable: true,
    suggestedAction: 'Classify the build output and repair the targeted failure.',
  },
  RUNTIME_DEPENDENCY_MISSING: {
    severity: 'error',
    recoverable: false,
    suggestedAction: 'Declare the dependency explicitly or remove the undeclared import.',
  },
  RUNTIME_DEVSERVER_UNREACHABLE: {
    severity: 'error',
    recoverable: true,
    suggestedAction: 'Verify the dev server port and retry runtime launch.',
  },
};

export function createRuntimeError(
  code: RuntimeErrorCode,
  message: string,
  detail: RuntimeErrorDetail = {},
  overrides: Partial<Pick<StructuredRuntimeError, 'severity' | 'recoverable' | 'suggestedAction'>> = {},
): StructuredRuntimeError {
  const defaults = ERROR_DEFAULTS[code];
  return {
    code,
    message,
    detail,
    severity: overrides.severity ?? defaults.severity,
    recoverable: overrides.recoverable ?? defaults.recoverable,
    timestamp: Date.now(),
    suggestedAction: overrides.suggestedAction ?? defaults.suggestedAction,
  };
}

export function classifyProcessFailure(exitCode?: number, stderr?: string): RuntimeErrorCode {
  const text = (stderr || '').toLowerCase();
  if (text.includes('cannot find module') || text.includes('module not found') || text.includes('could not resolve')) {
    return 'RUNTIME_DEPENDENCY_MISSING';
  }
  if (text.includes('failed to resolve import')) {
    return 'RUNTIME_DEPENDENCY_MISSING';
  }
  if (text.includes('build failed') || text.includes('tsc') || text.includes('vite build')) {
    return 'RUNTIME_BUILD_FAILURE';
  }
  if (exitCode && exitCode !== 0) {
    return 'RUNTIME_PROCESS_CRASH';
  }
  return 'RUNTIME_PROCESS_CRASH';
}
