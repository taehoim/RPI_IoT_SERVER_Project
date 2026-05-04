// Stub for @tamagui/lucide-icons in jsdom tests.
// The real icon set transitively requires react-native-svg, which pulls in
// untransformed React Native sources that Vite/Node ESM cannot parse. Icons
// are visual-only and don't affect the rendering contract we test, so we
// replace every export with a no-op component.
import { createElement } from 'react'

const Stub = (props: Record<string, unknown>) =>
  createElement('span', { 'data-icon-stub': true, ...props })

export const ChevronDown = Stub
export const Check = Stub
export const Power = Stub

// Catch-all proxy so any other icon name resolves to the stub component.
export default new Proxy(
  {},
  {
    get: () => Stub,
  },
)
