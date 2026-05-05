# User Dashboard + Mobile App Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Apple Home 스타일의 사용자 친화적 웹 대시보드 + iOS/Android PWA 또는 네이티브 앱(Expo). 농장주가 폰으로 환경 보고 환기팬 토글하는 게 30초 내 가능해야 함.

**Architecture:** pnpm monorepo. `apps/web` (Next.js 14 App Router) + `apps/mobile` (Expo SDK 51 + expo-router). `packages/ui` (Tamagui — cross-platform 컴포넌트, ~70% 공유) + `packages/api` (TanStack Query hooks — 100% 공유). 백엔드는 기존 FastAPI 그대로. 실시간 업데이트는 SSE (`/api/stream`) — MQTT subscriber → asyncio queue → SSE push.

**Tech Stack:**
- Monorepo: pnpm workspaces
- Web: Next.js 14 App Router, React 18, Tamagui
- Mobile: Expo SDK 51, expo-router, React Native, Tamagui
- Shared UI: Tamagui (StyleSheet → web/native 자동 컴파일)
- Data: TanStack Query v5 + axios + JWT
- Realtime: Server-Sent Events (EventSource on web, react-native-sse on mobile)
- Charts: Recharts (web) — 1차 MVP는 모바일 차트 생략, 카드만
- Auth: 기존 Keycloak (PKCE flow). Sim mode는 `sim-fake-jwt.py` 출력을 localStorage에 수동 입력
- Backend: 기존 FastAPI + 새 endpoint 2개 (`/api/stream`, `/api/dashboard`)

**Visual Direction:** Apple Home 모방
- 사이트 selector (상단 드롭다운): "농장 1동 ▼"
- 센서 카드 그리드 (3 컬럼): 큰 숫자 + 단위 + 라벨 + 컬러 인디케이터 (정상/주의/위험)
- 즐겨찾기 (액추에이터 토글): 큰 round 버튼 + 아이콘 + 상태 텍스트
- 다크모드 자동 (시스템 설정 따라감)
- 컬러 토큰: blue (정상), orange (주의), red (위험), green (액티브)

**Out of Scope (Phase 2로 미룸):**
- 알림/푸시 (이번엔 안 만듬, 라이트 MVP)
- 다중 사용자 권한 UI (백엔드는 이미 있음, UI는 다음 phase)
- 24h 트렌드 차트 (1차는 카드만, 차트는 별도 페이지로 task 추가)
- 사용자 등록/관리 페이지

---

## Phase Overview

| Phase | Tasks | Deliverable |
|---|---|---|
| **A. Foundation** | 1-4 | pnpm workspace, Tamagui 셋업, API client, 디자인 토큰 |
| **B. Web MVP** | 5-10 | 사이트 selector, 센서 카드 그리드, 액추에이터 토글, SSE 실시간, 24h 차트 |
| **C. Mobile MVP** | 11-14 | Expo 앱, 동일 UI 컴포넌트 재사용, 네비게이션 |
| **D. Integration** | 15-17 | install-sim.sh 통합, nginx 정적 서빙, 문서 |

총 17 tasks. CC+gstack 기준 1-2일.

---

## Phase A: Foundation

### Task 1: pnpm Monorepo 초기화

**Files:**
- Create: `package.json` (root)
- Create: `pnpm-workspace.yaml`
- Create: `.npmrc`
- Create: `apps/.gitkeep`, `packages/.gitkeep`

**Step 1: pnpm 설치 확인**

```bash
which pnpm || curl -fsSL https://get.pnpm.io/install.sh | sh -
pnpm --version  # >= 9.0
```

**Step 2: 루트 package.json 작성**

```json
{
  "name": "iot-gateway-server-monorepo",
  "private": true,
  "version": "0.1.0",
  "scripts": {
    "dev:web": "pnpm --filter @iot/web dev",
    "dev:mobile": "pnpm --filter @iot/mobile start",
    "build:web": "pnpm --filter @iot/web build",
    "lint": "pnpm -r lint",
    "test": "pnpm -r test"
  },
  "packageManager": "pnpm@9.0.0",
  "engines": {
    "node": ">=20.0.0"
  }
}
```

**Step 3: pnpm-workspace.yaml 작성**

```yaml
packages:
  - "apps/*"
  - "packages/*"
```

**Step 4: .npmrc**

```ini
node-linker=hoisted
shamefully-hoist=true
public-hoist-pattern[]=*tamagui*
public-hoist-pattern[]=*expo*
```

**Step 5: 디렉토리 생성 + 초기 커밋**

```bash
mkdir -p apps packages
touch apps/.gitkeep packages/.gitkeep
git add package.json pnpm-workspace.yaml .npmrc apps/.gitkeep packages/.gitkeep
git commit -m "chore(monorepo): init pnpm workspace for web+mobile apps"
```

---

### Task 2: packages/ui — Tamagui 디자인 토큰 (Apple Home 톤)

**Files:**
- Create: `packages/ui/package.json`
- Create: `packages/ui/tamagui.config.ts`
- Create: `packages/ui/src/tokens.ts`
- Create: `packages/ui/src/index.ts`
- Create: `packages/ui/tsconfig.json`

**Step 1: package.json**

```json
{
  "name": "@iot/ui",
  "version": "0.1.0",
  "main": "src/index.ts",
  "types": "src/index.ts",
  "dependencies": {
    "tamagui": "^1.108.0",
    "@tamagui/config": "^1.108.0",
    "@tamagui/lucide-icons": "^1.108.0"
  },
  "peerDependencies": {
    "react": "^18.0.0",
    "react-native": ">=0.74"
  }
}
```

**Step 2: tokens.ts (Apple Home 색상)**

```ts
import { tokens as base } from '@tamagui/config/v3'

export const tokens = {
  ...base,
  color: {
    ...base.color,
    statusOk: '#34C759',       // green — 정상
    statusWarn: '#FF9500',     // orange — 주의
    statusDanger: '#FF3B30',   // red — 위험
    statusActive: '#007AFF',   // blue — 액티브
    cardBg: '#FFFFFF',
    cardBgDark: '#1C1C1E',
    text: '#000000',
    textDark: '#FFFFFF',
    textMuted: '#8E8E93',
  },
  size: {
    ...base.size,
    cardRadius: 16,
    cardPad: 20,
    iconLarge: 48,
  },
}
```

**Step 3: tamagui.config.ts**

```ts
import { createTamagui } from 'tamagui'
import { config as defaultConfig } from '@tamagui/config/v3'
import { tokens } from './src/tokens'

export const config = createTamagui({
  ...defaultConfig,
  tokens,
  themes: {
    light: { background: tokens.color.cardBg, color: tokens.color.text },
    dark: { background: '#000000', color: tokens.color.textDark },
  },
})

export type AppConfig = typeof config
declare module 'tamagui' {
  interface TamaguiCustomConfig extends AppConfig {}
}
```

**Step 4: index.ts — re-export**

```ts
export * from 'tamagui'
export { config } from '../tamagui.config'
```

