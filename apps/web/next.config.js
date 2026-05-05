const path = require('path')
const { withTamagui } = require('@tamagui/next-plugin')

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
    // @react-native/assets-registry contains Flow syntax that SWC can't strip.
    // It's only used by react-native-svg's native asset path; on web we stub it.
    config.resolve.alias['@react-native/assets-registry/registry'] = path.resolve(
      __dirname,
      'src/stubs/assets-registry.js',
    )
    return config
  },
})
