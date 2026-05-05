import { useState, useEffect } from 'react'
import { ScrollView } from 'react-native'
import { Link } from 'expo-router'
import { YStack, XStack, H1, Paragraph, Spinner, Button } from 'tamagui'
import { SiteSelector, SensorCard, ActuatorToggle } from '@iot/ui'
import { useDashboard, useCommand, useApi, type Gateway } from '@iot/api'

export function DashboardScreen() {
  const api = useApi()
  const [gateways, setGateways] = useState<{ id: string; name: string }[]>([])
  const [selected, setSelected] = useState<string | null>(null)

  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api
      .get<Gateway[]>('/api/gateways')
      .then((list) => {
        if (cancelled) return
        setLoadError(null)
        setGateways(list.map((g) => ({ id: g.id, name: g.name || g.serial_number })))
        if (list[0]) setSelected(list[0].id)
      })
      .catch((err) => {
        if (cancelled) return
        // Without this, the spinner spins forever on a 401/network error.
        console.error('Failed to load gateways', err)
        setLoadError(err instanceof Error ? err.message : 'gateway 목록 로딩 실패')
      })
    return () => {
      cancelled = true
    }
  }, [api])

  const { data, isLoading } = useDashboard(selected)
  const { mutate: sendCmd, isPending } = useCommand(selected ?? '')

  if (loadError) {
    return (
      <YStack flex={1} alignItems="center" justifyContent="center" gap="$2" padding="$4">
        <Paragraph color="$red10">⚠ {loadError}</Paragraph>
        <Paragraph theme="alt2" size="$2">JWT가 만료됐다면 /login에서 재발급</Paragraph>
      </YStack>
    )
  }

  if (!selected || isLoading || !data) {
    return (
      <YStack flex={1} alignItems="center" justifyContent="center">
        <Spinner />
      </YStack>
    )
  }

  // Backend can return null sensor values; SensorCard expects number.
  const numericSensors = data.sensors.filter(
    (s): s is typeof s & { value: number } => typeof s.value === 'number',
  )

  return (
    <ScrollView contentContainerStyle={{ flexGrow: 1 }}>
      <YStack padding="$4" gap="$4">
        <H1 size="$7">{data.gateway.name}</H1>
        <SiteSelector gateways={gateways} value={selected} onChange={setSelected} />

        <Paragraph theme="alt2">
          마지막 업데이트:{' '}
          {data.last_seen ? new Date(data.last_seen).toLocaleTimeString() : '없음'}
        </Paragraph>

        <Link href="/trends" asChild>
          <Button>최근 측정값 보기</Button>
        </Link>

        <Paragraph fontWeight="700" size="$5">센서</Paragraph>
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

        <Paragraph fontWeight="700" size="$5">즐겨찾기</Paragraph>
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
    </ScrollView>
  )
}
