import { Card, H2, Paragraph, YStack, XStack } from 'tamagui'

const STATUS_COLOR = {
  ok: '#34C759',
  warn: '#FF9500',
  danger: '#FF3B30',
} as const

export type SensorStatus = keyof typeof STATUS_COLOR

export interface SensorCardProps {
  label: string
  value: number
  unit: string
  status: SensorStatus
}

export function SensorCard({ label, value, unit, status }: SensorCardProps) {
  const color = STATUS_COLOR[status]
  return (
    <Card elevate size="$4" bordered padding="$4" minWidth={120} minHeight={120}>
      <YStack gap="$2" alignItems="flex-start">
        <Paragraph theme="alt2" size="$2">{label}</Paragraph>
        <XStack alignItems="baseline" gap="$1">
          <H2 style={{ color }}>{value.toFixed(1)}</H2>
          <Paragraph theme="alt2" size="$3">{unit}</Paragraph>
        </XStack>
      </YStack>
    </Card>
  )
}
