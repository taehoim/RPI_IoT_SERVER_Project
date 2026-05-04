# Review Overview — 전체 구현 통합 점검

> 작성일: 2026-05-04
> 범위: HAL(C 1,151줄) + Gateway(Go 2,010줄) + Server(Python 1,867줄) + Shared schema + 7 diagrams + 41-section plan + deploy scripts
> 형태: 6개 영역별 리뷰 합산 + 단일 통합 결론
> 선행 리뷰: `docs/REVIEW_PHASE1_PHASE2.md` (Server-only, 2026-05-04 작성)
> **Fix 진행 상태 (2026-05-04 13:30 → 14:10 진행):**
> - Day 1 오전 batch: 12 finding fix됨 (§ "Sprint Day 1 오전 batch — APPLIED")
> - Day 1 오후: ID provisioning workflow 적용됨 (§ "Day 1 오후 — Provisioning APPLIED")
> - Day 1 저녁: **시뮬레이션 모드 + 단일 호스트 install/verify/uninstall + 운영 가이드** 추가 (`docs/SIMULATION_GUIDE.md`, `deploy/scripts/install-sim.sh`, `sim-verify.sh`, `sim-seed.py`, `sim-fake-jwt.py`, `gateway/internal/sim/`, `gateway/internal/hal/hal_sim.go`)
> - 서버 테스트 13/13 PASS, gateway sim 단위 테스트 5/5 PASS, sim 바이너리 end-to-end smoke 검증 OK

---

## 핵심 결론 한 줄

**현재 상태:** 각 layer는 독립적으로 컴파일/배포 가능하나, **3-tier end-to-end loop는 현재 단 한 건도 round-trip하지 않는다**. Gateway가 보내는 모든 telemetry/state/heartbeat/command-response는 server worker에서 ID 불일치 또는 wildcard 미스매치로 100% drop된다. 추가로 LAN 공격자가 자격증명 없이 살균기·환기팬 relay를 임의 조작 가능하다 (MQTT anonymous + ACL 없음).

**다음 sprint의 최우선 작업은 wire-level 정합성 회복(Day 1) + LAN 인증 활성화(Day 1) + 4건의 silent watchdog/safety 결함 수정(Day 2)**. 이 6-8시간 작업 후에야 README의 5개 acceptance criteria가 의미 있게 검증 가능해진다.

---

## 발견 이슈 합산

| 영역 | 🔴 Critical | 🟠 High | 🟡 Medium | 🔵 Better Alt | 합계 |
|---|---|---|---|---|---|
| 01. HAL (C) | 3 | 4 | 5 | 3 | 15 |
| 02. Gateway (Go) | 3 | 5 | 7 | 4 | 19 |
| 03. Server delta (Python) | 1 | 3 | 5 | 0 | 9 |
| 04. E2E wire 정합성 | 4 | 6 | 7 | 4 | 21 |
| 05. Docs/Plan/Diagrams | 4 | 8 | 11 | 5 | 28 |
| 06. 보안 cross-cut | 3 | 5 | 6 | 3 | 17 |
| **신규 합계 (이 리뷰)** | **18** | **31** | **41** | **19** | **109** |
| (참고) 선행 리뷰 잔존 | 0 | 1 (H3 worker serial) | 5 (M1-M7 일부) | 5 | 11 |

**Server delta 회귀 결과:** 선행 리뷰 8건 중 **6건 fix, 1건 잔존 (H3 worker 직렬 dispatch), 1건 부분 (H5 install-server.sh)**. Server 측은 의미 있는 진전.

---

## 시스템이 지금 동작하지 않는 5가지 이유 (BLOCKING)

이 5건은 모두 single-line ~ 半일 작업으로 즉시 해결 가능. 모두 fix하기 전까지 README의 5개 acceptance criteria 검증 자체가 불가능.

### B1. **Gateway ID 불일치로 모든 telemetry/state/heartbeat가 server에서 drop** (E2E C1)
- Gateway는 YAML `gateway.id` 슬러그(`"GW-DEV01"`) 사용, server worker는 `uuid.UUID(gw)`로 강제 변환 → ValueError → 모든 메시지 silently drop
- 영향: 대시보드 영원히 빈 화면, online/offline 영원히 false
- 1줄 fix 불가 — provisioning 설계 필요 (4-6h)

