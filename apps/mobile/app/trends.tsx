import { useEffect, useState } from 'react'
import { ScrollView } from 'react-native'
import { YStack, H1, Paragraph, Card, Spinner } from 'tamagui'
import { useApi, type Gateway, type DashboardData } from '@iot/api'

export default function Trends() {
  const api = useApi()
  const [latest, setLatest] = useState<DashboardData['sensors']>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const gateways = await api.get<Gateway[]>('/api/gateways')
      if (cancelled || !gateways[0]) return
      const data = await api.get<DashboardData>(
        `/api/dashboard?gateway_id=${gateways[0].id}`,
      )
      if (cancelled) return
      setLatest(data.sensors)
      setLoading(false)
    })().catch(() => setLoading(false))
    return () => {
      cancelled = true
    }
  }, [api])

  if (loading) {
    return (
      <YStack flex={1} alignItems="center" justifyContent="center">
        <Spinner />
      </YStack>
    )
  }

  return (
    <ScrollView contentContainerStyle={{ flexGrow: 1 }}>
      <YStack padding="$4" gap="$3">
        <H1 size="$7">최근 측정값</H1>
        {latest.map((s) => (
          <Card key={`${s.channel_id}-${s.measurement_key}`} bordered padding="$3">
            <Paragraph fontWeight="600">{s.channel_name}</Paragraph>
            <Paragraph size="$5">
              {typeof s.value === 'number' ? s.value.toFixed(1) : '—'} {s.unit}
            </Paragraph>
            <Paragraph theme="alt2" size="$2">
              {new Date(s.ts).toLocaleString()}
            </Paragraph>
          </Card>
        ))}
      </YStack>
    </ScrollView>
  )
}
