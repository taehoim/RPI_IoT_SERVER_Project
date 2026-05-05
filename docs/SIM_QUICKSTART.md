# 시뮬레이션 환경 — 첫 실행 가이드 (7 steps)

처음 sim 환경을 띄우고 대시보드/모바일까지 검증하는 순차 가이드. 단계별 기대 출력 + 실패 시 대응까지.

> 더 깊은 테스트(단위/통합/E2E/CI 매트릭스)는 [TEST_GUIDE.md](./TEST_GUIDE.md) 참조.
> UI 사용법은 [USER_DASHBOARD_GUIDE.md](./USER_DASHBOARD_GUIDE.md) 참조.

---

## STEP 0 — 사전 체크

모두 통과해야 STEP 1 진행 가능.

```bash
# Ubuntu 22.04 / 24.04 (다른 배포는 미지원)
lsb_release -a

# sudo 사용 가능
sudo -v

# 인터넷 (apt + go.dev + npm + pypi 도달)
curl -sI https://go.dev | head -1            # HTTP/2 200

# 포트 비어있음 (80, 3000, 8000, 5432, 1883)
ss -tlnp | grep -E ':(80|3000|8000|5432|1883)\s' || echo "OK: ports free"

# /opt 5GB 이상 여유
df -h /opt
```

---

## STEP 1 — 브랜치 선택

```bash
cd /path/to/IoT_Gateway_Server
git fetch --all

# 안정 — PR #1만 (원본 17-task)
git checkout feat/user-dashboard-mobile-app
git pull origin feat/user-dashboard-mobile-app
```

(선택) PR #2 + #3 + #4까지 통합 머지 시뮬레이션:

```bash
git checkout -b test/all-in feat/user-dashboard-mobile-app
git merge --no-ff origin/fix/dashboard-error-handling
git merge --no-ff origin/refactor/use-gateways-hook
git merge --no-ff origin/test/dashboard-coverage
```

---

## STEP 2 — 설치 (5~15분)

```bash
sudo bash deploy/scripts/install-sim.sh
```

### 정상 진행 출력

```
==> Installing apt packages
==> Creating sim user and directories
==> Configuring mosquitto (loopback only)
==> Configuring PostgreSQL
==> Installing server Python deps
==> Running alembic migrations
==> Seeding sim data
==> Building gateway-agent
==> Installing systemd units
==> Installing Node 20, pnpm, and nginx for web dashboard   ← 5~10분
==> Building web app (apps/web → standalone)                ← 8~16분
==> Configuring nginx
==> Installing JWT helper
✅ Installation complete
```

WSL drvfs 환경은 web build에 16분까지 정상.

### 실패 분기

| 증상 | 조치 |
|---|---|
| `apt-get install nodejs` 실패 | `curl -fsSL https://deb.nodesource.com/setup_20.x \| sudo bash -` 수동 실행 후 재시도 |
| `pnpm install` 무한 대기 | WSL drvfs 느림. 최대 10분 기다림 |
| `next build` Flow syntax 에러 | webpack alias 미적용. `apps/web/next.config.js` + `apps/web/src/stubs/assets-registry.js` 존재 확인 |
| `iot-sim-web` failed | `sudo journalctl -u iot-sim-web -n 30` |

---

## STEP 3 — 자동 검증

```bash
sudo bash deploy/scripts/sim-verify.sh
```

### 기대 출력 (PR #1: 5단계)

```
1. systemd services active                    ✅ (5~7개 service active)
2. MQTT telemetry stream                       ✅
3. PostgreSQL telemetry_latest                 ✅ (rows: 6)
4. Command round-trip                          ✅ executed
5. Gateway heartbeat                           ✅ within 5s

PASS: 5    FAIL: 0
```

### FAIL 시 디버깅

```bash
sudo journalctl -u iot-sim-gateway -n 50 --no-pager
sudo journalctl -u iot-sim-worker  -n 50 --no-pager
sudo journalctl -u iot-sim-backend -n 50 --no-pager
curl -v http://127.0.0.1:8000/health
```

---

## STEP 4 — JWT 발급

```bash
sudo /opt/iot-sim/bin/sim-fake-jwt
```

출력 토큰을 클립보드에 복사:

```
eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJpc3MiOi...
```

---

## STEP 5 — 웹 대시보드 검증

### 5-1. 접속

브라우저 `http://localhost/`

→ JWT 없으면 자동 `/login` redirect.

### 5-2. 로그인

토큰 붙여넣기 → "들어가기" → `/`로 자동 이동.

### 5-3. UI 체크리스트

| 영역 | 기대 |
|---|---|
| 헤더 게이트웨이 이름 | seed 이름 (예: `Test GW`) |
| 사이트 selector | 게이트웨이 1개라면 그대로 표시 |
| "마지막 업데이트" | 5초마다 시간 갱신 |
| 센서 카드 6개 | CO₂ / 온도 / 습도 등, 5초마다 값 변화 |
| 카드 색상 | ok=녹색(#34C759), warn=주황(#FF9500), danger=빨강(#FF3B30) |
| 즐겨찾기 토글 | 클릭 → 색 전환 (파랑↔회색) |
| `→ 24h 추세 보기` 링크 | `/trends` 이동 → LineChart 3개 |

### 5-4. MQTT 명령 검증 (별도 터미널)

```bash
mosquitto_sub -h 127.0.0.1 -t 'gw/+/command/+' -v
```

대시보드 토글 클릭 시:

```
gw/GW-SIMTEST/command/request   {"command_id":"...","action":"ON",...}
gw/GW-SIMTEST/command/response  {"command_id":"...","status":"executed",...}
```

---

## STEP 6 — 모바일 검증 (선택)

### 6-1. iOS PWA — 가장 빠름

WSL IP 확인:

```bash
ip -4 addr show eth0 | grep inet      # 예: 172.20.123.45
```

iPhone (같은 LAN) Safari → `http://172.20.123.45/` → 로그인 → 공유 → "홈 화면에 추가".

### 6-2. Expo Go — 네이티브 RN

```bash
cd /path/to/IoT_Gateway_Server
EXPO_PUBLIC_API_URL=http://172.20.123.45:8000 pnpm dev:mobile
```

Expo Go 앱 → QR 스캔 → 첫 빌드 수 분 → 로그인 → 대시보드.

---

## STEP 7 — 정리

### 유지 (재부팅 후 자동 시작)

별도 명령 불필요.

### 완전 제거

```bash
sudo bash deploy/scripts/uninstall-sim.sh
```

제거: systemd unit 5개, nginx config, `/opt/iot-sim/`, `/etc/iot-sim/`, `/var/lib/iot-sim/`, `/var/log/iot-sim/`, DB `iot_sim`, user `iotsim`.

---

## 한눈에 보기

```
[0] 사전 체크 (Ubuntu, sudo, 인터넷, 포트, 디스크)
[1] git checkout feat/user-dashboard-mobile-app
[2] sudo bash deploy/scripts/install-sim.sh         (5~15분)
[3] sudo bash deploy/scripts/sim-verify.sh           (5/5 PASS)
[4] sudo /opt/iot-sim/bin/sim-fake-jwt               (토큰 복사)
[5] 브라우저 http://localhost/login → 토큰 → 대시보드
[6] (선택) iPhone PWA / Expo Go
[7] (선택) sudo bash deploy/scripts/uninstall-sim.sh
```
