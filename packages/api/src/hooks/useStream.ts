import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'

/**
 * Subscribe to telemetry SSE stream for a gateway and invalidate dashboard cache on every push.
 *
 * IMPORTANT — `getToken` MUST be a stable reference (define with `useCallback` or pull from
 * a ref/context). Every new function reference will tear down and re-create the EventSource,
 * defeating the purpose of SSE.
 *
 * Token security note: JWT is passed as URL query (?token=) because EventSource cannot set
 * custom headers. URL ends up in nginx access logs and proxies. Task 4 should issue a
 * short-lived stream-only ticket to mitigate (TODO).
 */
export function useStream(gatewayId: string | null, getToken: () => string | null) {
  const qc = useQueryClient()
  useEffect(() => {
    if (!gatewayId) return
    if (typeof EventSource === 'undefined') return  // SSR / native
    const token = getToken()
    const url = `/api/stream?gateway_id=${gatewayId}&token=${token ?? ''}`
    const es = new EventSource(url)
    es.onmessage = () => {
      qc.invalidateQueries({ queryKey: ['dashboard', gatewayId] })
    }
    es.onerror = () => es.close()
    return () => es.close()
  }, [gatewayId, qc, getToken])
}
