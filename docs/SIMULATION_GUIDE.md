# Simulation Mode 설치 + 운영 가이드

> 작성일: 2026-05-04
> 대상: 라즈베리파이/CM4 + 실 센서 없이 IoT Gateway Server 전체 wire 흐름을 단일 호스트에서 검증하려는 개발자/QA
> 소요: 설치 5–10분, 검증 1분
> 환경: Ubuntu 22.04 또는 24.04 (sudo 가능, 외부 인터넷)

---

## 1. 무엇을 검증하는가

이 가이드는 **하드웨어 없이** 다음 wire 경로 전체를 한 머신 위에서 돌립니다.

```
┌──────────────────────────────────────────────────────────────────┐
│  하나의 Ubuntu 호스트 (예: 4 CPU / 4GB RAM / 20GB)                │
│                                                                  │
│  ┌─────────────┐   MQTT     ┌────────────┐    DB    ┌──────────┐ │
│  │ gateway-    │  publish   │            │  INSERT  │          │ │
│  │ agent-sim   │ ─────────▶ │  mosquitto │ ────────▶│Postgres  │ │
│  │             │ ◀───────── │  (loopback │  worker  │          │ │
│  │ - sensor:   │  command   │   :1883)   │          │          │ │
│  │   합성 sine │            │            │          │          │ │
│  │ - actuator: │            └────────────┘          └──────────┘ │
│  │   GPIO 우회 │                  ▲                       ▲     │
│  │ - heartbeat │                  │ subscribe              │     │
│  │             │                  │                       │     │
│  └─────────────┘            ┌─────┴──────┐  publish/      │     │
│         ▲                   │  iot-sim-  │  query         │     │
│         │ command           │  worker    │ ──────────────▶│     │
│         │                   │            │                │     │
│         │              ┌────┴───────┐  ┌─┴───────────┐    │     │
│         └──────────────│iot-sim-    │  │iot-sim-     │    │     │
│         (REST API +    │backend     │  │scheduler    │────┘     │
│          MQTT publish) │(FastAPI    │  │(periodic)   │          │
│                        │ uvicorn)   │  │             │          │
│                        └────────────┘  └─────────────┘          │
└──────────────────────────────────────────────────────────────────┘
                ▲
                │ curl (unsigned JWT)
            사용자 (검증)
```

**확인되는 것:**

- Gateway → Server: telemetry / state / heartbeat / command response (4 종 토픽)
- Server → Gateway: command request (REST API → MQTT publish)
- DB: telemetry 적재, telemetry_latest 갱신, gateway.last_seen_at 갱신, commands status 변환
- Wire 정합성: gateway 슬러그(`GW-SIMTEST`, `env-1`, `relay-vent`) → server UUID 변환
- systemd watchdog: 모든 서비스 sd_notify
- 명령 만료 / idempotency / safe-state 등 안전 분기 (단위 테스트로 보강)

**확인되지 않는 것 (의도적 제외):**

- 실 GPIO/RS485 동작 — Pi/CM4 + 센서 + 릴레이 모듈 필요
- Keycloak 통합 — `KC_VERIFY_SIGNATURE=false` + unsigned JWT로 우회
- VerneMQ — mosquitto loopback only
- TLS — Phase 7 항목, sim에서는 plain
- /dev/watchdog — sim에서는 비활성화 (systemd watchdog만 사용)

---

## 2. 사전 요구사항

| 항목 | 최소 | 권장 |
|---|---|---|
| OS | Ubuntu 22.04 | Ubuntu 24.04 |
| CPU | 2 core | 4 core |
| RAM | 2 GB | 4 GB |
| Disk | 5 GB | 20 GB |
| 권한 | sudo | sudo |
| 네트워크 | 설치 시점에만 외부 (apt/go.dev/pypi) | 동일 |

설치 후 운영 단계에서는 외부 네트워크 불필요 (모든 컴포넌트 loopback).

다음 포트를 점유합니다:
- `127.0.0.1:1883` — mosquitto MQTT
- `127.0.0.1:5432` — PostgreSQL
- `0.0.0.0:8000` — FastAPI backend (변경 시 backend 환경변수 수정)

---

## 3. 설치 (한 번에)

```bash
git clone <YOUR_REPO_URL> IoT_Gateway_Server
cd IoT_Gateway_Server
sudo bash deploy/scripts/install-sim.sh
```

설치 진행 단계 (스크립트 출력으로 표시됨):

