import { createTamagui } from 'tamagui'
import { config as defaultConfig } from '@tamagui/config/v3'
import { tokens } from './src/tokens'

// Use v3 default themes verbatim. We previously overrode `themes.light` /
// `themes.dark` with plain hex strings (`tokens.color.cardBg = '#FFFFFF'`),
// but v3 themes expect Variable objects produced by createToken — mixing
// raw strings broke createCSSVariable at build time.
//
// Apple Home palette lives in `tokens.color.*` (statusOk/Warn/Danger/cardBg
// etc) and components reference them by name (e.g., `backgroundColor="$cardBg"`).
// To customize the global background/foreground later, use createToken-based
// variables and assign them to the theme.
export const config = createTamagui({
  ...defaultConfig,
  tokens,
})

export type AppConfig = typeof config
declare module 'tamagui' {
  interface TamaguiCustomConfig extends AppConfig {}
}
