import { tokens as base } from '@tamagui/config/v3'

export const tokens = {
  ...base,
  color: {
    ...base.color,
    statusOk: '#34C759',       // green — 정상
    statusWarn: '#FF9500',     // orange — 주의
    statusDanger: '#FF3B30',   // red — 위험
    statusActive: '#007AFF',   // blue — 액티브
    cardBg: '#FFFFFF',
    cardBgDark: '#1C1C1E',
    text: '#000000',
    textDark: '#FFFFFF',
    textMuted: '#8E8E93',
  },
  size: {
    ...base.size,
    cardRadius: 16,
    cardPad: 20,
    iconLarge: 48,
  },
}
