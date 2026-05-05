// Stub for @react-native/assets-registry on web. The real module uses Flow
// syntax that SWC can't strip. react-native-svg pulls it via resolveAssetUri,
// but on web we never register native asset bundles, so a no-op is safe.
module.exports = {
  registerAsset: () => 0,
  getAssetByID: () => null,
}