**Step 5: tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*", "tamagui.config.ts"]
}
```

**Step 6: 설치 + 커밋**

```bash
cd packages/ui && pnpm install && cd ../..
git add packages/ui
git commit -m "feat(ui): Tamagui config + Apple Home color tokens"
```

---

### Task 3: packages/api — TanStack Query hooks

**Files:**
- Create: `packages/api/package.json`
- Create: `packages/api/src/client.ts`
- Create: `packages/api/src/types.ts`
- Create: `packages/api/src/hooks/useGateways.ts`
- Create: `packages/api/src/hooks/useDashboard.ts`
- Create: `packages/api/src/hooks/useCommand.ts`
- Create: `packages/api/src/hooks/useStream.ts`
- Create: `packages/api/src/index.ts`
- Test: `packages/api/src/__tests__/client.test.ts`

**Step 1: 테스트 먼저 작성 (TDD RED)**

`packages/api/src/__tests__/client.test.ts`:

```ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createApiClient } from '../client'

describe('createApiClient', () => {
  it('attaches Authorization header when token is provided', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: [] }),
    })
    global.fetch = fetchMock as any

    const api = createApiClient({ baseUrl: 'http://x', getToken: () => 'tok123' })
    await api.get('/api/gateways')

    expect(fetchMock).toHaveBeenCalledWith(
      'http://x/api/gateways',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer tok123' }),
      })
    )
  })

  it('throws ApiError on non-2xx', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'expired' }),
    }) as any

    const api = createApiClient({ baseUrl: 'http://x', getToken: () => 't' })
    await expect(api.get('/api/x')).rejects.toThrow(/401/)
  })
})
```

**Step 2: 테스트 실행 (FAIL)**

```bash
cd packages/api && pnpm test
```

Expected: FAIL — `createApiClient` not defined.

**Step 3: 최소 구현 (GREEN)**

`packages/api/src/client.ts`:

```ts
export interface ApiClientConfig {
  baseUrl: string
  getToken: () => string | null
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(`${status}: ${message}`)
  }
}

export function createApiClient(cfg: ApiClientConfig) {
  const headers = () => {
    const token = cfg.getToken()
    return {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    }
  }

  async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const res = await fetch(`${cfg.baseUrl}${path}`, {
      method,
      headers: headers(),
      ...(body ? { body: JSON.stringify(body) } : {}),
    })
    if (!res.ok) {
      let detail = res.statusText
      try {
        const j = await res.json()
        detail = j.detail ?? detail
      } catch {}
      throw new ApiError(res.status, detail)
    }
    return res.json() as Promise<T>
  }

  return {
    get: <T>(p: string) => request<T>('GET', p),
    post: <T>(p: string, b: unknown) => request<T>('POST', p, b),
    patch: <T>(p: string, b: unknown) => request<T>('PATCH', p, b),
  }
}
```

**Step 4: 테스트 통과 확인 (GREEN)**

```bash
pnpm test
```

Expected: 2 PASS.

**Step 5: types.ts — 백엔드 스키마 mirror**

```ts
export interface Gateway {
  id: string
  serial_number: string
  name: string
  status: 'online' | 'offline' | 'degraded'
  site_id: string
}

export interface SensorReading {
  channel_id: string
  channel_name: string
  measurement_key: string
  value: number
  unit: string
  ts: string
  status: 'ok' | 'warn' | 'danger'
}

export interface ActuatorChannel {
  id: string
  slug: string
  display_name: string
  state: 'on' | 'off' | 'unknown'
  enabled: boolean
}

export interface DashboardData {
  gateway: Gateway
  sensors: SensorReading[]
  actuators: ActuatorChannel[]
  last_seen: string
}

export interface CommandPayload {
  actuator_channel_id: string
  action: 'ON' | 'OFF'
  require_ack: boolean
}
```

**Step 6: hooks/useDashboard.ts**

```ts
import { useQuery } from '@tanstack/react-query'
import type { DashboardData } from '../types'
import { useApi } from './useApi'

export function useDashboard(gatewayId: string | null) {
  const api = useApi()
  return useQuery<DashboardData>({
    queryKey: ['dashboard', gatewayId],
    queryFn: () => api.get<DashboardData>(`/api/dashboard?gateway_id=${gatewayId}`),
    enabled: !!gatewayId,
    staleTime: 5_000,
  })
}
```

**Step 7: hooks/useCommand.ts**

```ts
import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { CommandPayload } from '../types'
import { useApi } from './useApi'

export function useCommand(gatewayId: string) {
  const api = useApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: CommandPayload) =>
      api.post(`/api/gateways/${gatewayId}/commands`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dashboard', gatewayId] }),
  })
}
```

**Step 8: hooks/useStream.ts (SSE — web only)**

```ts
import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'

export function useStream(gatewayId: string | null, getToken: () => string | null) {
  const qc = useQueryClient()
  useEffect(() => {
    if (!gatewayId) return
    const token = getToken()
    const url = `/api/stream?gateway_id=${gatewayId}&token=${token ?? ''}`
    const es = new EventSource(url)
    es.onmessage = (e) => {
      // Backend pushes "telemetry_updated" → invalidate dashboard
      qc.invalidateQueries({ queryKey: ['dashboard', gatewayId] })
    }
    es.onerror = () => es.close()
    return () => es.close()
  }, [gatewayId, qc, getToken])
}
```

**Step 9: useApi.ts (provider)**

```ts
import { createContext, useContext } from 'react'
import { createApiClient, type ApiClientConfig } from '../client'

const ApiContext = createContext<ReturnType<typeof createApiClient> | null>(null)

export function ApiProvider({
  config,
  children,
}: {
  config: ApiClientConfig
  children: React.ReactNode
}) {
  const api = createApiClient(config)
  return <ApiContext.Provider value={api}>{children}</ApiContext.Provider>
}

export function useApi() {
  const api = useContext(ApiContext)
  if (!api) throw new Error('ApiProvider missing')
  return api
}
```

**Step 10: index.ts + 커밋**

```ts
export * from './client'
export * from './types'
export * from './hooks/useApi'
export * from './hooks/useDashboard'
export * from './hooks/useCommand'
export * from './hooks/useStream'
```

```bash
pnpm test
git add packages/api
git commit -m "feat(api): TanStack Query hooks + JWT-aware fetch client"
```

---

### Task 4: 백엔드에 `/api/dashboard` + `/api/stream` endpoint 추가

> **Note (post-review):** SSE was removed — see commit log for `feat(server): replace SSE with client polling`. Real-time updates handled by TanStack Query `refetchInterval: 5_000`. Phase 2 will add MQTT-bridge SSE properly.

**Files:**
- Create: `server/app/routers/dashboard.py`
- Modify: `server/app/main.py` — router 등록
- Test: `server/tests/test_dashboard.py`

**Step 1: 테스트 먼저 (TDD RED)**

`server/tests/test_dashboard.py`:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_dashboard_returns_aggregated_view(client: AsyncClient, seeded_gateway):
    res = await client.get(f"/api/dashboard?gateway_id={seeded_gateway.id}")
    assert res.status_code == 200
    body = res.json()
    assert "gateway" in body
    assert "sensors" in body
    assert "actuators" in body
    assert isinstance(body["sensors"], list)
    assert isinstance(body["actuators"], list)


@pytest.mark.asyncio
async def test_dashboard_404_for_unknown_gateway(client: AsyncClient):
    res = await client.get("/api/dashboard?gateway_id=00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404
```

