// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactNode } from 'react'
import { ApiProvider } from '../hooks/useApi'
import { useCommand } from '../hooks/useCommand'

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

describe('useCommand', () => {
  let originalFetch: typeof global.fetch
  beforeEach(() => {
    originalFetch = global.fetch
  })
  afterEach(() => {
    global.fetch = originalFetch
  })

  it('settles isPending to false on POST failure', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      text: async () => 'mqtt timeout',
    }) as unknown as typeof fetch
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } })

    const { result } = renderHook(() => useCommand('gw-1'), { wrapper: wrap(qc) })

    result.current.mutate({
      actuator_channel_id: 'a-1',
      action: 'ON',
      require_ack: true,
    })

    await waitFor(() => expect(result.current.isPending).toBe(false))
    expect(result.current.isError).toBe(true)
    expect(result.current.error).toBeInstanceOf(Error)
  })

  it('does not invalidate dashboard cache on failure', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      text: async () => 'fail',
    }) as unknown as typeof fetch
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
    // Pre-populate cache. If onError fires invalidation by mistake, this entry
    // would be marked stale.
    qc.setQueryData(['dashboard', 'gw-1'], { sentinel: true })

    const { result } = renderHook(() => useCommand('gw-1'), { wrapper: wrap(qc) })
    result.current.mutate({
      actuator_channel_id: 'a-1',
      action: 'OFF',
      require_ack: true,
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    const state = qc.getQueryState(['dashboard', 'gw-1'])
    // isInvalidated would be true if invalidateQueries had run.
    expect(state?.isInvalidated).not.toBe(true)
  })

  it('invalidates dashboard cache on success', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 'cmd-1' }),
    }) as unknown as typeof fetch
    const qc = new QueryClient()
    qc.setQueryData(['dashboard', 'gw-1'], { sentinel: true })

    const { result } = renderHook(() => useCommand('gw-1'), { wrapper: wrap(qc) })
    result.current.mutate({
      actuator_channel_id: 'a-1',
      action: 'ON',
      require_ack: true,
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    const state = qc.getQueryState(['dashboard', 'gw-1'])
    expect(state?.isInvalidated).toBe(true)
  })
})
