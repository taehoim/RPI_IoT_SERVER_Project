import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'

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