**Step 2: 실행 (FAIL)**

```bash
cd server && pytest tests/test_dashboard.py -v
```

**Step 3: 구현**

`server/app/routers/dashboard.py`:

```python
"""Dashboard aggregator — 한 번의 호출로 카드 그리드를 그릴 모든 데이터."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_user
from app.db import get_session
from app.models import ActuatorChannel, Gateway, SensorChannel, Telemetry

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _classify(value: float, key: str) -> str:
    """간단한 임계치 → status. Phase 2에서 sensor_profile 기반으로 교체."""
    thresholds = {
        "co2_ppm": (1000, 1500),
        "temperature_c": (28, 35),
        "humidity_pct": (80, 90),
    }
    warn, danger = thresholds.get(key, (float("inf"), float("inf")))
    if value >= danger:
        return "danger"
    if value >= warn:
        return "warn"
    return "ok"


@router.get("")
async def get_dashboard(
    gateway_id: UUID,
    user=Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    gw = await session.get(Gateway, gateway_id)
    if not gw:
        raise HTTPException(404, "gateway not found")

    # 최신 telemetry per channel/measurement
    rows = await session.execute(
        select(Telemetry)
        .where(Telemetry.gateway_id == gateway_id)
        .order_by(Telemetry.ts.desc())
        .limit(50)
    )
    latest = {}
    for t in rows.scalars():
        key = (str(t.sensor_channel_id), t.measurement_key)
        if key not in latest:
            latest[key] = t

    # Channel display names
    ch_rows = await session.execute(
        select(SensorChannel).where(SensorChannel.gateway_id == gateway_id)
    )
    ch_names = {str(c.id): c.display_name for c in ch_rows.scalars()}

    sensors = [
        {
            "channel_id": str(t.sensor_channel_id),
            "channel_name": ch_names.get(str(t.sensor_channel_id), t.measurement_key),
            "measurement_key": t.measurement_key,
            "value": float(t.value),
            "unit": t.unit or "",
            "ts": t.ts.isoformat(),
            "status": _classify(float(t.value), t.measurement_key),
        }
        for t in latest.values()
    ]

    act_rows = await session.execute(
        select(ActuatorChannel).where(ActuatorChannel.gateway_id == gateway_id)
    )
    actuators = [
        {
            "id": str(a.id),
            "slug": a.slug,
            "display_name": a.display_name,
            "state": a.last_known_state or "unknown",
            "enabled": a.enabled,
        }
        for a in act_rows.scalars()
    ]

    return {
        "gateway": {
            "id": str(gw.id),
            "serial_number": gw.serial_number,
            "name": gw.name,
            "status": gw.status,
            "site_id": str(gw.site_id) if gw.site_id else None,
        },
        "sensors": sensors,
        "actuators": actuators,
        "last_seen": gw.last_seen.isoformat() if gw.last_seen else None,
    }
```

**Step 4: 테스트 통과 확인**

```bash
pytest tests/test_dashboard.py -v
```

Expected: 2 PASS.

**Step 5: main.py 등록 + SSE endpoint**

`server/app/routers/dashboard.py` 끝에 추가:

```python
import asyncio
from fastapi import Request
from fastapi.responses import StreamingResponse

# 모듈 레벨 — gateway_id → set of asyncio.Queue
_subscribers: dict[str, set[asyncio.Queue]] = {}


async def notify_telemetry(gateway_id: str) -> None:
    """worker에서 telemetry insert 후 호출. Sub들에게 push."""
    for q in _subscribers.get(gateway_id, set()):
        try:
            q.put_nowait("telemetry_updated")
        except asyncio.QueueFull:
            pass


@router.get("/stream")
async def stream(
    gateway_id: UUID,
    request: Request,
    user=Depends(require_user),
):
    gw_key = str(gateway_id)
    queue: asyncio.Queue = asyncio.Queue(maxsize=10)
    _subscribers.setdefault(gw_key, set()).add(queue)

    async def gen():
        try:
            yield "data: connected\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            _subscribers[gw_key].discard(queue)

    return StreamingResponse(gen(), media_type="text/event-stream")
```

`server/app/main.py`에 추가:

```python
from app.routers import dashboard
# ...
app.include_router(dashboard.router, prefix="/api")
```

**Step 6: worker에서 notify hook**

`server/worker/handlers/telemetry.py`의 INSERT 성공 직후:

```python
from app.routers.dashboard import notify_telemetry
await notify_telemetry(str(gateway_id))
```

**Step 7: 전체 테스트 + 커밋**

```bash
cd server && pytest -q
git add server/app/routers/dashboard.py server/app/main.py \
        server/worker/handlers/telemetry.py server/tests/test_dashboard.py
git commit -m "feat(server): dashboard aggregator + SSE telemetry stream"
```

---

## Phase B: Web MVP

### Task 5: apps/web — Next.js 14 셋업 + Tamagui 통합

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/next.config.js`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/app/layout.tsx`
- Create: `apps/web/app/providers.tsx`
- Create: `apps/web/app/page.tsx` (placeholder)

**Step 1: package.json**

```json
{
  "name": "@iot/web",
  "version": "0.1.0",
  "scripts": {
    "dev": "next dev -p 3000",
    "build": "next build",
    "start": "next start -p 3000",
    "lint": "next lint"
  },
  "dependencies": {
    "@iot/ui": "workspace:*",
    "@iot/api": "workspace:*",
    "@tanstack/react-query": "^5.51.0",
    "next": "14.2.5",
    "react": "18.3.1",
    "react-dom": "18.3.1",
    "tamagui": "^1.108.0",
    "@tamagui/next-plugin": "^1.108.0",
    "recharts": "^2.12.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "typescript": "^5.5.0"
  }
}
```

**Step 2: next.config.js**

```js
const { withTamagui } = require('@tamagui/next-plugin')

module.exports = withTamagui({
  config: '../../packages/ui/tamagui.config.ts',
  components: ['tamagui', '@iot/ui'],
  appDir: true,
})({
  reactStrictMode: true,
  transpilePackages: ['@iot/ui', '@iot/api', 'tamagui'],
})
```

**Step 3: app/layout.tsx**

```tsx
import { Providers } from './providers'

export const metadata = { title: '농장 모니터' }

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body style={{ margin: 0, fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif' }}>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
```

**Step 4: app/providers.tsx**

```tsx
'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { TamaguiProvider } from 'tamagui'
import { config } from '@iot/ui'
import { ApiProvider } from '@iot/api'
import { useState } from 'react'

export function Providers({ children }: { children: React.ReactNode }) {
  const [qc] = useState(() => new QueryClient())
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
  return (
    <TamaguiProvider config={config} defaultTheme="light">
      <QueryClientProvider client={qc}>
        <ApiProvider config={{ baseUrl, getToken: () => localStorage.getItem('jwt') }}>
          {children}
        </ApiProvider>
      </QueryClientProvider>
    </TamaguiProvider>
  )
}
```

**Step 5: 더미 page.tsx**

```tsx
export default function Home() {
  return <main>대시보드 준비 중</main>
}
```

**Step 6: 빌드 테스트 + 커밋**