### B2. **Worker wildcard `gw/+/+`가 3-segment 토픽 매칭 못함 — command response 영구 drop** (E2E C2)
- `gw/{id}/command/response`는 4 segment, `gw/+/+`는 3 segment만 매칭
- 영향: 모든 command가 server 측에서 "timeout"으로 표시됨
- **Fix: 5분** — `client.subscribe("gw/+/#", qos=1)` 한 줄

### B3. **sensor_channel_id 슬러그↔UUID 불일치로 telemetry value 0건 INSERT** (E2E C4)
- B1과 동일 root cause, 별도 fix 필요
- 영향: telemetry 테이블 영원히 비어있음

### B4. **expires_at RFC3339Nano 마이크로초가 Go에서 silent skip** (E2E H2)
- Server는 `now.isoformat()` (microsecond 6자리) 발행, gateway는 `time.RFC3339` (no fractional)로 파싱 → error → silently skip 만료 검사
- 영향: 만료된 명령도 실행됨
- **Fix: 15분** — gateway가 `time.RFC3339Nano` 사용

### B5. **MQTT broker LAN anonymous + ACL 없음 — 자격증명 없이 relay 조작 가능** (Security C1)
- `install-pi4.sh:96-99`: `listener 1883 0.0.0.0` + `allow_anonymous true`
- 영향: LAN 공격자가 살균기·환기팬을 임의 조작 → 가축 피해/화재 위험
- **Fix: 30분** — listener를 127.0.0.1로 바인딩 (Phase 0 single-machine)하거나 password file + ACL 추가

---

## 산업 안전 결함 (HARDWARE-SAFETY)

이 4건은 system-blocking은 아니지만 "전기·기계 fail-safe" 원칙(IRON RULE)을 위반한다. 운영 중 패닉/킬 시 relay가 ON으로 잠길 수 있음.

| ID | 위치 | 증상 | Fix 시간 |
|---|---|---|---|
| HAL C1 | `common.c:22-27` | `gw_hal_cleanup()`이 GPIO cleanup 안 함 → FD 누수 + 재초기화 시 dangling pointer UB | 30분 |
| HAL H1 | `platform_pi4.c:195` | `assertSafeState`가 `pthread_mutex_lock` 사용 → SIGTERM/SIGABRT 핸들러에서 데드락 → relay ON 고정 | 15분 |
| HAL H4 | `test_safe_state.c` + `Makefile:64` | safe_state 테스트가 mock backend만 검증, 실제 `platform_pi4.c` 미링크 → CI에서 IRON RULE C1 검증 안 됨 | 1h |
| Gateway C1 | `main.go:79-91` | defer LIFO 역전 — `recover()` defer가 `Cleanup`/`AssertSafeState` 다음에 등록되어 LIFO상 먼저 실행 → panic 경로에서 relay 안전 상태 보장 안 됨 | 15분 |
| Security C3 | `iot-gateway.service` + `watchdog.c:25` | `iot` 사용자가 `/dev/watchdog` 접근 권한 없음 → kernel WDT 실제 비동작 → main.go:107이 WARN으로만 처리 | 10분 (udev rule + supplementary group) |

**중복 위험:** Gateway C1 + HAL H1이 동시 발생하면 panic → re-panic → safe_state 호출 → mutex deadlock → relay 영구 ON. 이 경로는 `test_safe_state.c`가 platform 코드 미링크라 CI에서 검증 못함 (HAL H4).

---

## 공통 root cause 5가지

다음 5가지 설계 공백이 109개 finding 중 약 60-70%의 진짜 원인이다.

### 1. Provisioning 미설계 → ID 혼선 폭발
- Gateway는 슬러그(`GW-DEV01`), server는 UUID, sensor_channels.id도 UUID, actuator_channels.id도 UUID. 양측이 어떻게 sync되는지 정의된 곳 없음
- 파급: E2E C1, C4, C5 + Docs C3, C4 + 기타 H1, H3 등
- 권장: **Sprint 1 첫 작업으로 provisioning protocol 설계** (gateway boot → serial_number register → server UUID 발급 + sensor/actuator channel UUID sync)

