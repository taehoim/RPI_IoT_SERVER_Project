// Tamagui v3 token additions must be wrapped in createTokens / createToken
// (Variable instances), not raw strings. Spreading raw hex strings into
// `tokens.color` makes createCSSVariable crash on undefined.length at build
// time.
//
// For now we re-export the v3 base tokens unchanged and keep Apple Home
// constants as plain JS exports — components import them directly via
// inline style or the STATUS_COLOR map.
//
// To re-introduce these as Tamagui tokens, use createToken:
//   const cardBg = createToken('#FFFFFF', { name: 'cardBg' })
//   export const tokens = createTokens({ ...base, color: { ...base.color, cardBg } })
export { tokens } from '@tamagui/config/v3'

export const APPLE_HOME = {
  statusOk: '#34C759',
  statusWarn: '#FF9500',
  statusDanger: '#FF3B30',
  statusActive: '#007AFF',
  statusUnknown: '#8E8E93',
  cardBg: '#FFFFFF',
  cardBgDark: '#1C1C1E',
  text: '#000000',
  textDark: '#FFFFFF',
  textMuted: '#8E8E93',
} as const