```bash
cd apps/web && pnpm install && pnpm build && cd ../..
git add apps/web
git commit -m "feat(web): Next.js 14 scaffold + Tamagui + TanStack Query providers"
```

---

### Task 6: SiteSelector 컴포넌트 (TDD)

**Files:**
- Create: `packages/ui/src/components/SiteSelector.tsx`
- Test: `packages/ui/src/components/__tests__/SiteSelector.test.tsx`

**Step 1: 테스트 (RED)**

```tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { TamaguiProvider } from 'tamagui'
import { config } from '../../../tamagui.config'
import { SiteSelector } from '../SiteSelector'

const wrap = (ui: React.ReactNode) => (
  <TamaguiProvider config={config} defaultTheme="light">{ui}</TamaguiProvider>
)

describe('SiteSelector', () => {
  it('renders gateway names', () => {
    render(
      wrap(
        <SiteSelector
          gateways={[{ id: '1', name: '농장 1동' }, { id: '2', name: '농장 2동' }]}
          value="1"
          onChange={() => {}}
        />
      )
    )
    expect(screen.getByText('농장 1동')).toBeInTheDocument()
  })

  it('calls onChange with selected id', () => {
    const onChange = jest.fn()
    render(
      wrap(
        <SiteSelector
          gateways={[{ id: '1', name: 'A' }, { id: '2', name: 'B' }]}
          value="1"
          onChange={onChange}
        />
      )
    )
    fireEvent.click(screen.getByText('A'))
    fireEvent.click(screen.getByText('B'))
    expect(onChange).toHaveBeenCalledWith('2')
  })
})
```

**Step 2: 실행 (FAIL)**

```bash
cd packages/ui && pnpm test
```

**Step 3: 구현**

```tsx
import { Select, Adapt, Sheet } from 'tamagui'
import { ChevronDown } from '@tamagui/lucide-icons'

export interface GatewayOption {
  id: string
  name: string
}

export interface SiteSelectorProps {
  gateways: GatewayOption[]
  value: string
  onChange: (id: string) => void
}

export function SiteSelector({ gateways, value, onChange }: SiteSelectorProps) {
  return (
    <Select value={value} onValueChange={onChange}>
      <Select.Trigger iconAfter={ChevronDown} width={240}>
        <Select.Value placeholder="사이트 선택" />
      </Select.Trigger>
      <Adapt when="sm" platform="touch">
        <Sheet modal dismissOnSnapToBottom>
          <Sheet.Frame><Adapt.Contents /></Sheet.Frame>
          <Sheet.Overlay />
        </Sheet>
      </Adapt>
      <Select.Content>
        <Select.Viewport>
          {gateways.map((g, i) => (
            <Select.Item key={g.id} value={g.id} index={i}>
              <Select.ItemText>{g.name}</Select.ItemText>
            </Select.Item>
          ))}
        </Select.Viewport>
      </Select.Content>
    </Select>
  )
}
```

**Step 4: 통과 확인 + 커밋**

```bash
pnpm test
git add packages/ui/src/components/SiteSelector.tsx \
        packages/ui/src/components/__tests__/SiteSelector.test.tsx
git commit -m "feat(ui): SiteSelector dropdown with mobile sheet adapter"
```

---

### Task 7: SensorCard 컴포넌트 (TDD)

**Files:**
- Create: `packages/ui/src/components/SensorCard.tsx`
- Test: `packages/ui/src/components/__tests__/SensorCard.test.tsx`

**Step 1: 테스트**

```tsx
import { render, screen } from '@testing-library/react'
import { TamaguiProvider } from 'tamagui'
import { config } from '../../../tamagui.config'
import { SensorCard } from '../SensorCard'

const wrap = (ui: React.ReactNode) => (
  <TamaguiProvider config={config} defaultTheme="light">{ui}</TamaguiProvider>
)

describe('SensorCard', () => {
  it('shows value and unit', () => {
    render(wrap(<SensorCard label="온도" value={22.4} unit="°C" status="ok" />))
    expect(screen.getByText(/22\.4/)).toBeInTheDocument()
    expect(screen.getByText(/°C/)).toBeInTheDocument()
    expect(screen.getByText('온도')).toBeInTheDocument()
  })

  it('applies danger color when status=danger', () => {
    render(wrap(<SensorCard label="CO2" value={1600} unit="ppm" status="danger" />))
    const valueEl = screen.getByText(/1600/)
    expect(valueEl).toHaveStyle({ color: '#FF3B30' })
  })
})
```

**Step 2: 실행 (FAIL)**

**Step 3: 구현**

```tsx
import { Card, H2, Paragraph, YStack, XStack } from 'tamagui'

const STATUS_COLOR = {
  ok: '#34C759',
  warn: '#FF9500',
  danger: '#FF3B30',
} as const

export interface SensorCardProps {
  label: string
  value: number
  unit: string
  status: 'ok' | 'warn' | 'danger'
}

export function SensorCard({ label, value, unit, status }: SensorCardProps) {
  const color = STATUS_COLOR[status]
  return (
    <Card elevate size="$4" bordered padding="$4" minWidth={120} minHeight={120}>
      <YStack gap="$2" alignItems="flex-start">
        <Paragraph theme="alt2" size="$2">{label}</Paragraph>
        <XStack alignItems="baseline" gap="$1">
          <H2 style={{ color }}>{value.toFixed(1)}</H2>
          <Paragraph theme="alt2" size="$3">{unit}</Paragraph>
        </XStack>
      </YStack>
    </Card>
  )
}
```

**Step 4: 통과 확인 + 커밋**

```bash
pnpm test
git add .
git commit -m "feat(ui): SensorCard with status color (Apple Home style)"
```

---

### Task 8: ActuatorToggle 컴포넌트 (TDD)

**Files:**
- Create: `packages/ui/src/components/ActuatorToggle.tsx`
- Test: `packages/ui/src/components/__tests__/ActuatorToggle.test.tsx`

**Step 1: 테스트**

```tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { TamaguiProvider } from 'tamagui'
import { config } from '../../../tamagui.config'
import { ActuatorToggle } from '../ActuatorToggle'

const wrap = (ui: React.ReactNode) => (
  <TamaguiProvider config={config} defaultTheme="light">{ui}</TamaguiProvider>
)

describe('ActuatorToggle', () => {
  it('shows display name and state text', () => {
    render(wrap(<ActuatorToggle label="환기팬" state="on" onToggle={() => {}} />))
    expect(screen.getByText('환기팬')).toBeInTheDocument()
    expect(screen.getByText('켜짐')).toBeInTheDocument()
  })

  it('calls onToggle with opposite state when clicked', () => {
    const onToggle = jest.fn()
    render(wrap(<ActuatorToggle label="x" state="off" onToggle={onToggle} />))
    fireEvent.click(screen.getByRole('button'))
    expect(onToggle).toHaveBeenCalledWith('on')
  })

  it('disabled while loading', () => {
    const onToggle = jest.fn()
    render(wrap(<ActuatorToggle label="x" state="off" loading onToggle={onToggle} />))
    fireEvent.click(screen.getByRole('button'))
    expect(onToggle).not.toHaveBeenCalled()
  })
})
```

**Step 2: 실행 (FAIL)**

