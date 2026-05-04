import { Select, Adapt, Sheet } from 'tamagui'
import { ChevronDown } from '@tamagui/lucide-icons'

export interface GatewayOption {
  id: string
  name: string
}

export interface SiteSelectorProps {
  gateways: GatewayOption[]
  value: string
  onChange: (id: string) => void
}

export function SiteSelector({ gateways, value, onChange }: SiteSelectorProps) {
  // Tamagui's <Select.Value> only learns the active item label after the
  // dropdown has been opened at least once (it pulls from `selectedItem`
  // context, populated by <Select.Item>). For SSR + initial render to show
  // the right name we look it up ourselves and pass it as the Value child.
  const selectedName = gateways.find((g) => g.id === value)?.name

  return (
    <Select value={value} onValueChange={onChange}>
      <Select.Trigger
        // Tamagui renders the trigger as a <button>; declare combobox role
        // explicitly so accessibility tooling and tests treat it as a select.
        role="combobox"
        iconAfter={ChevronDown}
        width={240}
      >
        <Select.Value placeholder="사이트 선택">{selectedName}</Select.Value>
      </Select.Trigger>

      <Adapt when="sm" platform="touch">
        <Sheet modal dismissOnSnapToBottom>
          <Sheet.Frame>
            <Adapt.Contents />
          </Sheet.Frame>
          <Sheet.Overlay />
        </Sheet>
      </Adapt>

      <Select.Content>
        <Select.Viewport>
          {gateways.map((g, i) => (
            <Select.Item key={g.id} value={g.id} index={i}>
              <Select.ItemText>{g.name}</Select.ItemText>
            </Select.Item>
          ))}
        </Select.Viewport>
      </Select.Content>
    </Select>
  )
}