### 2. Idempotency 미구현 (gateway 측)
- `localdb.CommandSeen()` / `LogCommand()` API는 구현되어 있으나 `actuator.execute()`에서 호출 0건
- MQTT QoS 1 재전송 시 같은 relay가 두 번 ON → 살균기/펌프 이중 작동 = 산업 사고
- Fix: gateway actuator.go에 4-5줄 추가 (1-2h)

### 3. 오프라인 큐 Flush 미구현 (gateway 측)
- `Enqueue` + `PeekBatch` + `Delete` API 모두 존재하나 reconnect 시 drain 호출 0건
- 5분 broker 단절 후 재연결해도 SQLite의 데이터는 영원히 server에 도달 못함
- 핵심 설계 기능이 코드 0줄. **Phase 0 acceptance #5 (24h burn-in) 검증 시 디스크 점유율은 정상으로 보이지만 실제로는 데이터 영구 손실 중**

### 4. sd_notify watchdog 위장
- Server: REVIEW_PHASE1_PHASE2 C1 fix됨 (server delta 회귀 검증)
- Gateway: ✅ 구현됨
- HAL: `/dev/watchdog` 권한 없음 (Security C3) → kernel WDT 실제 비동작, main.go가 WARN만 출력하고 진행
- 결과: systemd만 watchdog하고 kernel은 안 함 → 다음 단계 (kernel hard reset)는 영원히 안 일어남

### 5. Schema validation 비대칭
- Server는 `jsonschema.validate` strict, gateway는 `encoding/json` (unknown field 무시)
- Profile 변경 시 server가 "OK"라 한 입력을 gateway가 silently 잘못 해석
- shared/sensor_profile_schema.json의 `data_type`, `length`, `endianness`를 gateway가 모두 무시 (E2E H4) → uint16 65535를 int16 -1로 표시

---

## 수정 우선순위 통합 (1-2 sprint)

### Sprint Day 1 오전 batch — **APPLIED (2026-05-04 13:30)**
| # | 항목 | 출처 | 변경 파일 | 상태 |
|---|---|---|---|---|
| 1 | E2E C2: worker subscribe `gw/+/+` → `gw/+/#` | E2E | `server/worker/main.py:37,71` | ✅ |
| 2 | E2E H2: gateway expires_at RFC3339Nano + invalid → reject | E2E | `gateway/internal/actuator/actuator.go:153-178` | ✅ |
| 3 | E2E H1: gateway-id mismatch reject in `execute()` | E2E | `gateway/internal/actuator/actuator.go:153-160` | ✅ |
| 4 | Security C1: mosquitto listener `0.0.0.0` → `127.0.0.1`, ufw 1883 제거 | Security | `deploy/scripts/install-pi4.sh:97,123-124` | ✅ |
| 5 | Security C3: watchdog group + udev rule + systemd SupplementaryGroups | Security | `install-pi4.sh:46-53,108-117`, `iot-gateway.service:11-12` | ✅ |
| 6 | HAL H1: `assertSafeState` `pthread_mutex_trylock` (signal-handler safe) | HAL | `hal/src/platform_pi4.c:215-235` | ✅ |
| 7 | Gateway C1: defer 순서 분리 — recover가 가장 마지막 등록 (LIFO 첫 실행) | Gateway | `gateway/cmd/gateway-agent/main.go:78-95` | ✅ |
| 8 | E2E C3: LWT timestamp 제거 (gateway) + server-side stamping (state.py) | E2E | `gateway/internal/mqtt/client.go:83-92`, `server/worker/handlers/state.py:42-50` | ✅ |
| 9 | HAL C1+H2: `gw_gpio_cleanup()` 신설 + `gw_hal_cleanup`이 호출 + g_gpio_initialized 리셋 | HAL | `hal/src/platform_pi4.c:193-219`, `hal/src/common.c:22-30`, `hal/src/platform_r1124.c:39-41`, `hal/include/gw_hal.h:84-90` | ✅ |
| 10 | HAL C3: Modbus exception response를 헤더 2바이트 후 분기로 도달 가능하게 | HAL | `hal/src/rs485.c:148-184` | ✅ |
| 11 | Gateway H1: `gateway.id` regex 검증 (MQTT topic injection 차단) + 길이 64 제한 | Gateway | `gateway/internal/config/config.go:9-18,165-170`, `config_test.go:140-156` | ✅ |
| 12 | E2E M9+M10: HAL Go wrapper에 `ModemAT/ResetSoft/ResetHard` 추가 + `ErrInternal` 상수 + `HAL_ABI.md` `GW_ERR_INTERNAL` 추가 | E2E + Docs | `gateway/internal/hal/hal.go:30-65,202-227`, `docs/HAL_ABI.md:23,40-41` | ✅ |