**Step 3: 구현**

```tsx
import { Button, Card, Paragraph, YStack, Spinner } from 'tamagui'
import { Power } from '@tamagui/lucide-icons'

export interface ActuatorToggleProps {
  label: string
  state: 'on' | 'off' | 'unknown'
  loading?: boolean
  onToggle: (next: 'on' | 'off') => void
}

export function ActuatorToggle({ label, state, loading, onToggle }: ActuatorToggleProps) {
  const isOn = state === 'on'
  return (
    <Card bordered padding="$4" minWidth={140} minHeight={140}>
      <YStack gap="$2" alignItems="center" justifyContent="center">
        <Button
          size="$6"
          circular
          onPress={() => !loading && onToggle(isOn ? 'off' : 'on')}
          backgroundColor={isOn ? '#007AFF' : '$gray5'}
          icon={loading ? <Spinner /> : <Power color={isOn ? 'white' : '$gray11'} />}
          disabled={loading}
        />
        <Paragraph fontWeight="600">{label}</Paragraph>
        <Paragraph theme="alt2" size="$2">
          {state === 'on' ? '켜짐' : state === 'off' ? '꺼짐' : '알 수 없음'}
        </Paragraph>
      </YStack>
    </Card>
  )
}
```

**Step 4: 통과 + 커밋**

```bash
pnpm test
git add .
git commit -m "feat(ui): ActuatorToggle with loading state"
```

---

### Task 9: web app/page.tsx — 대시보드 메인 화면 통합

**Files:**
- Modify: `apps/web/app/page.tsx`
- Create: `apps/web/app/components/DashboardScreen.tsx`

**Step 1: DashboardScreen.tsx**

```tsx
'use client'

import { useState, useEffect } from 'react'
import { YStack, XStack, H1, Paragraph, Spinner } from 'tamagui'
import { SiteSelector, SensorCard, ActuatorToggle } from '@iot/ui'
import { useDashboard, useCommand, useApi } from '@iot/api'

export function DashboardScreen() {
  const api = useApi()
  const [gateways, setGateways] = useState<{ id: string; name: string }[]>([])
  const [selected, setSelected] = useState<string | null>(null)

  useEffect(() => {
    api.get<any[]>('/api/gateways').then((list) => {
      setGateways(list.map((g) => ({ id: g.id, name: g.name || g.serial_number })))
      if (list[0]) setSelected(list[0].id)
    })
  }, [api])

  const { data, isLoading } = useDashboard(selected)
  const { mutate: sendCmd, isPending } = useCommand(selected ?? '')
  // useStream removed — useDashboard polls every 5s via refetchInterval

  if (isLoading || !data) return <Spinner />

  return (
    <YStack padding="$4" gap="$4" maxWidth={900} margin="auto">
      <XStack justifyContent="space-between" alignItems="center">
        <H1 size="$8">{data.gateway.name}</H1>
        <SiteSelector gateways={gateways} value={selected ?? ''} onChange={setSelected} />
      </XStack>

      <Paragraph theme="alt2">
        마지막 업데이트: {data.last_seen ? new Date(data.last_seen).toLocaleTimeString() : '없음'}
      </Paragraph>

      <YStack gap="$3">
        <Paragraph fontWeight="700" size="$5">센서</Paragraph>
        <XStack flexWrap="wrap" gap="$3">
          {data.sensors.map((s) => (
            <SensorCard
              key={`${s.channel_id}-${s.measurement_key}`}
              label={s.channel_name}
              value={s.value}
              unit={s.unit}
              status={s.status}
            />
          ))}
        </XStack>
      </YStack>

      <YStack gap="$3">
        <Paragraph fontWeight="700" size="$5">즐겨찾기</Paragraph>
        <XStack flexWrap="wrap" gap="$3">
          {data.actuators.map((a) => (
            <ActuatorToggle
              key={a.id}
              label={a.display_name}
              state={a.state}
              loading={isPending}
              onToggle={(next) =>
                sendCmd({
                  actuator_channel_id: a.id,
                  action: next === 'on' ? 'ON' : 'OFF',
                  require_ack: true,
                })
              }
            />
          ))}
        </XStack>
      </YStack>
    </YStack>
  )
}
```

**Step 2: page.tsx 교체**

```tsx
import { DashboardScreen } from './components/DashboardScreen'
export default function Home() {
  return <DashboardScreen />
}
```

**Step 3: 수동 검증 (실 데이터)**

```bash
# 백엔드 + 워커 + 게이트웨이 sim 모두 떠 있는 상태에서:
cd apps/web && pnpm dev
# 브라우저: http://localhost:3000
# Console에서: localStorage.setItem('jwt', '<sim-fake-jwt 출력>')
# 새로고침 → 대시보드 보임
```

확인:
- 카드 그리드 보이는가
- 5초마다 SSE 신호로 카드 값 업데이트되는가
- 토글 누르면 mosquitto_sub로 command 페이로드 보이는가

**Step 4: 커밋**

```bash
git add apps/web/app
git commit -m "feat(web): DashboardScreen with sensor cards + actuator toggles + SSE realtime"
```

---

### Task 10: 24h 트렌드 차트 페이지 (web only)

**Files:**
- Create: `apps/web/app/trends/page.tsx`
- Create: `apps/web/app/trends/components/TrendChart.tsx`
- Modify: `server/app/routers/telemetry.py` — `/api/telemetry/range` (없으면 추가)

**Step 1: 백엔드 endpoint 확인 + 추가 (필요시)**

`server/app/routers/telemetry.py`에 추가:

```python
from datetime import datetime, timedelta

@router.get("/range")
async def telemetry_range(
    gateway_id: UUID,
    measurement_key: str,
    hours: int = 24,
    user=Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    since = datetime.utcnow() - timedelta(hours=hours)
    rows = await session.execute(
        select(Telemetry.ts, Telemetry.value)
        .where(
            Telemetry.gateway_id == gateway_id,
            Telemetry.measurement_key == measurement_key,
            Telemetry.ts >= since,
        )
        .order_by(Telemetry.ts.asc())
    )
    return [{"ts": ts.isoformat(), "value": float(v)} for ts, v in rows]
```

**Step 2: TrendChart.tsx**

```tsx
'use client'
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts'

export function TrendChart({ data, label }: { data: { ts: string; value: number }[]; label: string }) {
  const formatted = data.map((d) => ({
    time: new Date(d.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    value: d.value,
  }))
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={formatted}>
        <XAxis dataKey="time" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip />
        <Line type="monotone" dataKey="value" stroke="#007AFF" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}
```

**Step 3: trends/page.tsx**

