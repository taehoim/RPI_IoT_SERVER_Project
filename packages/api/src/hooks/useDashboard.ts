import { useQuery } from '@tanstack/react-query'
import type { DashboardData } from '../types'
import { useApi } from './useApi'

export function useDashboard(gatewayId: string | null) {
  const api = useApi()
  return useQuery<DashboardData>({
    queryKey: ['dashboard', gatewayId],
    queryFn: () => api.get<DashboardData>(`/api/dashboard?gateway_id=${gatewayId}`),
    enabled: !!gatewayId,
    staleTime: 5_000,
  })
}
