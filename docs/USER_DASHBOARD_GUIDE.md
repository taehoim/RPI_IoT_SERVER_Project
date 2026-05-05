# 사용자 대시보드 + 모바일 앱 가이드

Apple Home / Google Home 톤의 친숙한 인터페이스로 IoT 게이트웨이를 모니터링하고 액추에이터를 제어합니다.

## 개요

| 채널 | 기술 스택 | 접속 |
|---|---|---|
| 웹 (PWA) | Next.js 14 + Tamagui | `http://<host>/` |
| 모바일 | Expo SDK 51 + Tamagui | Expo Go 또는 build |
| 공통 | `packages/ui` (Tamagui), `packages/api` (TanStack Query) | — |

데이터 흐름: 클라이언트 → `/api/dashboard?gateway_id=...` 5초 폴링 → FastAPI → Postgres `telemetry_latest`.

> SSE/MQTT push는 Phase 2 (cross-process pub/sub + EventSource auth ticket 필요).

## 시작하기 — 시뮬레이션 모드

### 1. 설치

```bash
sudo bash deploy/scripts/install-sim.sh    # 5-15분 (web 빌드 포함)
sudo bash deploy/scripts/sim-verify.sh     # PASS 확인
```

설치 항목:
- PostgreSQL + Mosquitto (loopback)
- FastAPI 백엔드 + 워커 + 스케줄러 + sim 게이트웨이
- Node 20 + pnpm + nginx
- Next.js standalone 빌드 (`/opt/iot-sim/web`)
- systemd unit `iot-sim-web.service`
- nginx → 80번 포트, `/api/*` → 8000, `/` → 3000

### 2. 로그인 (Sim JWT)

```bash
sudo /opt/iot-sim/bin/sim-fake-jwt           # 토큰 출력
```

브라우저에서 `http://localhost/login` → 토큰 붙여넣기 → "들어가기".

### 3. 대시보드 사용

| 영역 | 동작 |
|---|---|
| 사이트 selector (우상단) | 게이트웨이 다중일 때 전환 |
| 센서 카드 | 5초마다 자동 갱신, 색상은 `_classify` 임계치 (ok 녹색 / warn 주황 / danger 빨강) |
| 즐겨찾기 토글 | 액추에이터 ON/OFF (mosquitto에 commands 발행) |
| `→ 24h 추세 보기` | `/trends` 페이지 — Recharts LineChart |

### 4. 모바일 PWA 설치 (iOS Safari)

1. 같은 네트워크에서 `http://<wsl-ip>/` 접속
2. 공유 → "홈 화면에 추가"
3. 앱처럼 실행 (전체 화면)

### 5. 네이티브 모바일 (Expo Go)

```bash
pnpm dev:mobile
# QR 코드를 Expo Go 앱으로 스캔
```

`apps/mobile/_layout.tsx`의 `EXPO_PUBLIC_API_URL` 기본값:
- Android emulator: `http://10.0.2.2:8000`
- iOS simulator: `http://localhost:8000`
- 실 기기: `EXPO_PUBLIC_API_URL=http://<wsl-ip>:8000 pnpm dev:mobile`

JWT는 `expo-secure-store`에 저장 (iOS Keychain / Android EncryptedSharedPreferences).

## 화면 구조

```
apps/web
├── app/page.tsx                       # 토큰 체크 → /login redirect or DashboardScreen
├── app/login/page.tsx                 # JWT 입력
├── app/trends/page.tsx                # 24h 차트
└── app/components/DashboardScreen.tsx # 사이트 + 센서 + 액추에이터

apps/mobile
├── app/_layout.tsx                    # TamaguiProvider + ApiProvider + Stack
├── app/index.tsx                      # → DashboardScreen.native
├── app/login.tsx
├── app/trends.tsx                     # 최근값 카드 리스트 (차트는 web only)
└── app/components/DashboardScreen.native.tsx
```

## 트러블슈팅

### 카드가 비어 있음
- `sudo journalctl -u iot-sim-gateway -n 50` — 게이트웨이 sim이 telemetry 발행 중인지 확인
- `mosquitto_sub -h 127.0.0.1 -t 'gw/+/#' -v` — MQTT 메시지 확인

### "401 Unauthorized" 반복
- JWT 만료 → 다시 발급 (`sudo /opt/iot-sim/bin/sim-fake-jwt`)
- 브라우저 콘솔: `localStorage.removeItem('jwt')` 후 `/login`으로 다시

### nginx 502
- `sudo systemctl status iot-sim-web` — Next 서버 살아있는지
- `sudo journalctl -u iot-sim-web -n 50`
- 포트 점유: `ss -tlnp | grep -E ':(3000|8000)'`

### 모바일에서 "Network request failed"
- `EXPO_PUBLIC_API_URL`이 device에서 도달 가능한 호스트인지 (localhost는 device 자기 자신)
- WSL IP 확인: `ip -4 addr show eth0 | grep inet`

### 빌드 실패 (`@react-native/assets-registry` Flow 구문)
- `apps/web/next.config.js`의 webpack alias가 `@react-native/assets-registry/registry`를 stub으로 redirect 중인지 확인 (`apps/web/src/stubs/assets-registry.js`)

## 구조 결정

- **Polling 5s**: SSE는 cross-process pub/sub (Postgres LISTEN/NOTIFY 또는 MQTT events)와 EventSource auth ticket 흐름이 필요해 Phase 2로 연기. 단일 테넌트 sim 모드에서 폴링 비용은 무시 가능.
- **Tamagui pinned 1.108.4 EXACT**: 캐럿 범위(`^1.108.0`)는 Expo SDK 51의 RN 0.74와 호환되지 않는 버전(1.144+)을 끌어옵니다.
- **react-native-svg stub on web**: `@tamagui/lucide-icons` 트랜지티브 의존성이 SWC가 처리할 수 없는 Flow 구문을 포함. 웹에서는 native asset 등록이 불필요해 no-op stub으로 안전하게 우회.