```tsx
'use client'
import { useEffect, useState } from 'react'
import { YStack, H1, Paragraph } from 'tamagui'
import { useApi } from '@iot/api'
import { TrendChart } from './components/TrendChart'

export default function TrendsPage() {
  const api = useApi()
  const [series, setSeries] = useState<Record<string, { ts: string; value: number }[]>>({})

  useEffect(() => {
    const gatewayId = localStorage.getItem('selectedGateway')
    if (!gatewayId) return
    Promise.all(
      ['temperature_c', 'humidity_pct', 'co2_ppm'].map((k) =>
        api.get<{ ts: string; value: number }[]>(
          `/api/telemetry/range?gateway_id=${gatewayId}&measurement_key=${k}&hours=24`
        ).then((data) => [k, data] as const)
      )
    ).then((pairs) => setSeries(Object.fromEntries(pairs)))
  }, [api])

  return (
    <YStack padding="$4" gap="$5" maxWidth={900} margin="auto">
      <H1>24시간 추세</H1>
      {Object.entries(series).map(([key, data]) => (
        <YStack key={key} gap="$2">
          <Paragraph fontWeight="600">{key}</Paragraph>
          <TrendChart data={data} label={key} />
        </YStack>
      ))}
    </YStack>
  )
}
```

**Step 4: DashboardScreen에 링크 추가**

`apps/web/app/components/DashboardScreen.tsx` 위에:

```tsx
import Link from 'next/link'
// ... in render:
<Link href="/trends">→ 24h 추세 보기</Link>
```

**Step 5: 커밋**

```bash
git add apps/web server/app/routers/telemetry.py
git commit -m "feat(web): 24h trend chart page with Recharts"
```

---

## Phase C: Mobile MVP

### Task 11: apps/mobile — Expo SDK 51 셋업

**Files:**
- Create: `apps/mobile/package.json`
- Create: `apps/mobile/app.json`
- Create: `apps/mobile/babel.config.js`
- Create: `apps/mobile/metro.config.js`
- Create: `apps/mobile/tsconfig.json`
- Create: `apps/mobile/app/_layout.tsx`
- Create: `apps/mobile/app/index.tsx`

**Step 1: package.json**

```json
{
  "name": "@iot/mobile",
  "version": "0.1.0",
  "main": "expo-router/entry",
  "scripts": {
    "start": "expo start",
    "ios": "expo start --ios",
    "android": "expo start --android",
    "web": "expo start --web"
  },
  "dependencies": {
    "@iot/ui": "workspace:*",
    "@iot/api": "workspace:*",
    "@tanstack/react-query": "^5.51.0",
    "expo": "~51.0.0",
    "expo-router": "~3.5.0",
    "expo-status-bar": "~1.12.0",
    "expo-secure-store": "~13.0.0",
    "react": "18.2.0",
    "react-native": "0.74.5",
    "react-native-safe-area-context": "4.10.5",
    "react-native-screens": "3.31.1",
    "react-native-sse": "^1.2.1",
    "tamagui": "^1.108.0",
    "@tamagui/babel-plugin": "^1.108.0"
  },
  "devDependencies": {
    "@babel/core": "^7.24.0",
    "@types/react": "~18.2.79",
    "typescript": "~5.3.3"
  }
}
```

**Step 2: app.json**

```json
{
  "expo": {
    "name": "농장 모니터",
    "slug": "iot-farm-monitor",
    "version": "0.1.0",
    "orientation": "portrait",
    "userInterfaceStyle": "automatic",
    "ios": { "bundleIdentifier": "com.iotgateway.farmmonitor" },
    "android": { "package": "com.iotgateway.farmmonitor" },
    "plugins": ["expo-router"],
    "scheme": "farmmonitor"
  }
}
```

**Step 3: babel.config.js**

```js
module.exports = function (api) {
  api.cache(true)
  return {
    presets: ['babel-preset-expo'],
    plugins: [
      ['@tamagui/babel-plugin', {
        components: ['tamagui', '@iot/ui'],
        config: '../../packages/ui/tamagui.config.ts',
      }],
      'expo-router/babel',
    ],
  }
}
```

**Step 4: metro.config.js (monorepo 지원)**

```js
const { getDefaultConfig } = require('expo/metro-config')
const path = require('path')

const projectRoot = __dirname
const workspaceRoot = path.resolve(projectRoot, '../..')

const config = getDefaultConfig(projectRoot)
config.watchFolders = [workspaceRoot]
config.resolver.nodeModulesPaths = [
  path.resolve(projectRoot, 'node_modules'),
  path.resolve(workspaceRoot, 'node_modules'),
]
config.resolver.disableHierarchicalLookup = true
module.exports = config
```

**Step 5: app/_layout.tsx**

```tsx
import { Stack } from 'expo-router'
import { TamaguiProvider } from 'tamagui'
import { config } from '@iot/ui'
import { ApiProvider } from '@iot/api'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import * as SecureStore from 'expo-secure-store'

export default function Layout() {
  const [qc] = useState(() => new QueryClient())
  const baseUrl = process.env.EXPO_PUBLIC_API_URL || 'http://10.0.2.2:8000'
  return (
    <TamaguiProvider config={config} defaultTheme="light">
      <QueryClientProvider client={qc}>
        <ApiProvider config={{ baseUrl, getToken: () => SecureStore.getItem('jwt') }}>
          <Stack screenOptions={{ headerShown: false }} />
        </ApiProvider>
      </QueryClientProvider>
    </TamaguiProvider>
  )
}
```

**Step 6: app/index.tsx — placeholder**

```tsx
import { YStack, H1 } from 'tamagui'

export default function Home() {
  return (
    <YStack flex={1} alignItems="center" justifyContent="center">
      <H1>대시보드 준비 중</H1>
    </YStack>
  )
}
```

**Step 7: 빌드/실행 확인**

```bash
cd apps/mobile && pnpm install && pnpm web
# 브라우저에서 expo web preview 보임
```

**Step 8: 커밋**

```bash
git add apps/mobile
git commit -m "feat(mobile): Expo SDK 51 + expo-router + Tamagui scaffold"
```

---

### Task 12: 모바일 DashboardScreen — packages/ui 재사용

**Files:**
- Modify: `apps/mobile/app/index.tsx`
- Create: `apps/mobile/app/components/DashboardScreen.native.tsx`

**Step 1: 모바일용 DashboardScreen 작성**

웹 버전과 거의 동일. SSE 없음 — useDashboard가 5초 polling (refetchInterval). react-native-sse 의존성 불필요.

`apps/mobile/app/components/DashboardScreen.native.tsx`:

```tsx
import { useState, useEffect } from 'react'
import { ScrollView } from 'react-native'
import { YStack, XStack, H1, Paragraph, Spinner } from 'tamagui'
import { SiteSelector, SensorCard, ActuatorToggle } from '@iot/ui'
import { useDashboard, useCommand, useApi } from '@iot/api'

export function DashboardScreen() {
  const api = useApi()
  const [gateways, setGateways] = useState<{ id: string; name: string }[]>([])
  const [selected, setSelected] = useState<string | null>(null)

  useEffect(() => {
    api.get<any[]>('/api/gateways').then((list) => {
      setGateways(list.map((g) => ({ id: g.id, name: g.name || g.serial_number })))
      if (list[0]) setSelected(list[0].id)
    })
  }, [api])

  const { data, isLoading } = useDashboard(selected)
  const { mutate: sendCmd, isPending } = useCommand(selected ?? '')

  if (isLoading || !data) return <Spinner />

  return (
    <ScrollView>
      <YStack padding="$4" gap="$4">
        <H1 size="$7">{data.gateway.name}</H1>
        <SiteSelector gateways={gateways} value={selected ?? ''} onChange={setSelected} />

        <Paragraph theme="alt2">
          {data.last_seen ? new Date(data.last_seen).toLocaleTimeString() : '없음'}
        </Paragraph>

        <Paragraph fontWeight="700">센서</Paragraph>
        <XStack flexWrap="wrap" gap="$3">
          {data.sensors.map((s) => (
            <SensorCard
              key={`${s.channel_id}-${s.measurement_key}`}
              label={s.channel_name}
              value={s.value}
              unit={s.unit}
              status={s.status}
            />
          ))}
        </XStack>

        <Paragraph fontWeight="700">즐겨찾기</Paragraph>
        <XStack flexWrap="wrap" gap="$3">
          {data.actuators.map((a) => (
            <ActuatorToggle
              key={a.id}
              label={a.display_name}
              state={a.state}
              loading={isPending}
              onToggle={(next) =>
                sendCmd({
                  actuator_channel_id: a.id,
                  action: next === 'on' ? 'ON' : 'OFF',
                  require_ack: true,
                })
              }
            />
          ))}
        </XStack>
      </YStack>
    </ScrollView>
  )
}
```

