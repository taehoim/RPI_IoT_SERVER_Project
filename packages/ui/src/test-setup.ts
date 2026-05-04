import '@testing-library/jest-dom/vitest'

// jsdom doesn't implement matchMedia; Tamagui's Select calls it on import
// (via its media-query driver). Provide a minimal stub.
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })
}