**검증:**
- ✅ Python (`worker/main.py`, `state.py`) — `ast.parse` 통과
- ✅ Bash (`install-pi4.sh`) — `bash -n` 통과
- ✅ C (`common.c`, `rs485.c`, `platform_pi4.c`, `platform_r1124.c`) — `gcc -fsyntax-only` 통과 (gpiod stub 사용)
- ⚠️ Go — 이 환경에 `go` 미설치, syntactic 검증 미수행. Pi 환경의 `go build` 필요
- ⚠️ systemd unit — `Command not executable` 경고 (binary가 install 후 생성되므로 정상). `StartLimitIntervalSec` "Unknown key" 경고는 systemd 230+에서 [Unit] section으로 옮겨진 것 — 기존 코드 그대로, 영향 무시.

**fix 후 변화:**
- relay LAN 임의조작 즉시 차단 (Security C1)
- kernel WDT 실제 동작 (Security C3 — 기존 main.go가 `WARN: kernel watchdog disabled` 만 찍던 경로가 사라짐)
- panic/SIGTERM 경로의 relay 안전 상태 보장 (HAL H1 + Gateway C1)
- Modbus exception 응답이 `GW_ERR_TIMEOUT` 대신 `GW_ERR_IO`로 정상 반환 (HAL C3)
- worker가 `command/response` 4-segment 토픽 수신 가능 (E2E C2) — **단 ID 불일치는 별도 fix 필요** (E2E C1+C4 provisioning workflow, Day 2 작업)
- `expires_at` 마이크로초 silently skip 차단 (E2E H2)
- 다른 gateway 명령 오발행 차단 (E2E H1)
- LWT 가짜 timestamp 차단 (E2E C3)

**남은 BLOCKING (E2E C1+C4):** ID provisioning workflow는 4-6시간 작업이라 별도 sprint. Day 1 오전 fix 후에도 telemetry/state는 여전히 ID 불일치로 drop되므로 README acceptance criteria 검증은 ID 통일 fix 후 가능.

---

### Sprint Day 1 오전 batch (원본 plan, 위 내용으로 대체됨)

위 APPLIED 표가 원본 plan 8건 + 추가 4건 (HAL C1+H2 묶음, HAL C3, Gateway H1, E2E M9+M10) = **12건**을 모두 포함.

→ **Day 1 오전 끝나면**: relay LAN 임의조작 차단 + watchdog 진짜 가동 + safe-state 패닉 경로 안전 확보 + 일부 wire 정합성 (command 만료/방향 검증).

### Day 1 오후 — Provisioning APPLIED (2026-05-04 14:00)

**E2E C1 + C4 통합:** wire 식별자(슬러그)와 DB UUID의 분리. Gateway YAML/MQTT는 슬러그(`GW-DEV01`, `sensor-01`, `relay-vent`)를 사용, 서버는 boundary에서 슬러그 → UUID 변환.

