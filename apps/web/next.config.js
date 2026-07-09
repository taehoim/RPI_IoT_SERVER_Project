const path = require('path')

// Tamagui Next plugin (withTamagui) is intentionally NOT used here.
// Static extraction triggers Tamagui's createTamagui at build time, which
// requires single-instance @tamagui/web — pnpm monorepos duplicate it
// across packages/ui + apps/web even with shamefully-hoist. Until that
// dedup is solved (likely via pnpm overrides or tamagui-loader injection),
// this app uses plain HTML/CSS components in apps/web/app/*.tsx and skips
// withTamagui entirely.
module.exports = {
  reactStrictMode: true,
  // @iot/api still has TS source; @iot/ui is unused at runtime here.
  transpilePackages: ['@iot/api'],
  output: 'standalone',
  webpack: (config) => {
    // Stub left in case future dependencies pull react-native-svg again.
    config.resolve.alias = {
      ...config.resolve.alias,
      '@react-native/assets-registry/registry': path.resolve(
        __dirname,
        'src/stubs/assets-registry.js',
      ),
    }
    return config
  },
}
