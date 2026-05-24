import { ENV } from '../config/env'

interface RequestOptions extends RequestInit {
  timeout?: number
}

class ApiService {
  async fetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const { timeout = 30000, ...fetchOptions } = options
    
    const controller = new AbortController()
    const id = setTimeout(() => controller.abort(), timeout)
    
    try {
      const response = await fetch(`${ENV.API_URL}${path}`, {
        ...fetchOptions,
        headers: {
          'Content-Type': 'application/json',
          ...fetchOptions.headers,
        },
        signal: controller.signal,
      })
      
      if (!response.ok) {
        const err = await response.text()
        throw new Error(`API Error ${response.status}: ${err}`)
      }
      
      return await response.json()
    } finally {
      clearTimeout(id)
    }
  }

  async get<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.fetch<T>(path, { ...options, method: 'GET' })
  }

  async post<T>(path: string, data: any, options?: RequestOptions): Promise<T> {
    return this.fetch<T>(path, {
      ...options,
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async scan(projectPath: string): Promise<any> {
    return this.fetch<any>(`/scan?project_path=${encodeURIComponent(projectPath)}`)
  }

  async routeFromScan(projectPath: string): Promise<any> {
    return this.fetch<any>(`/route-from-scan?project_path=${encodeURIComponent(projectPath)}`)
  }

  async fetchSkills(): Promise<any[]> {
    return this.fetch<any[]>('/skills')
  }
}

export const api = new ApiService()
