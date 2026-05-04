import { createTamagui } from 'tamagui'
import { config as defaultConfig } from '@tamagui/config/v3'
import { tokens } from './src/tokens'

export const config = createTamagui({
  ...defaultConfig,
  tokens,
  themes: {
    light: { background: tokens.color.cardBg, color: tokens.color.text },
    dark: { background: '#000000', color: tokens.color.textDark },
  },
})

export type AppConfig = typeof config
declare module 'tamagui' {
  interface TamaguiCustomConfig extends AppConfig {}
}
