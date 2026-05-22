import { RUNTIME_CONFIG } from './runtime';

export const ENV = {
  API_URL: import.meta.env.VITE_API_URL || RUNTIME_CONFIG.API_URL,
  WS_URL: import.meta.env.VITE_WS_URL || RUNTIME_CONFIG.WS_URL,
}
