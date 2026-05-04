import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    globals: false,  // explicit imports preferred
    environment: 'node',
  },
})
