import { defineConfig } from 'vitest/config'
import { resolve } from 'node:path'

// Tamagui imports `react-native` at the top of Popover/Sheet/Select; in a
// jsdom environment we must redirect that to `react-native-web` (the same trick
// Next.js / Metro / Webpack apply via aliases). Without this, Node ESM tries
// to parse the actual react-native source which contains Flow syntax and
// blows up with `Unexpected token 'typeof'`.
//
// `@tamagui/lucide-icons` transitively requires `react-native-svg`, whose
// module entry imports from `react-native` and uses Metro `.web.js` resolution
// that Vite/Node cannot replicate. Icons are visual-only and irrelevant to our
// rendering-contract tests, so we stub the whole package with a no-op.
//
// We inline tamagui's pre-bundled .mjs files so Vite's resolver actually runs
// over them — externals load via Node's ESM loader and bypass Vite entirely.
export default defineConfig({
  resolve: {
    alias: {
      'react-native': 'react-native-web',
      '@tamagui/lucide-icons': resolve(__dirname, 'src/test-stubs/lucide-icons.ts'),
    },
  },
  test: {
    globals: false,
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    server: {
      deps: {
        inline: [/tamagui/, /@tamagui\//, /react-native-web/],
      },
    },
  },
})
