import { Button, Card, Paragraph, YStack, Spinner } from 'tamagui'
import { Power } from '@tamagui/lucide-icons'

export type ActuatorState = 'on' | 'off' | 'unknown'

export interface ActuatorToggleProps {
  label: string
  state: ActuatorState
  loading?: boolean
  onToggle: (next: 'on' | 'off') => void
}

const STATE_LABEL: Record<ActuatorState, string> = {
  on: '켜짐',
  off: '꺼짐',
  unknown: '알 수 없음',
}

export function ActuatorToggle({ label, state, loading, onToggle }: ActuatorToggleProps) {
  const isOn = state === 'on'
  return (
    <Card bordered padding="$4" minWidth={140} minHeight={140}>
      <YStack gap="$2" alignItems="center" justifyContent="center">
        <Button
          size="$6"
          circular
          aria-label={`toggle-${label}`}
          onPress={() => onToggle(isOn ? 'off' : 'on')}
          backgroundColor={isOn ? '#007AFF' : '$gray5'}
          icon={loading ? <Spinner /> : <Power color={isOn ? 'white' : '$gray11'} />}
          disabled={loading}
        />
        <Paragraph fontWeight="600">{label}</Paragraph>
        <Paragraph theme="alt2" size="$2">{STATE_LABEL[state]}</Paragraph>
      </YStack>
    </Card>
  )
}
