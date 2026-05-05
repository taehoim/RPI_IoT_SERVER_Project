const path = require('path')
const fs = require('fs')
const { withTamagui } = require('@tamagui/next-plugin')

// Force every @tamagui/* import (and tamagui itself) to resolve from the
// workspace root node_modules, eliminating duplicate instances pulled in
// by packages/ui's own dependency tree. Without this, createTamagui
// registers config on one instance while the consuming hook reads from
// another — symptom: `Cannot read properties of undefined (reading 'settings')`
// at SSR or `simpleHash undefined.length` at build.
const ROOT_NM = path.resolve(__dirname, '../../node_modules')
const tamaguiAliases = {}
for (const dir of fs.readdirSync(path.join(ROOT_NM, '@tamagui'))) {
  tamaguiAliases[`@tamagui/${dir}$`] = path.join(ROOT_NM, '@tamagui', dir)
}
tamaguiAliases['tamagui$'] = path.join(ROOT_NM, 'tamagui')

module.exports = withTamagui({
  config: '../../packages/ui/tamagui.config.ts',
  components: ['tamagui', '@iot/ui'],
  appDir: true,
  outputCSS: process.env.NODE_ENV === 'production' ? './public/tamagui.css' : null,
})({
  reactStrictMode: true,
  transpilePackages: ['@iot/ui', '@iot/api', 'tamagui', '@tamagui/lucide-icons', 'react-native-svg'],
  output: 'standalone',
  webpack: (config) => {
    config.resolve.alias = {
      ...config.resolve.alias,
      ...tamaguiAliases,
      // @react-native/assets-registry contains Flow syntax that SWC can't strip.
      '@react-native/assets-registry/registry': path.resolve(
        __dirname,
        'src/stubs/assets-registry.js',
      ),
    }
    return config
  },
})
