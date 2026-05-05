'use client'

import { useEffect } from 'react'
import Link from 'next/link'
import { YStack, XStack, H1, Paragraph, Spinner } from 'tamagui'
import { SiteSelector, SensorCard, ActuatorToggle } from '@iot/ui'
import { useDashboard, useCommand, useGateways } from '@iot/api'

export function DashboardScreen() {
  const { gateways, selected, setSelected, error: loadError } = useGateways()

  useEffect(() => {
    if (selected) localStorage.setItem('selectedGateway', selected)
  }, [selected])

  const { data, isLoading } = useDashboard(selected)
  const { mutate: sendCmd, isPending } = useCommand(selected ?? '')

  if (loadError) {
    return (
      <YStack padding="$6" alignItems="center" gap="$2">
        <Paragraph color="$red10">⚠ {loadError}</Paragraph>
        <Paragraph theme="alt2" size="$2">JWT가 만료됐다면 /login에서 재발급</Paragraph>
      </YStack>
    )
  }

  if (!selected || isLoading || !data) {
    return (
      <YStack padding="$6" alignItems="center">
        <Spinner />
      </YStack>
    )
  }

  // Backend returns null for value when value_double is empty; coercing to 0
  // would silently corrupt the threshold classification, so we skip those
  // entries entirely. The status='unknown' badge in @iot/ui handles the case
  // where a future change keeps the row but renders the missing value.
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

      <XStack justifyContent="space-between" alignItems="center">
        <Paragraph theme="alt2">
          마지막 업데이트:{' '}
          {data.last_seen ? new Date(data.last_seen).toLocaleTimeString() : '없음'}
        </Paragraph>
        <Link href="/trends" style={{ color: '#007AFF', textDecoration: 'none' }}>
          → 24h 추세 보기
        </Link>
      </XStack>

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
