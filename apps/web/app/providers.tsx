'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { TamaguiProvider } from 'tamagui'
import { config } from '@iot/ui'
import { ApiProvider } from '@iot/api'
import { useState } from 'react'

const apiConfig = {
  baseUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  getToken: () => (typeof window !== 'undefined' ? localStorage.getItem('jwt') : null),
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [qc] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5_000,
            refetchOnWindowFocus: false,
          },
        },
      })
  )
  return (
    <TamaguiProvider config={config} defaultTheme="light">
      <QueryClientProvider client={qc}>
        <ApiProvider config={apiConfig}>{children}</ApiProvider>
      </QueryClientProvider>
    </TamaguiProvider>
  )
}
