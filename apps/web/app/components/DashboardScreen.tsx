'use client'

import { useState, useEffect } from 'react'
import { YStack, XStack, H1, Paragraph, Spinner } from 'tamagui'
import { SiteSelector, SensorCard, ActuatorToggle } from '@iot/ui'
import { useDashboard, useCommand, useApi, type Gateway } from '@iot/api'

export function DashboardScreen() {
  const api = useApi()
  const [gateways, setGateways] = useState<{ id: string; name: string }[]>([])
  const [selected, setSelected] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api.get<Gateway[]>('/api/gateways').then((list) => {
      if (cancelled) return
      setGateways(list.map((g) => ({ id: g.id, name: g.name || g.serial_number })))
      if (list[0]) setSelected(list[0].id)
    })
    return () => {
      cancelled = true
    }
  }, [api])

  const { data, isLoading } = useDashboard(selected)
  const { mutate: sendCmd, isPending } = useCommand(selected ?? '')

  if (!selected || isLoading || !data) {
    return (
      <YStack padding="$6" alignItems="center">
        <Spinner />
      </YStack>
    )
  }

  // Backend can return null for value when value_double is empty; only render
  // numeric readings. Skipping null is safer than coercing to 0 for thresholds.
  const numericSensors = data.sensors.filter(
    (s): s is typeof s & { value: number } => typeof s.value === 'number',
  )

  return (
    <YStack padding="$4" gap="$4" maxWidth={900} margin="auto">
      <XStack justifyContent="space-between" alignItems="center" flexWrap="wrap" gap="$3">
        <H1 size="$8">{data.gateway.name}</H1>
        <SiteSelector
          gateways={gateways}
          value={selected}
          onChange={setSelected}
        />
      </XStack>

      <Paragraph theme="alt2">
        마지막 업데이트:{' '}
        {data.last_seen ? new Date(data.last_seen).toLocaleTimeString() : '없음'}
      </Paragraph>

      <YStack gap="$3">
        <Paragraph fontWeight="700" size="$5">
          센서
        </Paragraph>
        <XStack flexWrap="wrap" gap="$3">
          {numericSensors.map((s) => (
            <SensorCard
              key={`${s.channel_id}-${s.measurement_key}`}
              label={s.channel_name}
              value={s.value}
              unit={s.unit}
              status={s.status}
            />
          ))}
        </XStack>
      </YStack>

      <YStack gap="$3">
        <Paragraph fontWeight="700" size="$5">
          즐겨찾기
        </Paragraph>
        <XStack flexWrap="wrap" gap="$3">
          {data.actuators.map((a) => (
            <ActuatorToggle
              key={a.id}
              label={a.display_name}
              state={a.state}
              loading={isPending}
              onToggle={(next) =>
                sendCmd({
                  actuator_channel_id: a.id,
                  action: next === 'on' ? 'ON' : 'OFF',
                  require_ack: true,
                })
              }
            />
          ))}
        </XStack>
      </YStack>
    </YStack>
  )
}
