import type { ReactNode } from 'react'
import { TamaguiProvider } from 'tamagui'
import { config } from '../../tamagui.config'

export function wrap(ui: ReactNode) {
  return <TamaguiProvider config={config} defaultTheme="light">{ui}</TamaguiProvider>
}
