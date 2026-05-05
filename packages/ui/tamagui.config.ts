import { createTamagui } from 'tamagui'
import { config as defaultConfig } from '@tamagui/config/v3'
import { tokens } from './src/tokens'

// Spread defaultConfig fully, then override only what we need.
// Without this, `themes: { light, dark }` would wipe v3's default light_alt1, dark_accent, etc.
export const config = createTamagui({
  ...defaultConfig,
  tokens,
  themes: {
    ...defaultConfig.themes,
    light: {
      ...defaultConfig.themes.light,
      background: tokens.color.cardBg,
      color: tokens.color.text,
    },
    dark: {
      ...defaultConfig.themes.dark,
      background: '#000000',
      color: tokens.color.textDark,
    },
  },
})

export type AppConfig = typeof config
declare module 'tamagui' {
  interface TamaguiCustomConfig extends AppConfig {}
}
