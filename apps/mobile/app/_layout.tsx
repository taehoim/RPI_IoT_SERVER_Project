import { useState, useMemo } from 'react'
import { Stack } from 'expo-router'
import { TamaguiProvider, config } from '@iot/ui'
import { ApiProvider } from '@iot/api'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import * as SecureStore from 'expo-secure-store'

export default function Layout() {
  const [qc] = useState(() => new QueryClient())

  // ApiProvider config must be referentially stable across renders. Memoize
  // on baseUrl alone — getToken pulls fresh value each call.
  const apiConfig = useMemo(
    () => ({
      baseUrl: process.env.EXPO_PUBLIC_API_URL || 'http://10.0.2.2:8000',
      getToken: () => SecureStore.getItem('jwt'),
    }),
    [],
  )

  return (
    <TamaguiProvider config={config} defaultTheme="light">
      <QueryClientProvider client={qc}>
        <ApiProvider config={apiConfig}>
          <Stack screenOptions={{ headerShown: false }} />
        </ApiProvider>
      </QueryClientProvider>
    </TamaguiProvider>
  )
}