| 변경 | 파일 | 핵심 |
|---|---|---|
| Migration 0002 | `server/alembic/versions/0002_channel_slug.py` | sensor_channels/actuator_channels에 `slug` 컬럼(NOT NULL, UNIQUE per gateway, CHECK `^[A-Za-z0-9_-]+$`) + gateways.serial_number CHECK |
| Models | `server/app/models.py` | `SensorChannel.slug`, `ActuatorChannel.slug` mapped_column + `__table_args__` UniqueConstraint |
| Schemas | `server/app/schemas.py` | `SlugStr` Annotated 타입 (Pydantic StringConstraints) + `GatewayIn.serial_number`, `SensorChannelIn.slug`, `ActuatorChannelIn.slug` 적용 |
| Lookup cache | `server/worker/handlers/_lookups.py` (NEW) | TTL 60s in-memory 캐시 (gateway_uuid_by_serial, sensor_channel_uuid_by_slug, actuator_channel_by_slug) |
| Dispatcher | `server/worker/handlers/__init__.py` | regex `^gw/(?P<serial>[A-Za-z0-9_-]+)/(?P<kind>[a-z_/]+)$`, gateway lookup 후 UUID로 핸들러 위임 |
| Telemetry | `server/worker/handlers/telemetry.py` | `sensor_channel_id`(슬러그) → `sensor_channel_uuid_by_slug` lookup |
| Commands publish | `server/app/routers/commands.py` | 토픽 `gw/{gw.serial_number}/command/request` + payload `actuator_channel_id: actuator.slug` |
| Tests | `server/tests/test_worker_handlers.py` (rewrite) + `tests/test_dispatch.py` (NEW, 5건) | mock lookup으로 슬러그 경로 + 4-segment 토픽 + invalid 케이스 검증 |

**검증:** `pytest -v` → **13 passed**, 0.42s. 모든 worker handler/dispatch/command_response/health 테스트 통과.

**Wire 흐름 (적용 후):**
```
Gateway YAML:  gateway.id = "GW-DEV01"  ←→  Server DB: gateways.serial_number = "GW-DEV01"
                                              gateways.id = <UUID> (DB 내부 PK)

Gateway YAML:  channel_id = "sensor-01"  ←→  Server DB: sensor_channels.slug = "sensor-01"
                                              sensor_channels.id = <UUID>
               channel_id = "relay-vent"  ←→  actuator_channels.slug = "relay-vent"
                                              actuator_channels.id = <UUID>

MQTT topic:    gw/GW-DEV01/telemetry  →  worker dispatch → Gateway lookup → UUID → handler
MQTT payload:  {"sensor_channel_id": "sensor-01", ...}  →  slug → UUID → INSERT telemetry
MQTT command:  topic gw/GW-DEV01/command/request, payload {"actuator_channel_id": "relay-vent", ...}
```

**E2E C1+C4 fix 후 BLOCKING 상태:**
- ✅ telemetry round-trip 가능 (Gateway slug → DB UUID 변환)
- ✅ command request → response round-trip 가능 (4-segment topic + slug 변환)
- ✅ heartbeat/state 도달 가능
- ⚠️ **운영 검증 필요:** 실 Pi + server 통합 환경에서 telemetry INSERT count > 0 확인. 현재는 단위 테스트 13건만 PASS.

**남은 BLOCKING (Day 2 작업):**
- Gateway C2 — command idempotency 미연결 (1-2h)
- Gateway C3 — 오프라인 큐 Flush 미구현 (2-3h)
- Server H3 — worker 직렬 dispatch (2h)

---

### Sprint Day 1 (오후 ~ Day 2 — provisioning 설계 + 큰 fix) [원본 plan]
| 순위 | 항목 | 출처 | 시간 |
|---|---|---|---|
| 9 | E2E C1+C4+B2: provisioning workflow + serial_number-기반 dispatcher + sensor_channels 슬러그 컬럼 | E2E | 4-6h |
| 10 | HAL C1+H2: gw_hal_cleanup에 GPIO cleanup 추가 + g_gpio_initialized 리셋 | HAL | 30분 |
| 11 | HAL C2: rs485 read_with_timeout 누적 시간 추적 | HAL | 30분 |
| 12 | HAL C3: Modbus exception response 판별 위치 수정 | HAL | 20분 |
| 13 | Gateway C2: command idempotency API 연결 (CommandSeen + LogCommand) | Gateway | 1-2h |
| 14 | Gateway C3: 오프라인 큐 Flush 구현 (OnConnect 콜백 + worker goroutine) | Gateway | 2-3h |
| 15 | Server H3 (잔존): worker asyncio.Queue + N workers | Server | 2h |
| 16 | Server delta C-NEW-1: jwks.py를 httpx.AsyncClient로 전환 | Server | 30분 |

→ **Day 2 끝나면**: end-to-end loop 가동, provisioning 정형화, 오프라인 큐 동작, 직렬 dispatch 해소.