1. apt 의존성 (mosquitto, postgresql, python3-venv, build-essential, golang)
2. `iotsim` 시스템 사용자 + 디렉터리 (`/opt/iot-sim`, `/etc/iot-sim`, `/var/lib/iot-sim`, `/var/log/iot-sim`)
3. mosquitto loopback listener 설정
4. PostgreSQL DB(`iot_sim`) + user(`iot_sim`) 생성, 무작위 password 발급
5. Python venv + server pyproject 설치
6. alembic upgrade (migration 0001 + 0002 적용)
7. seed: 1 company / 1 site / 1 admin user / 1 gateway / 1 sensor profile / 1 sensor channel(`env-1`) / 2 actuator channel(`relay-vent`, `relay-spray`)
8. Go gateway-agent 빌드 (`-tags simulation`, no cgo, libgw_hal.so 불필요)
9. systemd unit 4개 (backend, worker, scheduler, gateway-sim) 등록 + 시작
10. JWT 헬퍼 스크립트 설치 (`/opt/iot-sim/bin/sim-fake-jwt`)

**재설치 (DB 초기화 포함):**

```bash
sudo bash deploy/scripts/install-sim.sh --reset
```

기존 DB는 drop, password 재발급, 모든 시드 재생성.

---

## 4. 자동 검증

설치 직후 5단계 wire 검증을 한 번에:

```bash
sudo bash deploy/scripts/sim-verify.sh
```

**기대 출력:**

```
------ 1. systemd services active ------
  ✅ postgresql: active
  ✅ mosquitto: active
  ✅ iot-sim-backend: active
  ✅ iot-sim-worker: active
  ✅ iot-sim-scheduler: active
  ✅ iot-sim-gateway: active

------ 2. MQTT telemetry stream (max 12s wait) ------
  ✅ telemetry received: gw/GW-SIMTEST/telemetry {"message_id":"...","gateway_id":"GW-SIMTEST"...

------ 3. PostgreSQL telemetry_latest ------
  ✅ telemetry_latest rows: 6

------ 4. Command round-trip (relay-vent ON) ------
  ✅ command issued: cmd-20260504-...
  ✅ command executed (round-trip 성공)

------ 5. Gateway heartbeat → last_seen_at 갱신 ------
  ✅ last_seen_at within 7s

==================================================
  PASS: 11    FAIL: 0
==================================================

✅ All wire-level checks PASS — sim 환경 정상 동작 중
```

FAIL이 발생하면 § 8 트러블슈팅 참조.

---

## 5. 수동 사용 — 흔한 시나리오

### 5.1 실시간 telemetry 관찰

```bash
mosquitto_sub -h 127.0.0.1 -t 'gw/+/#' -v
```

5초마다 telemetry payload + 10초마다 heartbeat가 흐릅니다.

### 5.2 JWT 발급

API 호출은 `Authorization: Bearer <token>` 헤더 필요. Sim 모드는 unsigned JWT (`alg=none`) 사용:

```bash
TOKEN=$(sudo /opt/iot-sim/bin/sim-fake-jwt)
echo "$TOKEN"
# eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJpc3MiOi...
```

이 토큰은 `sub=sim-admin`, role `system_admin` + `company_admin` 포함, 1시간 유효.

### 5.3 Gateway / 채널 UUID 조회

```bash
TOKEN=$(sudo /opt/iot-sim/bin/sim-fake-jwt)
# Gateway 목록
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/gateways | jq
# Actuator 채널 (gateway UUID 필요)
GW_UUID=$(curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/gateways | jq -r '.[0].id')
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/gateways/$GW_UUID/actuator-channels | jq
```

### 5.4 Telemetry 최신값 조회

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8000/api/gateways/$GW_UUID/telemetry/latest" | jq
```

응답 예:
```json
[
  {"sensor_channel_id": "...", "measurement_key": "temperature", "ts": "2026-05-04T...",
   "value_double": 22.4, "unit": "degC", "quality": "good"},
  {"sensor_channel_id": "...", "measurement_key": "humidity", "value_double": 58.2, ...},
  ...
]
```

### 5.5 Command 발행 → relay 동작 확인

```bash
ACT_UUID=$(curl -s -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8000/api/gateways/$GW_UUID/actuator-channels | jq -r '.[] | select(.slug=="relay-vent") | .id')

