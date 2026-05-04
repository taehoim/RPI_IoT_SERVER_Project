import { createContext, useContext, useMemo, type ReactNode } from 'react'
import { createApiClient, type ApiClientConfig } from '../client'

type ApiClient = ReturnType<typeof createApiClient>
const ApiContext = createContext<ApiClient | null>(null)

/**
 * `config` MUST be stable across renders — `getToken` is captured in closure at
 * client-creation time. Pass either a module-level config object or wrap in `useMemo`.
 * The memo key here intentionally only watches `baseUrl`; consumers that swap `getToken`
 * dynamically (e.g., logout flow) should re-mount this provider.
 */
export function ApiProvider({
  config,
  children,
}: {
  config: ApiClientConfig
  children: ReactNode
}) {
  const api = useMemo(() => createApiClient(config), [config.baseUrl])
  return <ApiContext.Provider value={api}>{children}</ApiContext.Provider>
}

export function useApi(): ApiClient {
  const api = useContext(ApiContext)
  if (!api) throw new Error('ApiProvider missing — wrap your tree in <ApiProvider config={...}>')
  return api
}