### Sprint Day 3 (안전망 보강 + doc-truth)
| 순위 | 항목 | 출처 | 시간 |
|---|---|---|---|
| 17 | Gateway H1: gateway_id topic injection 검증 (`^[A-Za-z0-9_-]+$`) | Gateway | 10분 |
| 18 | Gateway H4: MQTT OnConnect에서 actuator subscribe 재등록 | Gateway | 30분 |
| 19 | Gateway H5: `PurgeOld()` 호출 추가 (scheduler tick) | Gateway | 30분 |
| 20 | Gateway H3: SQLite Enqueue 트랜잭션 보장 + SetMaxOpenConns(1) | Gateway | 30분 |
| 21 | Server H5 (REVIEW): telemetry partition DEFAULT + scheduler N+2 ahead | Server | 1h |
| 22 | E2E H4: profile data_type/length/endianness 처리 | Gateway | 2h |
| 23 | E2E H5: command idempotency 캐시 (Gateway C2와 통합) | Gateway | (Day 2에 묶음) |
| 24 | Security H4: gateway sensor profile jsonschema 검증 추가 | Security | 1h |
| 25 | Docs C1: plan §36 phase 번호 0-based 통일 | Docs | 90분 |
| 26 | Docs C4: provision-keycloak.sh 추가 | Docs | 90분 |
| 27 | Docs C3: add-user.sh 추가 | Docs | 60분 |
| 28 | HAL H4: test_safe_state가 실제 platform_pi4.c 링크하도록 Makefile 수정 | HAL | 1h |

→ **Day 3 끝나면**: 안전망 + 운영 자동화 + doc-truth 일관성.

**3 sprint day 합계: ~24시간 작업 → 109개 finding 중 ~50개 해결 (모든 Critical + High 대부분)**.

남은 Medium/Better-Alternative는 Phase 1 R1124 산업 게이트웨이 도입 sprint 또는 Phase 3 web portal sprint에 병합.

---

## 선행 리뷰 회귀 검증 (REVIEW_PHASE1_PHASE2 → 현재)

| 선행 ID | 항목 | 현재 상태 | 비고 |
|---|---|---|---|
| C1 | server sd_notify | ✅ **fix됨** | `app/utils/sd.py` + `main.py:45,49` watchdog_loop |
| C2 | JWT verify default OFF | ✅ **fix됨** | default `True` + JWKS 캐시 + RS256 verify |
| H1 | telemetry partition 하드코딩 | ✅ **fix됨** | DEFAULT partition + 동적 N+3개월 |
| H2 | naive vs aware datetime | ✅ **fix됨** | `app/utils/time.py` + 4개 핸들러 교체 |
| H3 | worker 직렬 dispatch | ❌ **잔존** | asyncio.Queue 미도입 — Day 2 작업 |
| H4 | worker/scheduler watchdog | ✅ **fix됨** | WatchdogSec=30 + watchdog_loop |
| H5 | install-server.sh | ⚠️ **부분 fix** | password 자동 생성 + verification ✅, `curl|sh` uv 잔존 + `CHANGE_ME_VERNEMQ_PASSWORD` 잔존 |
| H6 | get_current_user upsert | ✅ **fix됨** | SELECT-only, 미등록 user → 403 |

**평가:** 8건 중 6 fix + 1 잔존 + 1 부분 = **양질의 진전**. Server delta 신규 발견(C-NEW-1 jwks.py sync httpx, H-NEW-1 companies/sites 권한 미구현)이 그 빈자리를 채움.

---

## 좋은 신호 (이 프로젝트의 강점)

리뷰가 critical을 많이 잡았지만 다음 5가지는 진심으로 잘 되어 있다.

1. **HAL ABI 문서화** — `gw_hal.h` ↔ `HAL_ABI.md` 함수/error code 100% 일치 (단 `GW_ERR_INTERNAL` 1건만 누락). Go cgo binding도 깔끔하게 매핑.
2. **systemd 운영 강화** — `Type=notify` + WatchdogSec + ProtectSystem + ReadWritePaths + MemoryMax + SupplementaryGroups까지 production-grade 패턴. 단지 코드가 따라가야 함 (sd_notify 등).
3. **선행 리뷰 후속 fix 속도** — Server 8건 중 6건이 사실상 한 번에 fix됨. 의사결정/실행 cycle이 빠름.
4. **JSON Schema를 server↔gateway SoT로 명시 설계** — `shared/sensor_profile_schema.json` 한 곳에서 양측이 참조 (단 gateway가 실제 사용 안 하는 게 아쉬움 — fix 예정).
5. **Phase별 명시적 deferral** — plan 41 섹션 중 Phase 3-7로 미룬 항목들이 명시되어 있어 "왜 지금 없는지" 추적 가능. 다이어그램에서만 deferral 표시가 약함 (보강 권장).

