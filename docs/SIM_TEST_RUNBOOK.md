# sim 환경 테스트 런북

end-to-end 검증된 절차. 첫 설치 가이드는 [SIM_QUICKSTART.md](./SIM_QUICKSTART.md), 깊은 단위/회귀 테스트는 [TEST_GUIDE.md](./TEST_GUIDE.md). 이 문서는 **재현 가능한 sim 환경 테스트 1회 사이클**.

## TL;DR

```bash
# 한 번만 (WSL 사용자 필수)
rsync -a --exclude=node_modules --exclude=.next \
  /mnt/d/20_claude/IoT_Gateway_Server/ ~/IoT_Gateway_Server/
cp -r /mnt/d/20_claude/IoT_Gateway_Server/.git ~/IoT_Gateway_Server/
sudo chmod 755 /home/$USER

# 매번
cd ~/IoT_Gateway_Server && git pull && \
  sudo bash deploy/scripts/install-sim.sh && \
  sudo bash deploy/scripts/sim-verify.sh

# 토큰 + 브라우저
sudo /opt/iot-sim/bin/sim-fake-jwt | tr -d '\n' | clip.exe   # WSL → Win clipboard
# http://localhost/login → paste → 대시보드
```

---

## 1. 사전 준비 (1회)

### WSL에서 작업 시 — 워크스페이스 위치 강제

`/mnt/c`, `/mnt/d` 같은 Windows 마운트 경로는 **사용 불가**. drvfs는 root의 atomic rename도 막아 pnpm install이 `EACCES`로 실패. install-sim.sh가 자동 감지해 중단.

```bash
# Windows 작업 트리 → WSL 네이티브로 복사
mkdir -p ~/IoT_Gateway_Server
rsync -a \
  --exclude=node_modules --exclude=.next --exclude=.expo --exclude=.tamagui \
  /mnt/d/20_claude/IoT_Gateway_Server/ ~/IoT_Gateway_Server/
cp -r /mnt/d/20_claude/IoT_Gateway_Server/.git ~/IoT_Gateway_Server/
```

### 사용자 홈 권한

`iotsim` 시스템 user가 `~/IoT_Gateway_Server`로 들어가려면 `/home/$USER`가 traverse 가능해야 함. install-sim.sh가 자동 감지 + 수정하지만 미리 풀어두면 안전:

```bash
sudo chmod 755 /home/$USER
```

---

## 2. 설치 사이클 (코드 변경 시마다)

```bash
cd ~/IoT_Gateway_Server

# 최신 변경 가져오기 (사용 중인 브랜치)
git pull

# 이전 빌드 캐시 제거 (Tamagui static extractor가 stale 캐시에 민감)
sudo rm -rf apps/web/.next apps/web/.tamagui apps/web/public/tamagui.css

# 설치 — DB/services는 idempotent로 skip하고 web만 재빌드 (~5-10분)
sudo bash deploy/scripts/install-sim.sh
```

### 정상 종료 표시

```
✅ Installation complete

Services:
  postgresql: active
  mosquitto: active
  nginx: active
  iot-sim-backend: active
  iot-sim-worker: active
  iot-sim-scheduler: active
  iot-sim-gateway: active
  iot-sim-web: active     ← 핵심
```

`iot-sim-web` 가 `activating` 또는 `failed` 면 → 트러블슈팅 표 참조.

---

## 3. 자동 검증 (시스템 레벨, 13/13 PASS 기대)

```bash
sudo bash ~/IoT_Gateway_Server/deploy/scripts/sim-verify.sh
```

| # | 단계 | 검증 |
|---|---|---|
| 1 | systemd services | 7개 모두 active |
| 2 | MQTT telemetry | gateway sim → mosquitto |
| 3 | telemetry_latest | worker → DB |
| 4 | Command round-trip | API → MQTT → gateway → DB executed |
| 5 | Heartbeat | gateways.last_seen_at 30초 내 |
| 6 | nginx → web | port 80 → 200 |
| 7 | nginx → /api | /api/dashboard 401 (auth required = 도달) |

`PASS: 13   FAIL: 0` 면 wire 흐름 OK.

---

## 4. 수동 UI 검증 (브라우저)

### 4-1. 토큰 발급

```bash
# WSL에서 한 번에 클립보드까지 (Windows clip.exe)
sudo /opt/iot-sim/bin/sim-fake-jwt | tr -d '\n' | clip.exe

# 또는 그냥 출력
sudo /opt/iot-sim/bin/sim-fake-jwt
```

