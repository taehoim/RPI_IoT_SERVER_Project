'use client'

import { ReactNode, useState, useMemo } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ApiProvider } from '@iot/api'

// NOTE: TamaguiProvider intentionally absent. Tamagui's static extractor
// duplicates @tamagui/* across packages/ui + apps/web in pnpm monorepos
// (despite shamefully-hoist + public-hoist-pattern), causing
// `simpleHash undefined.length` at build and `Cannot read 'settings'` at
// SSR. Restoring Tamagui in this PR's scope kept hitting the issue;
// deferred to a follow-up with proper module-level dedup (likely via
// pnpm overrides or tamagui-loader injection patterns).
//
// Components in apps/web/app/*.tsx use plain HTML/CSS in the meantime.
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
      baseUrl: process.env.NEXT_PUBLIC_API_URL ?? '',
      getToken: () => (typeof window !== 'undefined' ? localStorage.getItem('jwt') : null),
    }),
    [],
  )
  return (
    <QueryClientProvider client={qc}>
      <ApiProvider config={apiConfig}>{children}</ApiProvider>
    </QueryClientProvider>
  )
}
