import { useEffect, useState } from 'react'
import { useApi } from './useApi'
import type { Gateway } from '../types'

export interface GatewayOption {
  id: string
  name: string
}

export interface UseGatewaysResult {
  gateways: GatewayOption[]
  selected: string | null
  setSelected: (id: string) => void
  error: string | null
}

/**
 * Fetches /api/gateways once on mount, exposes the list as { id, name }
 * pairs (falling back to serial_number when name is empty), and tracks
 * the currently selected gateway. The first gateway is auto-selected.
 *
 * Both web DashboardScreen and mobile DashboardScreen.native consumed the
 * exact same effect — extracting it here removes ~15 LOC per consumer
 * and centralizes the error path.
 */
export function useGateways(): UseGatewaysResult {
  const api = useApi()
  const [gateways, setGateways] = useState<GatewayOption[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api
      .get<Gateway[]>('/api/gateways')
      .then((list) => {
        if (cancelled) return
        setError(null)
        setGateways(list.map((g) => ({ id: g.id, name: g.name || g.serial_number })))
        if (list[0]) setSelected(list[0].id)
      })
      .catch((err) => {
        if (cancelled) return
        // Without this, consumers' spinner spins forever on a 401/network error.
        console.error('Failed to load gateways', err)
        setError(err instanceof Error ? err.message : 'gateway 목록 로딩 실패')
      })
    return () => {
      cancelled = true
    }
  }, [api])

  return { gateways, selected, setSelected, error }
}
