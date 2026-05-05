'use client'

import { ReactNode, useState, useMemo } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { TamaguiProvider } from 'tamagui'
import { config } from '@iot/ui'
import { ApiProvider } from '@iot/api'

export function Providers({ children }: { children: ReactNode }) {
  const [qc] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 5_000, refetchOnWindowFocus: false },
        },
      }),
  )
  const apiConfig = useMemo(
    () => ({
      // Empty baseUrl → relative URLs (/api/...) → same origin as page →
      // nginx proxies /api/* to backend :8000. Avoids cross-origin CORS.
      // Set NEXT_PUBLIC_API_URL only when frontend host differs from backend.
      baseUrl: process.env.NEXT_PUBLIC_API_URL ?? '',
      getToken: () => (typeof window !== 'undefined' ? localStorage.getItem('jwt') : null),
    }),
    [],
  )
  return (
    <TamaguiProvider config={config} defaultTheme="light">
      <QueryClientProvider client={qc}>
        <ApiProvider config={apiConfig}>{children}</ApiProvider>
      </QueryClientProvider>
    </TamaguiProvider>
  )
}
