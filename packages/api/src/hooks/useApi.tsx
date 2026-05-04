import { createContext, useContext, useMemo, type ReactNode } from 'react'
import { createApiClient, type ApiClientConfig } from '../client'

type ApiClient = ReturnType<typeof createApiClient>
const ApiContext = createContext<ApiClient | null>(null)

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
