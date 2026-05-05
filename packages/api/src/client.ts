export interface ApiClientConfig {
  baseUrl: string
  getToken: () => string | null
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(`${status}: ${message}`)
  }
}

export function createApiClient(cfg: ApiClientConfig) {
  const headers = () => {
    const token = cfg.getToken()
    return {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    }
  }

  async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const res = await fetch(`${cfg.baseUrl}${path}`, {
      method,
      headers: headers(),
      ...(body ? { body: JSON.stringify(body) } : {}),
    })
    if (!res.ok) {
      let detail = res.statusText
      try {
        const j = await res.json()
        detail = j.detail ?? detail
      } catch {}
      throw new ApiError(res.status, detail)
    }
    return res.json() as Promise<T>
  }

  return {
    get: <T>(p: string) => request<T>('GET', p),
    post: <T>(p: string, b: unknown) => request<T>('POST', p, b),
    patch: <T>(p: string, b: unknown) => request<T>('PATCH', p, b),
  }
}
