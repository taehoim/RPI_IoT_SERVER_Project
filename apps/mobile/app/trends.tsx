import { useEffect, useState } from 'react'
import { ScrollView } from 'react-native'
import { YStack, H1, Paragraph, Card, Spinner } from 'tamagui'
import { useApi, type Gateway, type DashboardData } from '@iot/api'

export default function Trends() {
  const api = useApi()
  const [latest, setLatest] = useState<DashboardData['sensors']>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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
    })().catch((err) => {
      if (cancelled) return
      // Without preserving the error, the screen would render an empty
      // list with no signal to the operator that the fetch failed.
      console.error('Trends fetch failed', err)
      setError(err instanceof Error ? err.message : '추세 데이터 로딩 실패')
      setLoading(false)
    })
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

  if (error) {
    return (
      <YStack flex={1} alignItems="center" justifyContent="center" gap="$2" padding="$4">
        <Paragraph color="$red10">⚠ {error}</Paragraph>
        <Paragraph theme="alt2" size="$2">JWT가 만료됐다면 /login에서 재발급</Paragraph>
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
