const apiUrl =
  import.meta.env.VITE_API_URL ||
  import.meta.env.VITE_API_BASE_URL ||
  "http://127.0.0.1:8000";

const wsUrl =
  import.meta.env.VITE_WS_URL ||
  apiUrl.replace(/^http/, "ws");

export const RUNTIME_CONFIG = {
  API_URL: apiUrl.replace(/\/$/, ""),
  WS_URL: wsUrl.replace(/\/$/, ""),
};

export const ENV = RUNTIME_CONFIG;