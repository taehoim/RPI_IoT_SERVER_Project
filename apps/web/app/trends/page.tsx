'use client'

import { useEffect, useState } from 'react'
import { YStack, H1, Paragraph, Spinner } from 'tamagui'
import { useApi } from '@iot/api'
import { TrendChart, type TrendPoint } from './components/TrendChart'

interface TelemetryRow {
  ts: string
  measurement_key: string
  value_double: number | null
  unit: string | null
  quality: number | null
}

const SERIES = [
  { key: 'temperature_c', label: '온도 (°C)' },
  { key: 'humidity_pct', label: '습도 (%)' },
  { key: 'co2_ppm', label: 'CO₂ (ppm)' },
] as const

export default function TrendsPage() {
  const api = useApi()
  const [series, setSeries] = useState<Record<string, TrendPoint[]>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const gatewayId = localStorage.getItem('selectedGateway')
    if (!gatewayId) {
      setLoading(false)
      return
    }
    Promise.all(
      SERIES.map(({ key }) =>
        api
          .get<TelemetryRow[]>(
            `/api/gateways/${gatewayId}/telemetry?measurement_key=${key}&hours=24&limit=2000`,
          )
          // Backend returns desc; chart expects ascending by ts.
          .then((rows) => {
            const points: TrendPoint[] = rows
              .filter((r): r is TelemetryRow & { value_double: number } => typeof r.value_double === 'number')
              .map((r) => ({ ts: r.ts, value: r.value_double }))
              .reverse()
            return [key, points] as const
          }),
      ),
    )
      .then((pairs) => {
        setError(null)
        setSeries(Object.fromEntries(pairs))
      })
      .catch((err) => {
        // Without this, a 401/network error would render every series as
        // "데이터 없음", indistinguishable from a gateway with no readings.
        console.error('Telemetry range fetch failed', err)
        setError(err instanceof Error ? err.message : '추세 데이터 로딩 실패')
      })
      .finally(() => setLoading(false))
  }, [api])

  if (loading) {
    return (
      <YStack padding="$6" alignItems="center">
        <Spinner />
      </YStack>
    )
  }

  if (error) {
    return (
      <YStack padding="$6" alignItems="center" gap="$2">
        <Paragraph color="$red10">⚠ {error}</Paragraph>
        <Paragraph theme="alt2" size="$2">JWT가 만료됐다면 /login에서 재발급</Paragraph>
      </YStack>
    )
  }

  return (
    <YStack padding="$4" gap="$5" maxWidth={900} margin="auto">
      <H1>24시간 추세</H1>
      {SERIES.map(({ key, label }) => {
        const data = series[key] ?? []
        return (
          <YStack key={key} gap="$2">
            <Paragraph fontWeight="600" size="$4">{label}</Paragraph>
            {data.length > 0 ? (
              <TrendChart data={data} />
            ) : (
              <Paragraph theme="alt2">데이터 없음</Paragraph>
            )}
          </YStack>
        )
      })}
    </YStack>
  )
}
