import { useQuery } from '@tanstack/react-query'
import type { DashboardData } from '../types'
import { useApi } from './useApi'

/**
 * Polls /api/dashboard every 5s when the page is visible.
 * SSE/MQTT push is a Phase 2 optimization; for sim mode and a single tenant
 * the polling overhead is trivial (one request per gateway per 5s).
 */
export function useDashboard(gatewayId: string | null) {
  const api = useApi()
  return useQuery<DashboardData>({
    queryKey: ['dashboard', gatewayId],
    queryFn: () => api.get<DashboardData>(`/api/dashboard?gateway_id=${gatewayId}`),
    enabled: !!gatewayId,
    staleTime: 5_000,
    refetchInterval: 5_000,
    refetchIntervalInBackground: false,  // pause polling when tab hidden
  })
}