**Step 2: index.tsx 교체**

```tsx
import { DashboardScreen } from './components/DashboardScreen.native'
export default DashboardScreen
```

**Step 3: 수동 검증 (Expo Go 또는 simulator)**

```bash
cd apps/mobile && pnpm start
# 'w' 키 → 웹에서 확인 (가장 빠름)
# 'i' 키 → iOS simulator (Mac만)
# QR → Expo Go 앱
```

**Step 4: 커밋**

```bash
git add apps/mobile
git commit -m "feat(mobile): DashboardScreen reusing @iot/ui components"
```

---

### Task 13: JWT 입력 화면 (sim mode 인증 진입점)

**Files:**
- Create: `apps/web/app/login/page.tsx`
- Create: `apps/mobile/app/login.tsx`
- Modify: `apps/web/app/page.tsx` — JWT 없으면 redirect

**Step 1: web login page**

```tsx
'use client'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { YStack, Input, Button, H2, Paragraph } from 'tamagui'

export default function LoginPage() {
  const [token, setToken] = useState('')
  const router = useRouter()

  return (
    <YStack padding="$4" gap="$4" maxWidth={500} margin="auto" marginTop="$10">
      <H2>로그인</H2>
      <Paragraph theme="alt2">
        Sim mode: 터미널에서 `python3 deploy/scripts/sim-fake-jwt.py` 실행 후 출력 붙여넣기
      </Paragraph>
      <Input
        size="$4"
        placeholder="JWT token..."
        value={token}
        onChangeText={setToken}
        secureTextEntry
      />
      <Button
        theme="active"
        onPress={() => {
          localStorage.setItem('jwt', token)
          router.push('/')
        }}
      >
        들어가기
      </Button>
    </YStack>
  )
}
```

**Step 2: mobile login**

```tsx
import { useRouter } from 'expo-router'
import { useState } from 'react'
import { YStack, Input, Button, H2, Paragraph } from 'tamagui'
import * as SecureStore from 'expo-secure-store'

export default function Login() {
  const [token, setToken] = useState('')
  const router = useRouter()
  return (
    <YStack padding="$4" gap="$4" marginTop="$10">
      <H2>로그인</H2>
      <Paragraph>Sim JWT 붙여넣기</Paragraph>
      <Input value={token} onChangeText={setToken} secureTextEntry />
      <Button
        onPress={() => {
          SecureStore.setItem('jwt', token)
          router.replace('/')
        }}
      >
        들어가기
      </Button>
    </YStack>
  )
}
```

**Step 3: web page.tsx — 토큰 체크**

```tsx
'use client'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { DashboardScreen } from './components/DashboardScreen'

export default function Home() {
  const router = useRouter()
  useEffect(() => {
    if (!localStorage.getItem('jwt')) router.push('/login')
  }, [router])
  return <DashboardScreen />
}
```

**Step 4: 커밋**

```bash
git add apps/web/app/login apps/mobile/app/login.tsx apps/web/app/page.tsx
git commit -m "feat(auth): JWT entry screens for sim mode (web + mobile)"
```

---

### Task 14: 모바일 네비게이션 — 추세 화면 추가

**Files:**
- Create: `apps/mobile/app/trends.tsx`
- Modify: `apps/mobile/app/_layout.tsx` — Stack 화면 정의

**Step 1: trends.tsx (모바일은 단순 리스트만, 차트는 web만)**

```tsx
import { useEffect, useState } from 'react'
import { ScrollView } from 'react-native'
import { YStack, H1, Paragraph, Card } from 'tamagui'
import { useApi } from '@iot/api'

export default function Trends() {
  const api = useApi()
  const [latest, setLatest] = useState<any[]>([])

  useEffect(() => {
    const gatewayId = localStorage?.getItem?.('selectedGateway') // RN에선 별도 처리
    if (!gatewayId) return
    api.get<any>(`/api/dashboard?gateway_id=${gatewayId}`).then((d) => setLatest(d.sensors))
  }, [api])

  return (
    <ScrollView>
      <YStack padding="$4" gap="$3">
        <H1>최근 측정값</H1>
        {latest.map((s) => (
          <Card key={`${s.channel_id}-${s.measurement_key}`} bordered padding="$3">
            <Paragraph fontWeight="600">{s.channel_name}</Paragraph>
            <Paragraph>{s.value} {s.unit}</Paragraph>
            <Paragraph theme="alt2" size="$2">{new Date(s.ts).toLocaleString()}</Paragraph>
          </Card>
        ))}
      </YStack>
    </ScrollView>
  )
}
```

**Step 2: 네비게이션 추가**

`apps/mobile/app/_layout.tsx`에 Stack.Screen 정의는 expo-router가 파일 라우팅으로 자동 처리. 화면 간 이동은 `<Link href="/trends">`.

`apps/mobile/app/components/DashboardScreen.native.tsx`에 추가:

```tsx
import { Link } from 'expo-router'
// ... in render:
<Link href="/trends" asChild>
  <Button>최근 측정값 보기</Button>
</Link>
```

**Step 3: 커밋**

```bash
git add apps/mobile
git commit -m "feat(mobile): trends screen + navigation link"
```

---

## Phase D: Integration

### Task 15: install-sim.sh — Node 설치 + web 빌드 + nginx 정적 서빙

**Files:**
- Modify: `deploy/scripts/install-sim.sh`
- Create: `deploy/nginx/iot-sim.conf`

**Step 1: nginx 설정 작성**

`deploy/nginx/iot-sim.conf`:

```nginx
server {
  listen 80;
  server_name _;

  # 정적 빌드 (Next.js export)
  root /opt/iot-sim/web;
  index index.html;

  # FastAPI proxy
  location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_buffering off;  # SSE 필수
    proxy_read_timeout 1h;
  }

  # SSR/CSR fallback
  location / {
    try_files $uri $uri.html $uri/ /index.html;
  }
}
```

**Step 2: install-sim.sh에 추가** (마지막 systemd unit 정의 직전)

