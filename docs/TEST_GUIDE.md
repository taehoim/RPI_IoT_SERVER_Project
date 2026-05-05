# 테스트 가이드 — 사용자 대시보드 + 모바일 앱

`feat/user-dashboard-mobile-app` 브랜치(17-task plan)의 동작/회귀 검증 절차.

## 0. 사전 준비

```bash
git checkout feat/user-dashboard-mobile-app
pnpm install --frozen-lockfile=false        # WSL drvfs에서 ~10분
```

설치 결과:
- `node_modules/` 루트(hoisted) + `apps/web/node_modules`, `apps/mobile/node_modules`, `packages/{ui,api}/node_modules`
- pnpm-lock.yaml 변경 없음을 권장 (있으면 다시 freeze 시도)

## 1. 단위/통합 테스트 (CI에서 돌릴 수준)

### 1-1. packages/api (TanStack Query + fetch client) — 4 tests

```bash
pnpm --filter @iot/api test
```

**기대 출력**

```
 ✓ src/__tests__/client.test.ts (4 tests)
   ✓ attaches Authorization header when token present
   ✓ omits Authorization header when token null
   ✓ throws ApiError on non-2xx
   ✓ serializes POST body to JSON
 Test Files  1 passed (1)
      Tests  4 passed (4)
```

### 1-2. packages/ui (Tamagui 컴포넌트) — 7 tests

```bash
pnpm --filter @iot/ui test
```

**기대 출력**

```
 ✓ src/components/__tests__/SiteSelector.test.tsx (2 tests)
 ✓ src/components/__tests__/SensorCard.test.tsx (2 tests)
 ✓ src/components/__tests__/ActuatorToggle.test.tsx (3 tests)
 Test Files  3 passed (3)
      Tests  7 passed (7)
```

> Vitest 첫 실행은 WSL에서 ~150초. 두 번째부터는 캐시로 빠릅니다.

### 1-3. server (FastAPI 대시보드 aggregator) — 4 tests

```bash
cd server && pytest tests/test_dashboard.py -v
```

**기대 출력**

```
tests/test_dashboard.py::test_aggregated_view PASSED
tests/test_dashboard.py::test_empty_when_no_telemetry PASSED
tests/test_dashboard.py::test_404_for_unknown_gateway PASSED
tests/test_dashboard.py::test_classify_thresholds PASSED
======== 4 passed in 1.5s ========
```

### 1-4. 전체 회귀 (한 번에)

```bash
pnpm test                    # vitest 합계 (api + ui = 11 tests)
cd server && pytest          # 모든 backend test (test_dashboard 포함)
```

## 2. 빌드 검증

### 2-1. Web (Next.js 14 standalone)

```bash
pnpm --filter @iot/web build
```

**기대 출력 (마지막)**

```
Route (app)                              Size     First Load JS
┌ ○ /                                    9.86 kB         244 kB
├ ○ /_not-found                          876 B          88.4 kB
├ ○ /login                               3.95 kB         161 kB
└ ○ /trends                              101 kB          266 kB
○  (Static)  prerendered as static content
```

> 6/6 정적 페이지(/, /_not-found, /login, /trends + Next 내부 2개) 생성. WSL drvfs에서 첫 빌드 ~16분.

### 2-2. Mobile (Expo) — 타입 체크만

```bash
pnpm --filter @iot/mobile exec tsc --noEmit
# 또는 Expo Go 미리보기:
pnpm dev:mobile
# 'w' 키 → 웹 미리보기 (가장 빠름)
# QR → 실 폰 Expo Go 앱
```

## 3. 시뮬레이션 통합 (Ubuntu 22.04/24.04)

전체 wire 흐름(HAL → gateway → MQTT → backend → dashboard) 검증.

### 3-1. 설치

```bash
sudo bash deploy/scripts/install-sim.sh
```

설치 항목 (자동):
- PostgreSQL + Mosquitto (loopback only, 익명 허용)
- 백엔드 venv + alembic migrations 0001 + 0002
- gateway-agent (`-tags simulation`, no cgo)
- systemd: `iot-sim-{backend,worker,scheduler,gateway,web}`
- Node 20 + pnpm 9 + nginx
- Next.js standalone 빌드 (`/opt/iot-sim/web`)
- nginx config `/etc/nginx/sites-available/iot-sim` (port 80 → web :3000, `/api/*` → :8000)

소요시간: 5-15분 (web 빌드 포함).

### 3-2. 자동 검증 (7 단계)

```bash
sudo bash deploy/scripts/sim-verify.sh
```

**기대 출력**

```
1. Telemetry 흐름 (gateway → MQTT → DB)
   ✅ telemetry rows in last 60s: 12
2. Telemetry latest 갱신
   ✅ telemetry_latest rows: 6
3. Heartbeat
   ✅ last_seen_at within 7s
4. Command round-trip
   ✅ command issued: <UUID>
   ✅ command executed (round-trip 성공)
5. Gateway heartbeat → last_seen_at 갱신
   ✅ last_seen_at within 5s
6. nginx → web (Next standalone) 응답
   ✅ nginx serves web at / (HTTP 200)
7. nginx → /api/dashboard proxy 도달
   ✅ /api/dashboard reachable through nginx (HTTP 401)

PASS: 7    FAIL: 0
✅ All wire-level checks PASS — sim 환경 정상 동작 중
```

