const { withTamagui } = require('@tamagui/next-plugin')

module.exports = withTamagui({
  config: '../../packages/ui/tamagui.config.ts',
  components: ['tamagui', '@iot/ui'],
  appDir: true,
  outputCSS: process.env.NODE_ENV === 'production' ? './public/tamagui.css' : null,
})({
  reactStrictMode: true,
  transpilePackages: ['@iot/ui', '@iot/api', 'tamagui'],
  output: 'standalone',
})
