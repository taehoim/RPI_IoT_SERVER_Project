import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { CommandPayload } from '../types'
import { useApi } from './useApi'

export function useCommand(gatewayId: string) {
  const api = useApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: CommandPayload) =>
      api.post(`/api/gateways/${gatewayId}/commands`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dashboard', gatewayId] }),
    // IoT command failures (relay stuck, MQTT timeout) must not be silent.
    // Surface to console at minimum; UI surfaces should consume `mutation.error`.
    onError: (err) => {
      console.error('Command failed', err)
    },
  })
}