### 3-3. 수동 UI 검증 (브라우저)

1. **로그인:**
   ```bash
   sudo /opt/iot-sim/bin/sim-fake-jwt
   # 출력 예: eyJhbGciOiJIUzI1NiIs...
   ```
   브라우저 `http://localhost/` → `/login`로 자동 redirect → 토큰 붙여넣기 → "들어가기".

2. **대시보드 확인:**
   - 사이트 selector(우상단) — 게이트웨이 1개라면 `farm-sim-001` 표시
   - 센서 카드 (CO₂ / 온도 / 습도 등) — 5초마다 자동 갱신, 값 변화 관찰
   - 색상: 정상 녹색(#34C759), 주의 주황(#FF9500), 위험 빨강(#FF3B30)
   - 즐겨찾기 토글 — 클릭 시 ON/OFF 전환

3. **MQTT 명령 검증** (별도 터미널):
   ```bash
   mosquitto_sub -h 127.0.0.1 -t 'gw/+/command/+' -v
   ```
   대시보드에서 토글 누르면 `gw/farm-sim-001/command/request` 페이로드 보임.

4. **추세 화면 (24h 차트):**
   `/trends` 또는 대시보드 헤더의 "→ 24h 추세 보기" 클릭 — 온도/습도/CO₂ LineChart.

### 3-4. 모바일 검증

#### Expo Go (가장 빠름)

```bash
pnpm dev:mobile
# QR 코드 → iPhone Camera (or Expo Go 앱) 스캔
```

같은 LAN이어야 함. 다른 네트워크면:
```bash
EXPO_PUBLIC_API_URL=http://<wsl-ip>:8000 pnpm dev:mobile
```

WSL IP 확인:
```bash
ip -4 addr show eth0 | grep inet
```

#### iOS PWA (Safari, 빠른 데모)

1. iPhone Safari에서 `http://<wsl-ip>/` 접속
2. 공유 → "홈 화면에 추가"
3. 앱 아이콘으로 실행 (전체 화면)

## 4. 회귀 시나리오 (수정 시 반드시 통과해야)

| 시나리오 | 명령 | 기대 |
|---|---|---|
| @iot/ui 변경 후 | `pnpm --filter @iot/ui test` | 7/7 PASS |
| @iot/api 변경 후 | `pnpm --filter @iot/api test` | 4/4 PASS |
| backend dashboard 변경 후 | `pytest server/tests/test_dashboard.py` | 4/4 PASS |
| web 변경 후 | `pnpm --filter @iot/web build` | 6 routes, 0 webpack error |
| 어디든 변경 후 (sim 환경) | `bash deploy/scripts/sim-verify.sh` | 7/7 PASS |

## 5. 일반 트러블슈팅

### 빌드: "Module parse failed: 'export type'" (Flow 구문)
- `apps/web/next.config.js`의 webpack alias가 `@react-native/assets-registry/registry` → `apps/web/src/stubs/assets-registry.js`로 redirect 중인지 확인.

### 빌드: "TypeError: ...createContext is not a function"
- `apps/web/package.json`에 `react-native@0.74.5` + `react-native-web@0.19.12` 둘 다 EXACT로 박혀 있는지 확인 (Tamagui SSR이 둘 다 필요).

### 테스트: ActuatorToggle 다중 button 매칭
- 테스트는 `getAllByLabelText('toggle-x')` 사용 — Tamagui Button이 disabled 상태에서 mirror 버튼을 추가 렌더해 같은 aria-label이 2개 등장. 이건 정상.

### 모바일 install: react 18.3.1 vs 18.2.0 충돌
- `apps/mobile/package.json`의 react는 18.2.0 (Expo SDK 51 baseline). 루트 hoist는 18.3.1. peer dep 검사가 strict면 `auto-install-peers=false`(이미 .npmrc 적용)로 우회.

### nginx 502 (`http://localhost/`)
```bash
sudo systemctl status iot-sim-web
sudo journalctl -fu iot-sim-web    # Next 서버 에러
ss -tlnp | grep ':3000'             # 포트 점유 확인
```

### Sim mode JWT 만료
```bash
sudo /opt/iot-sim/bin/sim-fake-jwt   # 새 토큰 발급
# 브라우저 콘솔: localStorage.removeItem('jwt')
# /login으로 다시
```

## 6. CI 권장 매트릭스 (참고)

```yaml
# .github/workflows/ci.yml (예시)
jobs:
  test-js:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v3
        with: { version: 9 }
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: pnpm }
      - run: pnpm install --frozen-lockfile=false
      - run: pnpm test                # api(4) + ui(7) = 11
      - run: pnpm --filter @iot/web build

  test-py:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: cd server && pip install -e ".[dev]"
      - run: cd server && pytest

  sim-verify:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
      - run: sudo bash deploy/scripts/install-sim.sh
      - run: sudo bash deploy/scripts/sim-verify.sh
```

> sim-verify를 CI에 넣으면 빌드 시간이 30분+ → self-hosted runner 권장.
