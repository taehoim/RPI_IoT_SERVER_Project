// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactNode } from 'react'
import { ApiProvider } from '../hooks/useApi'
import { useDashboard } from '../hooks/useDashboard'

const wrap = (qc: QueryClient): ((p: { children: ReactNode }) => JSX.Element) => {
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>
      <ApiProvider config={{ baseUrl: 'http://test', getToken: () => 't' }}>
        {children}
      </ApiProvider>
    </QueryClientProvider>
  )
  return Wrapper
}

describe('useDashboard', () => {
  let originalFetch: typeof global.fetch
  beforeEach(() => {
    originalFetch = global.fetch
  })
  afterEach(() => {
    global.fetch = originalFetch
  })

  it('does NOT fetch when gatewayId is null (enabled guard)', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({}),
    })
    global.fetch = fetchMock as unknown as typeof fetch
    const qc = new QueryClient()

    renderHook(() => useDashboard(null), { wrapper: wrap(qc) })

    // Give react-query a chance to resolve. If the enabled guard is removed,
    // a fetch would be issued here and this test would catch it.
    await new Promise((r) => setTimeout(r, 50))
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('fetches when gatewayId is set', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        gateway: { id: 'gw-1', serial_number: 'X', name: 'X', status: 'online', site_id: '' },
        sensors: [],
        actuators: [],
        last_seen: null,
      }),
    })
    global.fetch = fetchMock as unknown as typeof fetch
    const qc = new QueryClient()

    const { result } = renderHook(() => useDashboard('gw-1'), { wrapper: wrap(qc) })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(fetchMock).toHaveBeenCalledWith(
      'http://test/api/dashboard?gateway_id=gw-1',
      expect.any(Object),
    )
  })
})