```bash
echo "==> Installing Node 20 + nginx..."
if ! command -v node >/dev/null 2>&1 || [ "$(node -v | cut -d. -f1 | tr -d v)" -lt 20 ]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi
apt-get install -y nginx

echo "==> Installing pnpm..."
npm install -g pnpm@9

echo "==> Building web app..."
cd "$REPO_ROOT"
pnpm install --frozen-lockfile=false
pnpm --filter @iot/web build

# Static export (next.config에 output: 'export' 또는 standalone)
# 1차 MVP는 standalone으로 가고 nginx가 reverse proxy
mkdir -p /opt/iot-sim/web
cp -r apps/web/.next/standalone/* /opt/iot-sim/web/ || true
cp -r apps/web/.next/static /opt/iot-sim/web/.next/ || true
cp -r apps/web/public/* /opt/iot-sim/web/public/ 2>/dev/null || true

echo "==> Configuring nginx..."
cp "$REPO_ROOT/deploy/nginx/iot-sim.conf" /etc/nginx/sites-available/iot-sim
ln -sf /etc/nginx/sites-available/iot-sim /etc/nginx/sites-enabled/iot-sim
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

**Step 3: next.config.js 수정 — standalone output**

```js
module.exports = withTamagui(...)({
  reactStrictMode: true,
  transpilePackages: ['@iot/ui', '@iot/api', 'tamagui'],
  output: 'standalone',  // <-- 추가
})
```

**Step 4: web용 systemd unit (Next.js standalone server)**

`deploy/systemd/iot-sim-web.service`:

```ini
[Unit]
Description=IoT Sim Web (Next.js standalone)
After=iot-sim-backend.service

[Service]
Type=simple
WorkingDirectory=/opt/iot-sim/web
Environment=PORT=3000
Environment=NEXT_PUBLIC_API_URL=http://localhost:8000
ExecStart=/usr/bin/node server.js
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

`install-sim.sh`에 systemd 등록 추가 (기존 unit 등록 패턴 따라).

**Step 5: nginx upstream 변경 (정적 → Next 서버 proxy)**

`deploy/nginx/iot-sim.conf` 수정:

```nginx
location / {
  proxy_pass http://127.0.0.1:3000;
  proxy_http_version 1.1;
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection 'upgrade';
  proxy_set_header Host $host;
}
```

**Step 6: 커밋**

```bash
git add deploy/scripts/install-sim.sh deploy/nginx deploy/systemd/iot-sim-web.service \
        apps/web/next.config.js
git commit -m "feat(deploy): nginx + Next standalone in install-sim.sh"
```

---

### Task 16: sim-verify.sh — 웹 endpoint 추가 검증

**Files:**
- Modify: `deploy/scripts/sim-verify.sh`

**Step 1: 검증 항목 추가**

```bash
# 12. nginx serves web
status_curl=$(curl -s -o /dev/null -w '%{http_code}' http://localhost/)
if [ "$status_curl" = "200" ]; then
  echo "PASS: nginx serves web at /"
else
  echo "FAIL: nginx returned $status_curl"
fi

# 13. /api/dashboard reachable
api_status=$(curl -s -o /dev/null -w '%{http_code}' \
  "http://localhost/api/dashboard?gateway_id=$(...uuid lookup...)")
[ "$api_status" = "401" -o "$api_status" = "200" ] && echo "PASS: dashboard API up" || echo "FAIL"
```

**Step 2: 커밋**

```bash
git add deploy/scripts/sim-verify.sh
git commit -m "test(verify): include web + dashboard endpoints in sim-verify"
```

---

### Task 17: 문서 업데이트

**Files:**
- Modify: `README.md`
- Create: `docs/USER_DASHBOARD_GUIDE.md`
- Modify: `docs/SIMULATION_GUIDE.md`

**Step 1: USER_DASHBOARD_GUIDE.md 작성**

다음 섹션 포함:
- 접속 방법 (`http://localhost/`)
- Sim mode 로그인 (`sim-fake-jwt.py` 출력)
- 화면 설명 (사이트 selector, 센서 카드, 즐겨찾기 토글, 추세)
- 모바일 PWA 설치 (Safari "홈 화면에 추가")
- Expo Go로 모바일 앱 실행 (`pnpm dev:mobile` → QR)
- 트러블슈팅 (JWT 만료, SSE 끊김 등)

**Step 2: README.md 업데이트**

기존 "빠른 시작" 섹션에 추가:

```markdown
### 옵션 A — 시뮬레이션 (이제 웹 대시보드 포함!)

```bash
sudo bash deploy/scripts/install-sim.sh    # 5-15분 (web 빌드 포함)
sudo bash deploy/scripts/sim-verify.sh     # 13/13 PASS 기대
```

브라우저: `http://localhost/`
모바일: 같은 네트워크에서 `http://<wsl-ip>/`, Safari → 홈 화면에 추가 → PWA 설치
```

**Step 3: 커밋**

```bash
git add README.md docs/USER_DASHBOARD_GUIDE.md docs/SIMULATION_GUIDE.md
git commit -m "docs: user dashboard + mobile app guide"
```

---

## Verification Checklist

각 phase 끝나면 체크:

- [ ] **Phase A**: `pnpm test` — packages/api, packages/ui 테스트 모두 PASS
- [ ] **Phase A**: `pnpm --filter @iot/ui build` 성공
- [ ] **Phase A**: `pytest server/tests/test_dashboard.py` PASS (2 tests)
- [ ] **Phase B**: `pnpm dev:web` → `localhost:3000` 카드 보임
- [ ] **Phase B**: 토글 누르면 mosquitto_sub로 command 페이로드 보임
- [ ] **Phase B**: 5초마다 SSE로 카드 값 업데이트 (개발자 도구 Network 탭에 EventSource 보임)
- [ ] **Phase B**: `/trends` 차트 페이지 24h 데이터 그림
- [ ] **Phase C**: `pnpm dev:mobile` → 'w' → 웹 미리보기에서 같은 UI
- [ ] **Phase C**: Expo Go 또는 simulator에서 카드 보임 (실 폰에서는 WSL IP 접근 필요)
- [ ] **Phase D**: `sudo bash deploy/scripts/install-sim.sh` 처음부터 끝까지 성공
- [ ] **Phase D**: `http://localhost/` (port 80, nginx) 접속 → 로그인 → 대시보드
- [ ] **Phase D**: `sudo bash deploy/scripts/sim-verify.sh` 13/13 PASS

---

## Out-of-Scope Recap (Phase 2 이후)

- 알림 / push notification (Expo Push, FCM)
- 다중 사용자 관리 UI (백엔드는 이미 multi-tenant 모델)
- Sensor profile-driven 임계치 (현재 hardcoded `_classify`)
- 차트 더 많이 (히트맵, 비교, 다운로드)
- Apple Health/HomeKit 연동
- 오프라인 모드 / 동기화

---

## Rollback Plan

문제 시 단계별 rollback:

```bash
# 웹/모바일 코드만 제거 (백엔드는 그대로):
git revert <task15-commit>  # nginx 설정 제거
sudo systemctl stop iot-sim-web
sudo rm /etc/nginx/sites-enabled/iot-sim
sudo systemctl reload nginx

# packages/* 통째로 제거:
git rm -r apps packages
git commit -m "revert: roll back monorepo, keep backend"
```

백엔드 `dashboard` router만 살리고 싶으면 Task 4 commit은 유지.
