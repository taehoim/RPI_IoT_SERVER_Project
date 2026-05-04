// Curated re-exports of Tamagui surface used by @iot/ui consumers.
// Do NOT use `export *` — it defeats tree-shaking on Webpack/Metro.
// Add new symbols here as components require them (Tasks 6-8).
export {
  TamaguiProvider,
  Theme,
  Stack,
  XStack,
  YStack,
  Text,
  Paragraph,
  H1,
  H2,
  Button,
  Card,
  Input,
  Spinner,
  Adapt,
  Sheet,
  Select,
} from 'tamagui'

// Components
export { SiteSelector, type SiteSelectorProps, type GatewayOption } from './components/SiteSelector'
export { SensorCard, type SensorCardProps, type SensorStatus } from './components/SensorCard'
export { ActuatorToggle, type ActuatorToggleProps, type ActuatorState } from './components/ActuatorToggle'

// Project config + tokens
export { config } from '../tamagui.config'
export { tokens } from './tokens'