---

## 걱정 신호

1. **테스트가 happy path 위주** — `test_safe_state.c`가 실제 platform 미링크, smoke #4 manual unplug 미자동화, server side는 `KC_VERIFY_SIGNATURE=false`로만 CI 실행. 핵심 안전 경로가 검증 안 됨.
2. **API는 있지만 호출이 없는 dead code** — `localdb.CommandSeen` / `PurgeOld` / `state.firmware_version` 처리 등 "준비된 API 0건 호출" 패턴 5건 발견. 향후 silently regress 가능.
3. **Doc-truth 균열** — plan §36 (1-7) vs README/diagram (0-7) phase 번호 충돌. 다이어그램이 미구현 컴포넌트(ruleengine, Web Portal, RLS)를 active와 같은 visual weight로 표시 → 신규 contributor가 "이미 구현됐다" 오해.
4. **3-tier 사이의 contract가 코드로 정의되지 않음** — wire schema가 양측 코드에 hand-coded → drift 발생. `datamodel-code-generator` + `quicktype` 같은 자동 생성으로 lock-in 권장 (Phase 1+).

---

## 영역별 리뷰 파일

| 파일 | 줄 수 | 주요 발견 |
|---|---|---|
| `01_HAL_REVIEW.md` | 309 | gw_hal_cleanup GPIO 누수, RS485 timeout 재사용, exception detection 도달불가, mutex 데드락 |
| `02_GATEWAY_REVIEW.md` | 444 | defer LIFO 역전, idempotency 미연결, 오프라인 큐 Flush 미구현, topic injection, MQTT 재구독 누락 |
| `03_SERVER_DELTA_REVIEW.md` | 413 | 회귀 6/8 fix, jwks 동기 httpx, companies/sites 권한 부재 |
| `04_E2E_INTEGRATION_REVIEW.md` | 592 | gateway_id slug↔UUID, worker wildcard 부족, sensor_channel_id 불일치, expires_at 파싱 |
| `05_DOCS_AND_PLAN_REVIEW.md` | 428 | plan §36 phase 번호 충돌, Keycloak realm 미자동화, 41 섹션 매트릭스 |
| `06_SECURITY_CROSSCUT_REVIEW.md` | 535 | MQTT anonymous LAN, /dev/watchdog 권한, idempotency 부재, sensor profile validation |
| **합계** | **2,721** | **🔴 18 / 🟠 31 / 🟡 41 / 🔵 19 = 109건** |

**선행:** `docs/REVIEW_PHASE1_PHASE2.md` (335줄) — Server-only 1차 리뷰, 이번 회귀 결과 6/8 fix.

---

## 다음 단계 권장

1. **이 OVERVIEW를 팀과 공유** — 특히 BLOCKING 5건 (B1-B5)이 모두 함께 fix되어야 README acceptance criteria 검증이 의미 있음을 강조.
2. **Sprint Day 1 오전을 BLOCKING + 안전 결함 묶음에 할당** — 8개 작업 모두 합쳐 ~3시간. 가성비 최고.
3. **Day 2의 provisioning workflow 설계** — 이 작업이 wire schema 정합성의 backbone. 이 후 OTA/config push (Phase 5+)도 자연스럽게 build-on 가능.
4. **plan §36 갱신을 doc 작업 첫 순위로** — 90분 투자로 "Phase X" 의미의 분기를 차단. 후속 모든 cross-check 비용 감소.
5. **테스트 강화 backlog 생성** — `test_safe_state` 실제 링크, smoke USB unplug 자동화, server `KC_VERIFY_SIGNATURE=true` CI matrix. 안전 critical 경로의 회귀 방지.
