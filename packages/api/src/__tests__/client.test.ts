import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createApiClient, ApiError } from '../client'

describe('createApiClient', () => {
  let originalFetch: typeof global.fetch

  beforeEach(() => {
    originalFetch = global.fetch
  })

  afterEach(() => {
    global.fetch = originalFetch
  })

  it('attaches Authorization header when token is provided', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: [] }),
    })
    global.fetch = fetchMock as unknown as typeof fetch

    const api = createApiClient({ baseUrl: 'http://x', getToken: () => 'tok123' })
    await api.get('/api/gateways')

    expect(fetchMock).toHaveBeenCalledWith(
      'http://x/api/gateways',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer tok123' }),
      })
    )
  })

  it('omits Authorization header when token is null', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({}),
    })
    global.fetch = fetchMock as unknown as typeof fetch

    const api = createApiClient({ baseUrl: 'http://x', getToken: () => null })
    await api.get('/api/x')

    const callArgs = fetchMock.mock.calls[0][1]
    expect(callArgs.headers).not.toHaveProperty('Authorization')
  })

  it('throws ApiError with status when response not ok', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
      json: async () => ({ detail: 'token expired' }),
    }) as unknown as typeof fetch

    const api = createApiClient({ baseUrl: 'http://x', getToken: () => 't' })
    await expect(api.get('/api/x')).rejects.toThrow(ApiError)
    await expect(api.get('/api/x')).rejects.toThrow(/401/)
  })

  it('post method serializes body as JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({}),
    })
    global.fetch = fetchMock as unknown as typeof fetch

    const api = createApiClient({ baseUrl: 'http://x', getToken: () => null })
    await api.post('/api/cmd', { action: 'ON' })

    const callArgs = fetchMock.mock.calls[0][1]
    expect(callArgs.method).toBe('POST')
    expect(callArgs.body).toBe('{"action":"ON"}')
  })
})