### 4-2. 로그인

브라우저 → `http://localhost/`
→ `/login`으로 자동 이동 → textarea에 토큰 paste → "들어가기"

### 4-3. 대시보드 체크리스트

| 영역 | 기대 |
|---|---|
| 헤더 게이트웨이 이름 | `Sim Gateway 01` 또는 `GW-SIMTEST` |
| 마지막 업데이트 시간 | 5초마다 갱신 |
| 센서 카드 6개 | CO₂ / 온도 / 습도 / 등, 값 5초마다 변화 |
| 카드 색상 | ok=녹색, warn=주황, danger=빨강, unknown=회색 |
| 액추에이터 토글 2개 | 클릭 시 색 전환, 약 2초 내 응답 |
| `→ 24h 추세 보기` | `/trends` 이동 → LineChart 3개 |

### 4-4. MQTT 명령 검증 (별도 터미널, 선택)

```bash
mosquitto_sub -h 127.0.0.1 -t 'gw/+/command/+' -v
```

대시보드에서 토글 클릭 시 즉시 출력:
```
gw/GW-SIMTEST/command/request   {"command_id":"...","action":"ON",...}
gw/GW-SIMTEST/command/response  {"command_id":"...","status":"executed",...}
```

---

## 5. 트러블슈팅 (이번 세션에서 발견 + 해결)

| 증상 | 원인 | 해결 |
|---|---|---|
| `EACCES: rename` (pnpm install) | WSL drvfs (`/mnt/*`) | 워크스페이스를 `~/`로 이동 |
| `go: no modules specified` | iotsim user가 `/home/$USER` 진입 불가 | `sudo chmod 755 /home/$USER` |
| `Cannot read 'settings'` (SSR) | Tamagui module duplication | packages/ui peer deps (PR #5) |
| `simpleHash undefined.length` (build) | tamagui.config themes에 raw string | themes override 제거 (PR #5) |
| `_next/static/chunks/*` 404 | install-sim cp 경로가 monorepo nesting 무시 | install-sim 수정 (PR #5) |
| systemd `iot-sim-web` 시작 실패 | WorkingDirectory가 nested 경로와 불일치 | systemd unit 수정 (PR #5) |
| `Failed to fetch` (브라우저 console) | cross-origin (`localhost:80` ↔ `127.0.0.1:8000`) | providers default `baseUrl: ''` (PR #5) |
| 들어가기 클릭해도 토큰 입력 안 됨 | password input + paste 문제 | textarea + ref 사용 (PR #5) |

모든 fix는 [PR #5](https://github.com/taehoim/RPI_IoT_SERVER_Project/pull/5).

---

## 6. 디버그 명령 모음

```bash
# 서비스 상태
sudo systemctl status iot-sim-web --no-pager | head -15

# Next 서버 로그
sudo journalctl -u iot-sim-web -n 50 --no-pager

# 백엔드 API 직접 호출
TOKEN=$(sudo /opt/iot-sim/bin/sim-fake-jwt | tr -d '\n')
curl -sH "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/gateways | jq

# 대시보드 응답 (gateway UUID 필요)
GW=$(PGPASSWORD=$(grep -oP '(?<=:)[^@]+(?=@)' /etc/iot-sim/server.env) psql -h 127.0.0.1 -U iot_sim -d iot_sim -tAc \
    "SELECT id FROM gateways WHERE serial_number='GW-SIMTEST';" | tr -d ' ')
curl -sH "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/api/dashboard?gateway_id=$GW" | jq

# 포트 점유 확인
sudo ss -tlnp | grep -E ':(80|3000|8000)\s'

# Static asset 직접 서빙 확인
ls /opt/iot-sim/web/apps/web/.next/static/chunks/ | head -3
curl -sI http://127.0.0.1:3000/_next/static/chunks/$(ls /opt/iot-sim/web/apps/web/.next/static/chunks/ | grep webpack | head -1) | head -3

# nginx config 검증
sudo nginx -t
```

---

## 7. 정리

### DB 유지 (재부팅 후 자동 시작)
별도 명령 불필요.

### DB 초기화 + 재설치
```bash
sudo bash ~/IoT_Gateway_Server/deploy/scripts/install-sim.sh --reset
```

### 완전 제거
```bash
sudo bash ~/IoT_Gateway_Server/deploy/scripts/uninstall-sim.sh
```