# 환기팬 ON
CMD=$(curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"actuator_channel_id\":\"$ACT_UUID\",\"action\":\"ON\",\"expires_in_sec\":30}" \
  http://127.0.0.1:8000/api/gateways/$GW_UUID/commands)
echo "$CMD" | jq

CMD_ID=$(echo "$CMD" | jq -r .id)

# 1-3초 후 상태 조회 — gateway sim이 응답하면 status=executed
sleep 3
curl -s -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/api/commands/$CMD_ID" | jq '.status, .response.local_safety_check'
# "executed"
# "passed"
```

### 5.6 만료 명령 거부 검증

`expires_in_sec=0` (또는 즉시 만료):

```bash
# expires가 즉시 지난 명령
CMD=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"actuator_channel_id\":\"$ACT_UUID\",\"action\":\"ON\",\"expires_in_sec\":0}" \
  http://127.0.0.1:8000/api/gateways/$GW_UUID/commands)
sleep 2
CMD_ID=$(echo "$CMD" | jq -r .id)
curl -s -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/api/commands/$CMD_ID" \
  | jq '.status, .response.local_safety_check'
# "rejected"
# "rejected_expired"
```

---

## 6. 무엇이 어디에 있는가 (file map)

| 경로 | 내용 |
|---|---|
| `/opt/iot-sim/bin/gateway-agent-sim` | Gateway Go 바이너리 (-tags simulation) |
| `/opt/iot-sim/bin/sim-fake-jwt` | JWT 발급 헬퍼 |
| `/opt/iot-sim/server-venv/bin/iot-{backend,worker,scheduler}` | Python entry point |
| `/opt/iot-sim/share/profiles/sim-env-6in1.json` | Sensor profile (livestock 6-in-1 변형) |
| `/etc/iot-sim/server.env` | DB / MQTT / Keycloak (mock) 설정 |
| `/etc/iot-sim/gateway.yaml` | Gateway YAML (simulation: enabled) |
| `/var/lib/iot-sim/local.db` | Gateway 측 SQLite 오프라인 큐 |
| `/var/log/iot-sim/` | (logrotate config 별도) |
| `/etc/systemd/system/iot-sim-*.service` | 4개 systemd unit |

PostgreSQL 데이터: `/var/lib/postgresql/16/main/` (apt postgresql-16 기준). 직접 접근:
```bash
PG_PASS=$(sudo grep DATABASE_URL /etc/iot-sim/server.env | sed 's|.*://[^:]*:\([^@]*\)@.*|\1|')
PGPASSWORD="$PG_PASS" psql -h 127.0.0.1 -U iot_sim -d iot_sim
```

---

## 7. systemd 서비스 운영

### 상태 확인

```bash
systemctl status iot-sim-backend iot-sim-worker iot-sim-scheduler iot-sim-gateway
```

### 로그 follow

```bash
sudo journalctl -fu iot-sim-gateway      # gateway agent
sudo journalctl -fu iot-sim-worker       # MQTT subscriber
sudo journalctl -fu iot-sim-backend      # FastAPI
sudo journalctl -fu iot-sim-scheduler    # periodic jobs
```

### 재시작

```bash
sudo systemctl restart iot-sim-gateway
```

### 시뮬레이션 패턴 변경

`/etc/iot-sim/gateway.yaml`의 `simulation` 섹션 수정 후 gateway만 재시작:

```yaml
simulation:
  enabled: true
  pattern: random_walk    # sine | random_walk | fixed
  jitter_percent: 5.0
  seed: 42                # 0=시간 기반, 양수=재현 가능
```

```bash
sudo systemctl restart iot-sim-gateway
```

### 폴링 간격 변경

`/etc/iot-sim/gateway.yaml`의 `sensors[].polling_interval_sec` 수정 (예: 1초로 단축하여 부하 테스트):

```yaml
sensors:
  - channel_id: env-1
    polling_interval_sec: 1
    ...
```

10초 안에 broker가 60+ 메시지 받음 → worker dispatch 처리량 검증.

---

## 8. 트러블슈팅

### 8.1 `iot-sim-backend` 30초 후 재시작 루프

증상: `journalctl -u iot-sim-backend` 에 `Watchdog timeout` 반복.

원인: `sd_notify` 미동작 — 일반적으로 `sdnotify` Python 패키지 누락.

해결:
```bash
sudo /opt/iot-sim/server-venv/bin/pip install sdnotify
sudo systemctl restart iot-sim-backend
```

### 8.2 `mosquitto_sub`에 telemetry가 안 보임

확인 순서:
1. `systemctl is-active iot-sim-gateway` → active 인가?
2. `sudo journalctl -u iot-sim-gateway --since '1 min ago' | grep -i error`
3. `mosquitto_sub -h 127.0.0.1 -t '$SYS/broker/clients/connected' -C 1` → 1 이상이어야 함 (gateway connected)
4. broker가 다른 포트에서 listen하지는 않는지: `ss -tlnp | grep 1883`

### 8.3 `telemetry_latest` 가 비어 있음 (verify step 3 FAIL)

증상: gateway가 publish는 하나 server worker가 INSERT 안 함.

원인 후보:
- Worker가 죽음 → `journalctl -u iot-sim-worker | tail -20`
- Sensor channel slug 불일치 → DB 확인:
  ```bash
  PGPASSWORD="$PG_PASS" psql -h 127.0.0.1 -U iot_sim -d iot_sim \
    -c "SELECT slug FROM sensor_channels;"
  # env-1 행이 있어야 함
  ```
- Gateway YAML의 `sensors[].channel_id` 가 `env-1`인지 확인.

### 8.4 Command가 영원히 `published` 상태

증상: 명령 발행 후 status가 `executed`로 안 바뀜.

원인 후보:
- gateway가 broker 연결 실패 → `journalctl -u iot-sim-gateway | grep -i mqtt`
- worker subscribe가 잘못된 wildcard → `journalctl -u iot-sim-worker | grep subscribed`
  → `subscribed gw/+/#` 가 보여야 함 (4-segment 매칭).
- actuator slug `relay-vent`가 gateway YAML에 없음.

### 8.5 401 Unauthorized

`KC_VERIFY_SIGNATURE=false`인지 확인:
```bash
sudo grep KC_VERIFY /etc/iot-sim/server.env
# KC_VERIFY_SIGNATURE=false
```

값이 다르면 수정 후 `sudo systemctl restart iot-sim-backend`.

### 8.6 사용자가 새 gateway/channel을 추가하고 싶다

REST API로 추가:

```bash
TOKEN=$(sudo /opt/iot-sim/bin/sim-fake-jwt)
COMPANY_ID=$(curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/companies | jq -r '.[0].id')

# 새 gateway
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"serial_number\":\"GW-SIM02\",\"name\":\"Sim 02\",\"company_id\":\"$COMPANY_ID\"}" \
  http://127.0.0.1:8000/api/gateways | jq
```

토픽 형식 `gw/{serial_number}/...` 이므로 `serial_number`는 `^[A-Za-z0-9_-]+$` 범위 + 64자 제한.

채널 slug도 동일 패턴. 새 sensor channel:
```bash
NEW_GW_UUID=$(...)
PROFILE_UUID=$(curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/sensor-profiles | jq -r '.[0].id')

curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"slug\":\"env-2\",\"sensor_profile_id\":\"$PROFILE_UUID\",\"display_name\":\"센서2\",\"interface_name\":\"/dev/null\",\"protocol\":\"modbus_rtu\",\"slave_id\":2}" \
  http://127.0.0.1:8000/api/gateways/$NEW_GW_UUID/sensor-channels
```

---

## 9. 제거

```bash
sudo bash deploy/scripts/uninstall-sim.sh
```

수행: systemd unit 제거, mosquitto sim listener 제거, PostgreSQL DB/user drop, `/opt/iot-sim` 등 삭제, `iotsim` user 삭제.

PostgreSQL/mosquitto 패키지 자체는 남깁니다 (다른 용도 가능). 완전 제거는:
```bash
sudo apt-get purge -y mosquitto mosquitto-clients postgresql postgresql-contrib
```

---

## 10. Sim ↔ 실 운영 차이점 (이행 시 주의)

| 항목 | Sim 모드 | 실 운영 (Phase 1+) |
|---|---|---|
| Hardware | 없음 | Pi 4 / CM4 / R1124 |
| HAL | noop (`-tags simulation`) | cgo + libgw_hal.so |
| Sensor 데이터 | 합성 (sine/random_walk) | RS485 Modbus RTU |
| Actuator GPIO | log only | libgpiod 실 동작 |
| Kernel WDT | 비활성 | `/dev/watchdog` 활성 |
| Broker | mosquitto loopback anonymous | VerneMQ + password file + (Phase 7) TLS |
| Auth | Unsigned JWT | Keycloak RS256 발급 + JWKS verify |
| 사용자 추가 | seed 자동 | Keycloak admin UI + DB sync (`add-user.sh` 별도 — REVIEW C3 권고) |

실 운영 전환은 Phase 0 → Phase 1 install (`deploy/scripts/install-pi4.sh` + Phase 1 server install) 사용. 본 sim 환경은 그 이전에 wire schema 정합성을 검증하는 용도로 설계.

---

## 11. 추가 참고

- `docs/reviews/00_OVERVIEW.md` — 전체 구현 통합 점검 보고서 (109 finding, fix 진행 상태)
- `docs/HAL_ABI.md` — HAL ABI 명세 (sim 모드도 동일 ABI 준수)
- `docs/PHASE0_RUNBOOK.md` — 실 Pi 운영 절차 (sim 후 다음 단계)
- `cm4_iot_gateway_no_docker_detailed_implementation_plan.md` — 41 섹션 마스터 계획서

---

## 12. 변경 이력

| 날짜 | 변경 |
|---|---|
| 2026-05-04 | 초판 — sim 모드 추가 + 단일 호스트 install/verify/uninstall 스크립트 + 본 가이드 |
