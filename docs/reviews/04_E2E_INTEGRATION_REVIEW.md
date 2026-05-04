# Review: 3-Tier Integration & Wire Schema Consistency

> 작성일: 2026-05-04
> 범위: HAL ABI ↔ Gateway (Go) ↔ Server (Python) cross-layer 정합성
> 형태: review only — 구현 0줄
> 발견 이슈: 🔴 4 · 🟠 6 · 🟡 7 · 🔵 4

---

## A. Topic Map

| Topic Pattern | 발행자 (file:line) | QoS | Retained | Will | 구독자 (file:line) | QoS | 상태 |
|---|---|---|---|---|---|---|---|
| `gw/{id}/telemetry` | gateway sensor.go:227 | 1 (cfg.QoS default) | no | - | server worker/main.py:37 (`gw/+/+`) → handlers/__init__.py:37 → telemetry.py | 1 | ❌ topic-id 형식 불일치 (C1) — gateway는 `GW-DEV01` 슬러그, worker regex는 UUID만 통과 |
| `gw/{id}/state` | gateway mqtt/client.go:84 (LWT, retain=true), client.go:135 (graceful), client.go:193 (online); health.go:65 (shutdown) | 1 | yes (LWT + PublishOnline + graceful) | yes (LWT) | server handlers/__init__.py:39 → state.py | 1 | ❌ topic-id 형식 불일치 (C1) · ❌ LWT timestamp = `New()` 호출시점에 결정 (C3) |
| `gw/{id}/heartbeat` | gateway health.go:104 | 1 | no | - | server handlers/__init__.py:41 → heartbeat.py | 1 | ❌ topic-id 형식 불일치 (C1) |
| `gw/{id}/event` | gateway actuator.go:222 | 1 | no | - | server handlers/__init__.py:45 (log only, "unhandled") | 1 | 🟡 worker가 silently drop (M1) |
| `gw/{id}/command/request` | server commands.py:79 (`mqtt_publisher.publish`, qos=1) | 1 | no | - | gateway actuator.go:79-82 (`Subscribe` qos=cfg.QoS) | 1 | ❌ gateway는 단일 segment까지의 wildcard로만 매칭 가능. server가 발행하는 `command/request` 는 gateway 측 path filter와 일치 (정확 토픽 명시) — OK 하지만 gateway-id 형식 불일치(C1) 문제는 동일 |
| `gw/{id}/command/response` | gateway actuator.go:131 | 1 | no | - | server handlers/__init__.py:43 → command_response.py | 1 | ❌ topic-id 형식 불일치 (C1) · 🟠 worker dispatch regex `[a-z_/]+` 가 슬래시를 포함하므로 일치하나 `command_response`(언더스코어) 패턴과 충돌 가능 (M2) |
| `gw/{id}/config/desired` | server: 발행자 없음 (Phase 5+) | - | - | - | gateway: client.go:13 주석 only — 실제 subscribe 호출 0건 | - | 🔵 미구현, 양측 모두 stub (B1) |
| `gw/{id}/config/reported` | gateway: 발행자 없음 (mqtt/client.go:13 주석만) | - | - | - | server handlers/__init__.py:45 (unhandled) | - | 🔵 미구현 (B1) |
| `gw/{id}/ota/status` | 양측 모두 미구현 | - | - | - | server handlers/__init__.py:45 (unhandled) | - | 🔵 Phase 5+ |

> **참고:** worker는 wildcard `gw/+/+` 한 단계만 구독 (main.py:37). `gw/{id}/command/response` 처럼 두 단계 sub-path는 broker가 deliver 안 함 → **C2 별도 이슈로 다룸**.

---

## B. Payload Schema Diff

### B.1 Telemetry payload (`gw/{id}/telemetry`)

| 필드 | Gateway 발행 (sensor.go:220-225) | Server 수신 (handlers/telemetry.py:30-72, schemas.py 미정의) | 일치? |
|---|---|---|---|
| `message_id` | `uuid.NewString()` (string) | 사용 안 함 (drop) | 🟡 dedup 키 미활용 (M3) |
| `gateway_id` | `m.gatewayID` (string, e.g. `"GW-DEV01"`) | topic에서 UUID 파싱하여 덮어씀, body 필드는 무시 | ❌ string slug ↔ UUID 불일치 (C1) |
| `timestamp` | `time.Now().UTC().Format(time.RFC3339Nano)` | `parse_iso8601` (Z suffix 자동 처리) | ✅ |
| `values[].sensor_channel_id` | `c.cfg.ChannelID` (YAML 슬러그, e.g. `"sensor-01"`) | `uuid.UUID(v["sensor_channel_id"])` 강제 변환 — 실패 시 `bad sensor_channel_id` 로그 후 drop | ❌ slug ↔ UUID 불일치 (C4) |
| `values[].measurement_key` | string (e.g. `"ammonia"`) | string, model String(64) | ✅ |
| `values[].value` | `float64` (sensor.go:194 `int16` → float64 cast) | `float(value) if isinstance(value, (int, float))` → `value_double` 만 채움 | 🟡 비-float 타입 silent drop (REVIEW_PHASE1_PHASE2 M3 재확인) |
| `values[].unit` | string from profile (`degC`, `ppm`, `%`, `ug/m3`) | String(32) — `ug/m3`(5자), `degC`(4자) 모두 길이 OK | ✅ |
| `values[].quality` | `"good"` 또는 `"out_of_range"` | `String(32)` 저장 | ✅ |
| (없음) `company_id`, `site_id` | gateway 발행 안 함 | server가 `Gateway` row 조회로 채움 | ✅ (server-side enrichment) |

### B.2 State payload (`gw/{id}/state`)

| 필드 | Gateway 발행 | Server 수신 (state.py) | 일치? |
|---|---|---|---|
| `gateway_id` | LWT/graceful/online 모두 포함 (mqtt/client.go:86,131,185) | topic에서 추출, body 필드 무시 | ❌ C1 |
| `status` | `"offline"` (LWT/graceful), `"online"` (PublishOnline), `"shutdown"` (health.go:63) | `if new_status in ("online", "offline", "shutdown")` 화이트리스트 | ✅ |
| `timestamp` | `time.RFC3339` (LWT/state) vs `time.RFC3339Nano` (heartbeat) | `parse_iso8601` 양쪽 호환 | ✅ |
| `reason` | `"lwt"` / `"graceful"` (mqtt/client.go:89,134) | 사용 안 함 (drop) | 🟡 운영상 유용한 정보 누락 (M4) |
| `app_version` | health.go:48 PublishOnline에서만 (`"0.1.0-pi4-phase0"`) | state.py:38 저장 | ✅ |
| `firmware_version` | gateway 발행 안 함 | state.py:40 저장 (있을 때만) | 🟡 미발행 → DB always NULL (M5) |
| `config_version` | gateway 발행 안 함 | state.py:42 (`isinstance(int)` 가드) | 🟡 미발행 → DB default 0 고정 (M5) |
| `uptime_sec` | health.go:49 PublishOnline에 포함 | 무시 | 🟡 손실 |

### B.3 Heartbeat payload (`gw/{id}/heartbeat`)

| 필드 | Gateway 발행 (health.go:92-102) | Server 수신 (heartbeat.py) | 일치? |
|---|---|---|---|
| `gateway_id` | string | topic 우선 | ❌ C1 |
| `timestamp` | RFC3339Nano | `parse_iso8601` | ✅ |
| `hostname` | string | 무시 | 🟡 손실 |
| `uptime_sec` | int | 무시 | 🟡 손실 |
| `go_alloc_mb` / `go_sys_mb` / `goroutines` | float / int | 무시 | 🟡 손실 (M6 — heartbeat이 단순 ping만 됨) |
| `disk_root_used_percent` | float | 무시 | 🟡 손실 (cfg.Storage.DiskUsageWarnPct alarm 무용지물) |
| `cpu_temp_celsius` | float | 무시 | 🟡 손실 |

### B.4 Command request (`gw/{id}/command/request`)

| 필드 | Server 발행 (commands.py:64-76) | Gateway 수신 (actuator.go:89-101 `CommandRequest`) | 일치? |
|---|---|---|---|
| `command_id` | `f"cmd-{strftime}-{uuid8}"` (str) | `string` | ✅ 형식 호환 |
| `gateway_id` | `str(gateway_id)` UUID hex | `string` | ⚠️ gateway는 자기 ID 비교 검증 없음 (받기만 하면 무조건 자기 명령으로 가정) → 다른 gateway 명령 오발행 시 무방어 (H1) |
| `target_type` | `"actuator"` | gateway 검사 안 함 | 🟡 stub field (M7) |
| `actuator_channel_id` | `str(body.actuator_channel_id)` UUID hex | string lookup `m.channels[req.ActuatorChannelID]` — gateway는 YAML config의 `channel_id` 슬러그 (`"relay-01"`) 키로 등록 | ❌ UUID ↔ 슬러그 불일치 (C5) |
| `action` | `Literal["ON", "OFF"]` | `"ON"|"on"|"1"|"true"|"OFF"|"off"|"0"|"false"` 모두 허용 | ✅ (gateway 관대) |
| `issued_by` | `str(user.id)` UUID | string | ✅ |
| `issued_at` | `now.isoformat()` aware UTC | 사용 안 함 | 🟡 |
| `expires_at` | `expires_at.isoformat()` aware UTC | `time.Parse(time.RFC3339, ...)` (RFC3339, **not Nano**) | ⚠️ Python `isoformat()`은 microsecond 6자리 포함 → `time.RFC3339` 파서가 이를 파싱하지 못해 expires 검사 silently skip (H2) |
| `timeout_ms` | int | int (사용 안 함) | 🟡 클라이언트 timeout만, gateway는 무시 |
| `require_ack` | bool (default True) | bool (handleCommand:129) | ✅ |
| `reason` | `body.reason or ""` | string | ✅ |

### B.5 Command response (`gw/{id}/command/response`)

| 필드 | Gateway 발행 (actuator.go:104-112) | Server 수신 (command_response.py) | 일치? |
|---|---|---|---|
| `command_id` | string | `body.get("command_id")` lookup | ✅ |
| `gateway_id` | gateway slug string | topic 우선, `cmd.gateway_id != gateway_id` 비교 → 항상 mismatch (UUID vs slug) | ❌ 모든 응답이 "gateway mismatch" 로 drop (C1+C5 합산 효과 — H3) |
| `status` | `"executed" | "rejected" | "failed"` | `body.get("status", "executed")` (default "executed" 위험) | 🟡 default 위험 (M8) — `"timeout"` 누락 |
| `reason` | string | `cmd.response = body` 통째 저장 | ✅ |
| `result` | string (e.g. `"relay-01-ON"`) | response JSONB 안에 저장 | ✅ |
| `executed_at` | `time.RFC3339Nano` aware UTC | `parse_iso8601` → `cmd.completed_at` | ✅ |
| `local_safety_check` | string | response JSONB 안 저장 | ✅ |

---

## C. HAL ABI ↔ Go binding 매핑

| C 함수 (gw_hal.h:NN) | Go wrapper (hal.go:NN) | 일치? | 비고 |
|---|---|---|---|
| `gw_hal_init` (h:41) | `Init` (hal.go:74) | ✅ | Init이 추가로 `gw_gpio_init`도 호출 — ABI 측면 OK, 호출 순서 문서화 필요 |
| `gw_hal_cleanup` (h:44) | `Cleanup` (hal.go:83) | ✅ | |
| `gw_hal_version` (h:47) | `Version` (hal.go:88) | ✅ | buf size 64 일치 |
| `gw_gpio_init` (h:55) | `Init` 내부에서만 호출 (hal.go:78) | 🟡 별도 export 없음 (재호출 불가) — 멱등이라 OK |
| `gw_gpio_request_output` (h:63) | `RequestOutput` (hal.go:106) | ✅ | |
| `gw_gpio_request_input` (h:70) | `RequestInput` (hal.go:111) | ✅ | |
| `gw_gpio_set` (h:73) | `GPIOSet` (hal.go:116) | ✅ | |
| `gw_gpio_get` (h:76) | `GPIOGet` (hal.go:121) | ✅ | |
| `gw_gpio_assert_safe_state` (h:83) | `AssertSafeState` (hal.go:131) | ⚠️ | C 함수는 int 반환하나 Go wrapper는 반환값 무시 — 함수 명세상 "절대 실패하지 않음" 이므로 OK이지만 향후 ABI 확장 시 주의 |
| `gw_rs485_open` (h:96) | `RS485Open` (hal.go:138) | ✅ | parity는 `byte` 전달 — Go 호출자가 `'N'` 리터럴 사용 |
| `gw_rs485_modbus_read` (h:104) | `ModbusRead` (hal.go:149) | ✅ | length 0 또는 >125 사전 차단 |
| `gw_rs485_modbus_write` (h:109) | `ModbusWrite` (hal.go:167) | ✅ | |
| `gw_rs485_close` (h:113) | `RS485Close` (hal.go:173) | ✅ | |
| `gw_watchdog_open` (h:122) | `WatchdogOpen` (hal.go:180) | ✅ | |
| `gw_watchdog_kick` (h:125) | `WatchdogKick` (hal.go:189) | ✅ | |
| `gw_watchdog_close` (h:128) | `WatchdogClose` (hal.go:194) | ✅ | |
| `gw_modem_at` (h:136) | **wrapper 없음** | ❌ Phase 0 stub이지만 Go wrapper 0건 — HAL_ABI.md는 Phase 1+ 표시 (M9) |
| `gw_modem_reset_soft` (h:139) | **wrapper 없음** | ❌ 동일 (M9) |
| `gw_modem_reset_hard` (h:142) | **wrapper 없음** | ❌ 동일 (M9) |

| Error code (gw_hal.h:26-36) | Go const (hal.go:30-39) | 매핑 | HAL_ABI.md (l:13-22) |
|---|---|---|---|
| `GW_OK = 0` | `OK Err = 0` | ✅ | ✅ |
| `GW_ERR_TIMEOUT = -1` | `ErrTimeout = -1` | ✅ | ✅ |
| `GW_ERR_CRC = -2` | `ErrCRC = -2` | ✅ | ✅ |
| `GW_ERR_IO = -3` | `ErrIO = -3` | ✅ | ✅ |
| `GW_ERR_INVALID = -4` | `ErrInvalid = -4` | ✅ | ✅ |
| `GW_ERR_NOT_INIT = -5` | `ErrNotInit = -5` | ✅ | ✅ |
| `GW_ERR_BUSY = -6` | `ErrBusy = -6` | ✅ | ✅ |
| `GW_ERR_PERM = -7` | `ErrPerm = -7` | ✅ | ✅ |
| `GW_ERR_INTERNAL = -99` | **누락** | ❌ Go wrapper에 상수 없음 (M10) — `Err.Error()` default branch가 처리하지만 비교(`err == hal.ErrInternal`) 불가 |

C 구조체: gw_hal.h는 opaque (구조체 노출 0건). 모든 상태는 fd/pin int + slave/register/length scalar. Go side cgo struct 매핑 0건 → **레이아웃 불일치 위험 0** ✅.

---

## D. Sensor Profile Schema 정합성

**스키마 (shared/sensor_profile_schema.json):**
- `additionalProperties: false` 양측에 강제 (root + measurement + modbus_spec)
- 필수: root `[name, protocol, measurements]`; measurement `[key, unit, data_type]`; modbus_spec `[function_code, register, length]`
- `data_type` enum: `[int, uint, float, bool, string]`
- `function_code` enum: `[3, 4]`
- modbus_spec에 `endianness` 필드 정의 (default `"big"`)

**5개 example 스키마 검증:**
- `temp_humidity_rs485.json`, `co2_rs485.json`, `nh3_rs485.json`, `pm_sensor_rs485.json`, `livestock_6in1_rs485.json` — 모두 root required + measurement required 충족 ✅
- 모두 `data_type: "float"` 사용, `function_code: 3` ✅
- `endianness` 미지정 (모두 default `"big"` 의존) ✅
- ⚠️ 모든 예제가 `length: 1` 만 사용 — gateway sensor.go:194에 `int16` 단일 register 처리 하드코딩, length>1 측정 구성 시 첫 값만 사용하고 나머지 silent drop (H4)

**Gateway parser (sensor.go:29-59):**
- `additionalProperties: false` 가 schema에 있지만 Go `encoding/json`은 default로 unknown field를 무시 (strict 검증 없음) → **schema 위반을 gateway가 발견 못함** (M11)
- `display_group`, `order` 같은 schema-정의된 optional field 파싱 **전혀 안 함** (Profile struct에 필드 없음) → 미사용이라 큰 문제는 아니나 향후 sensor.go에서 그룹/정렬 활용 시 누락
- `data_type`, `description`, `endianness` 모두 무시 → **gateway는 항상 int16 → float 처리** (H4)
- `default_polling_interval_sec` 파싱은 하지만 (`Profile.DefaultPollingSec`), 실제로는 `cfg.SensorChannel.PollingIntervalSec` (YAML) 만 사용 → profile의 default 무용지물 (M12)
- Scale=0 → 1.0 default 적용 (sensor.go:75-77), Offset default는 적용 안 함 (Go zero value 0 그대로 → OK)

**Server consumer (sensor_profiles.py:36-49):**
- `jsonschema.validate(body.profile_schema, _schema())` — schema-아래 모든 키/타입 검증 ✅
- 단, **shared 경로 의존**: `Path(__file__).resolve().parents[3] / "shared" / "sensor_profile_schema.json"` — 배포 시 `parents[3]` 경로가 깨질 수 있음 (예: pip install로 server 패키지화 시) (M13)

**비대칭 위험:**
- Server는 schema validation **strict**, gateway는 **무시**
- → 사용자가 server API로 valid profile 등록 가능, 이를 gateway가 받아 `connection.endianness="little"` 설정해도 gateway는 못 본 척 → 데이터 silent corruption (H4 연관)
- 반대로 server는 거부했지만 gateway YAML로 직접 invalid profile 로드 → gateway는 통과, server에 저장된 schema와 불일치

---

## E. Command Lifecycle 통합 분석

```
┌─────────────────────┐
│ User → POST         │
│ /gateways/{id}/cmds │  commands.py:23
└──────────┬──────────┘
           │ 1. INSERT commands (status='pending')  commands.py:46-60
           ↓
   DB(commands.id="cmd-...", status='pending')
           │
           │ 2. mqtt_publisher.publish(qos=1)  commands.py:78-80
           │    topic: gw/{UUID-string}/command/request
           │    payload: { command_id, gateway_id=UUID, actuator_channel_id=UUID, ... }
           ↓
   ┌──────────────────────────────────────┐
   │ MQTT broker (VerneMQ/mosquitto)      │
   │   QoS 1: queues if subscriber off    │
   │   clean_session=false (gateway)      │
   └──────┬──────────────────────────┬────┘
          │ 3a. publish OK           │
          ↓                          │
   commands.py:81 status='published' │
          │                          │
          ↓                          │
   ◇──────────────────────◇          │
   │ Gateway online?       │ NO ───→ broker queues (QoS 1 store)
   ◇──────────────────────◇          │   gateway reconnect 시 deliver
          │ YES                      │
          ↓                          │
   actuator.go:114 handleCommand     │
          │                          │
          │ 4. JSON unmarshal        │
          │ 5. CommandID empty? → reject (no replay/dup check) (H5)
          │ 6. ExpiresAt check (RFC3339, microsec fail silent) (H2)
          │ 7. m.channels[ActuatorChannelID]  ← UUID lookup, but key=YAML slug ❌ (C5)
          │    → "rejected: unknown channel: <UUID>"
          │ 8. (skipped) hal.GPIOSet
          │
          ↓ if RequireAck (req.RequireAck:129)
   actuator.go:131 publish gw/{slug}/command/response
          │   QoS 1, retain=false
          │   payload: { command_id, gateway_id=slug ❌ (C1) , status, ... }
          ↓
   ┌──────────────────────────────────────┐
   │ MQTT broker                           │
   └──────┬───────────────────────────────┘
          │
          ↓
   worker main.py:37 subscribe gw/+/+
   ├── topic = gw/{slug}/command/response (3 segments → matched? NO) (C2)
   │   → wildcard `gw/+/+` only matches 2-segment children
   │   → response NEVER reaches dispatcher
   │
   └── (assume reach via fix) handlers/__init__.py:43
          │
          ↓
   command_response.py:34 session.get(Command, cmd_id)
          │ if cmd.gateway_id (UUID) != gateway_id (UUID from topic, but topic carries slug)
          │   → "gateway mismatch" log + return  (H3)
          │
          ↓ (assume reach via C1+C2 fix)
   commands.status = body.status
   commands.response = body
   commands.completed_at = parse_iso8601(body.executed_at)
   await session.commit()
          │
          │ MEANWHILE
          ↓
   ◇──────────────────────────────────────────◇
   │ scheduler/jobs/command_timeout            │  (REVIEW_PHASE1_PHASE2 M7 race)
   │ N초마다 status IN ('pending','published') │
   │   AND expires_at < now → status='timeout' │
   │ ↑ 동시 UPDATE race with worker            │
   ◇──────────────────────────────────────────◇
```

**상태 추적:**
- Server: `commands` row with `status`, `response`, `completed_at` (단일 source of truth)
- Gateway: actuator.go의 `channelState.currentValue` (in-memory only) — 재시작 시 손실, server에 sync 안 함
- Broker: QoS 1 + clean_session=false 양쪽 → 양방향 store-and-forward 보장 (단 gateway client_id 안정 가정)

**Race / 데이터 손실 위험:**
1. **C2 (worker wildcard 부족) + C1 (slug↔UUID)**: command response가 worker에 도달조차 못함 → server 측 commands는 **영원히 published 상태로 정체** → scheduler.command_timeout이 결국 `'timeout'` 으로 변경 → 사용자에게는 모든 명령이 "타임아웃" 으로 보임 (운영 BLOCKER)
2. **H1 (gateway-id 미검증)**: 같은 broker에 두 gateway가 wrong topic으로 잘못 subscribe → 다른 gateway 명령 실행 가능
3. **H5 (replay/idempotency 없음)**: gateway는 같은 command_id 중복 수신 시 두 번 GPIOSet 실행 → relay flicker 위험
4. **H2 (expires_at 파싱 실패)**: silently skip → 만료된 명령도 실행됨
5. **REVIEW_PHASE1_PHASE2 M7**: scheduler/worker UPDATE race
6. **broker QoS 1 store**: gateway 장기 offline → broker가 GB 단위 queue 적재 → backlog 폭주 시 broker OOM

---

## F. 발견 이슈

### 🔴 CRITICAL

#### C1. Gateway ID 형식 불일치 — 모든 telemetry/state/heartbeat/command가 server에서 drop됨

**위치:**
- gateway: `gateway/internal/config/config.go:27` (`ID string` 예시 `"GW-DEV01"`), `sensor.go:227`/`actuator.go:131`/`mqtt/client.go:84,135`/`health.go:104` 모두 `m.gatewayID` 슬러그 그대로 토픽에 사용
- server: `worker/handlers/__init__.py:16-25` regex `^gw/(?P<gw>[0-9a-fA-F\-]+)/(?P<kind>[a-z_/]+)$` 후 `uuid.UUID(m.group("gw"))` 강제 변환

**증상:** gateway가 `gw/GW-DEV01/telemetry` 발행 → worker regex가 `GW-DEV01`을 매칭(`-`+hex chars 만족)하지만 `uuid.UUID("GW-DEV01")` ValueError → "invalid gateway_id in topic" 로그 후 메시지 drop. 사실상 **모든 wire 메시지가 server에서 처리되지 않음**.

**근거:**
```
config.go:27   ID string `yaml:"id"`   // "GW-DEV01" 등
__init__.py:16 _TOPIC_RE = re.compile(r"^gw/(?P<gw>[0-9a-fA-F\-]+)/(?P<kind>[a-z_/]+)$")
__init__.py:25 gateway_id = uuid.UUID(m.group("gw"))   # raises
models.py:138  Gateway.id: UUID(as_uuid=True) primary key
```

추가로 server `gateways` 테이블 PK가 UUID이므로 `serial_number`(text, unique) 와 `id`(UUID) 가 분리되어 있음 — 즉 server 모델은 "서버가 부여한 UUID"를 토픽 식별자로 가정한 설계. 그러나 gateway는 자체 YAML config의 `gateway.id` 슬러그를 사용 → 양측 모델 자체가 불일치.

**영향:** Phase 0 ↔ Phase 2 간 wire 통신 **완전 실패**. Telemetry 0건, command 응답 0건, online/offline 미반영. 운영 불가.

**해결:**
- (A) Gateway YAML `gateway.id` 를 등록 시 서버가 발급한 UUID로 변경 (provisioning workflow 추가)
- (B) Server 모델에 `Gateway.serial_number`(이미 존재) 를 토픽 키로 사용. worker dispatcher가 `serial_number` lookup → UUID 변환
- (C) Topic 명명 규칙 변경: `gw/{serial}/...` 로 명확히 분리, server는 `serial` 기반 dispatch
- **권장:** (B) — `serial_number = "GW-DEV01"` 매칭으로 양측 코드 변경 최소화. dispatcher 1곳만 수정 + Gateway lookup 추가 (REVIEW_PHASE1_PHASE2 H3 worker 큐 재설계 시 함께 처리).

---

#### C2. Worker subscribe wildcard `gw/+/+` 가 sub-path 토픽 매칭 못함 — command/response 전부 drop

**위치:**
- server: `worker/main.py:37` `await client.subscribe("gw/+/+", qos=1)`
- gateway: `actuator.go:131` publish `gw/{id}/command/response` (3 segments after `gw`)

**증상:** MQTT wildcard `+` 는 정확히 한 단계 segment만 매칭. `gw/{id}/command/response` 는 `gw/+/+/+` 패턴이 필요. **Gateway가 보낸 모든 command response, config/reported, ota/status 토픽을 worker가 영원히 못 받음**.

**근거:** MQTT 5.0 §4.7.1 (and 3.1.1) wildcard 시맨틱 표준. paho/aiomqtt 모두 표준 준수.

**영향:** C1과 결합 시 commands 시스템이 100% 무응답. Scheduler가 모든 명령을 timeout 처리. 사용자 UI: "모든 제어 명령 실패".

**해결:**
- Worker가 multi-level subscribe: `client.subscribe("gw/+/+/#", qos=1)` 또는 `client.subscribe([("gw/+/+", 1), ("gw/+/+/+", 1)])`
- Dispatcher regex도 `kind` 그룹이 슬래시 포함해야 하므로 이미 `[a-z_/]+` 로 OK
- 단, `gw/+/#` 는 Phase 5+의 `config/desired/abc/...` 같은 4단계 까지 다 잡으므로 권장. 단 metadata 토픽 `$SYS/...` 는 별도 prefix라 안전.

---

#### C3. LWT timestamp 가 client 생성 시점 고정 — 비정상 종료 시 잘못된 시각

**위치:**
- gateway: `gateway/internal/mqtt/client.go:85-91`
```go
lwtPayload, _ := json.Marshal(map[string]any{
    "timestamp": time.Now().UTC().Format(time.RFC3339),  // ← New() 호출 순간
    ...
})
pahoOpts.SetWill(lwtTopic, string(lwtPayload), opts.QoS, true)
```
- server: `worker/handlers/state.py:44` `gw.last_seen_at = parse_iso8601(body.get("timestamp"))` 단, `body.status == "online"` 일 때만

**증상:** Gateway가 7일간 정상 운행 후 abort → broker가 LWT 발행 → 그 timestamp는 **7일 전 New() 시점**. server state.py는 "online"일 때만 last_seen_at을 갱신하므로 직접 영향은 적으나, alarm/audit 분석 시 잘못된 종료 시각 기록.

**근거:** MQTT LWT는 broker가 client disconnect 감지 시 사전 등록된 payload를 그대로 발행. payload 내 timestamp 동적 갱신 불가능.

**영향:** 사후 incident 분석 misleading. SLA 계산 오류. Audit log 신뢰도 저하.

**해결:**
- LWT payload에서 `timestamp` 제거 (또는 `"timestamp": null` 명시)
- 대신 server가 LWT 수신 시점에 server-side timestamp 부여 (state.py에서 `body.status == "offline"` 이고 `body.reason == "lwt"` 면 서버 현재시각 사용)
- 또는 timestamp 의미를 "마지막 정상 보고된 시각"으로 재정의하고 heartbeat의 last seen 기준 사용

---

#### C4. sensor_channel_id 형식 불일치 — telemetry values가 모두 drop

**위치:**
- gateway: `sensor.go:206` `"sensor_channel_id": c.cfg.ChannelID` (YAML slug, e.g. `"sensor-01"`)
- server: `worker/handlers/telemetry.py:47` `channel_id = uuid.UUID(v["sensor_channel_id"])` — ValueError → "bad sensor_channel_id" 로그 후 continue

**증상:** Server `sensor_channels.id` 는 UUID (models.py:187). Gateway YAML의 `channel_id` 는 운영자가 지정한 슬러그. 모든 telemetry value 가 `bad sensor_channel_id` 로 drop. **Telemetry 테이블에 INSERT 0건**.

**근거:** C1과 동일 구조적 문제 (provisioning 미설계).

**영향:** 대시보드 영원히 빈 화면. `telemetry_latest` 도 비어있음. C1 fix 후에도 별도로 fix 필요.

**해결:**
- Gateway가 server에서 받은 `sensor_channels.id` (UUID) 를 YAML config에 함께 보유 (provisioning 시 sync)
- 또는 server worker가 `(gateway_id, slug) → sensor_channel.id` lookup 캐시 (sensor_channels에 slug 컬럼 추가 필요)
- 권장: provisioning workflow 단순화 위해 **gateway 측 `channel_id` 를 server UUID 그대로 사용**. YAML 가독성 손실은 `display_name` 으로 보완.

---

### 🟠 HIGH

#### H1. Gateway가 수신 command의 gateway_id 검증 안 함

**위치:**
- gateway: `actuator.go:79-82` subscribe 토픽은 자기 ID 기반이라 보통 자기 명령만 옴. 하지만 actuator.go:138-218 `execute()` 어디에도 `req.GatewayID == m.gatewayID` 검증 없음.

**증상:** 누군가 `gw/A/command/request` 에 `gateway_id="B"` 를 담아 발행해도 gateway A가 그대로 실행. 일반적 운용에서는 broker ACL이 막아야 하지만, Phase 0 mosquitto는 anonymous (config.go:36 `Username` 빈 문자열 default).

**해결:** `execute()` 시작부에 `if req.GatewayID != "" && req.GatewayID != m.gatewayID { reject "wrong gateway" }`.

---

#### H2. expires_at 파싱 형식 불일치 — RFC3339Nano 마이크로초가 silent drop

**위치:**
- server: `commands.py:71` `now.isoformat()` — Python aware datetime은 microsecond 6자리 포함 (`"2026-05-04T12:34:56.123456+00:00"`)
- gateway: `actuator.go:155` `time.Parse(time.RFC3339, req.ExpiresAt)` — `time.RFC3339` (not Nano) 는 `2006-01-02T15:04:05Z07:00` 으로 fractional 미지원

**증상:** Go `time.Parse(time.RFC3339, "2026-05-04T12:34:56.123456+00:00")` → error → `if t, err := ...; err == nil` 가드에 의해 **expires 검사 자체 skip**. 만료된 명령도 실행됨.

**근거:** Go 표준 라이브러리 doc — RFC3339Nano 는 별도 layout (`2006-01-02T15:04:05.999999999Z07:00`).

**해결:** gateway가 `time.RFC3339Nano` 사용 + fallback `time.RFC3339` 로 try chain. Python 측은 변경 불필요 (자체 포맷 일관).

---

#### H3. command_response의 gateway_id slug ↔ UUID mismatch로 모든 응답 drop

**위치:**
- gateway: `actuator.go:142` `GatewayID: m.gatewayID` (slug)
- server: `command_response.py:38-42` `if cmd.gateway_id != gateway_id` 비교

C1+C5 결합 효과. 단독 fix 불가, C1 fix 시 자동 해결.

---

#### H4. Sensor 측정에서 data_type / length / endianness 무시

**위치:**
- shared/sensor_profile_schema.json: `data_type` enum `[int, uint, float, bool, string]`, `length: 1-125`, `endianness: big|little`
- gateway: `sensor.go:194` `val := float64(int16(raw[0]))` — **항상 첫 register만, signed 16-bit, big-endian 가정**

**증상:** Profile에 `length: 2` (uint32, float32) 또는 `data_type: "uint"` 정의 시 gateway는 **infer 정보 무시하고 raw[0]을 int16으로 처리**. 값 의미적 corruption (예: 65535 ppm CO2 → -1로 표시됨).

**해결:** Phase 1 작업 — profile data_type+length+endianness에 따른 분기 추가. `int16` / `uint16` / `int32` / `uint32` / `float32` 처리.

---

#### H5. Command idempotency / replay 보호 없음

**위치:**
- gateway: `actuator.go:147-151` `command_id` 빈 문자열만 reject. 동일 `command_id` 중복 수신 처리 없음
- server: `commands.id` 는 PK이므로 server-side는 자연 unique이지만 broker가 QoS 1 재전송 시 gateway가 중복 실행

**증상:** broker → gateway 사이 ACK 손실 시 paho가 같은 메시지를 재전송 → 같은 relay를 두 번 ON. Max-on timer는 cancel/재설정으로 reset되어 의도보다 길게 작동.

**해결:** Gateway에 최근 N개 `command_id` 캐시(LRU) 또는 SQLite로 `applied_commands` 테이블 → 중복 시 prior response를 그대로 재발행 (idempotent).

---

#### H6. config_version / firmware_version 발행 자체가 없음

**위치:**
- gateway: state payload (mqtt/client.go:185 PublishOnline) 에 `app_version` 만 health.go:48에서 추가. `config_version`, `firmware_version` 발행 0건
- server: `state.py:38-42` 두 필드 처리 분기 있음. `Gateway.config_version` PK fallback default 0 영구 유지.

**증상:** OTA / config push (Phase 5+) 도입 시 server가 gateway 현재 firmware/config 상태를 못 알아 incremental update 불가. state.py 코드는 이미 준비됐으나 발행자 없음 → dead code.

**해결:** Phase 5+ 작업이지만, 지금부터 PublishOnline payload에 `firmware_version`, `config_version` 필드 추가 (지금은 hard-coded 0 / `runtime.Version()` 으로라도).

---

### 🟡 MEDIUM

#### M1. `gw/{id}/event` (max_on_auto_off 등) 가 worker에서 silently dropped

**위치:** `actuator.go:222` 발행, `__init__.py:45` `kind in ("event", ...)` → log only.

운영자가 자동 OFF 발생 사실을 server UI에서 확인할 방법 없음. event 핸들러 추가 (audit_logs 적재) 권장.

---

#### M2. dispatch regex의 `kind` 패턴이 너무 관대

**위치:** `__init__.py:16` `kind = [a-z_/]+`

`gw/abc/command_response` (언더스코어, 잘못된 형태) 도 매칭됨. `command/response` 와 충돌 가능. 명시적 enum dispatch (각 kind 별 prefix 매칭) 가 안전.

---

#### M3. `message_id` 가 server에서 무시 — at-least-once 중복 처리 안 됨

**위치:** `sensor.go:221` `message_id` 발행, `telemetry.py` 에서 미사용. Broker QoS 1 재전송 시 telemetry가 중복 INSERT (단, `telemetry_latest` 는 ts 비교로 일관성 유지). 시계열 raw row가 dup → 분석 시 평균 왜곡.

**해결:** `Telemetry` 테이블에 `message_id` 컬럼 + UNIQUE 제약 또는 worker dedup 캐시.

---

#### M4. LWT `reason` 필드가 server에서 무시

운영 진단 가치 큼 (`"lwt"` vs `"graceful"` vs `"shutdown"` 분류). state.py에서 `gw.last_termination_reason` 컬럼 추가 권장.

---

#### M5. firmware_version / config_version 대응 H6 와 동일 root cause

---

#### M6. heartbeat의 모든 지표 (cpu_temp, disk%, goroutines) silently dropped

운영 모니터링/알람 기능 무력화. heartbeat 처리 시 별도 `gateway_metrics` 테이블 또는 Prometheus pushgateway 권장.

---

#### M7. command request의 `target_type` 미사용

actuator.go가 `target_type` 검증 안 함. 향후 `"system"` (reboot, OTA trigger) 추가 시 기존 명령과 혼동 가능. Schema 강제 권장.

---

#### M8. command_response.py의 `status` default `"executed"` 위험

**위치:** `command_response.py:44` `cmd.status = body.get("status", "executed")`

Gateway가 status 누락된 invalid response 발행 시 자동 success 표시 — 데이터 무결성 위협. default를 `"unknown"` 또는 reject 처리 권장.

---

### 🟡 MEDIUM (계속)

#### M9. HAL modem AT 함수 3개 Go wrapper 없음

C ABI에 정의되어 있으나 Go 측 접근 불가. Phase 1+ 구현 시 추가 필요. HAL_ABI.md에는 명시.

---

#### M10. `GW_ERR_INTERNAL` (-99) Go 상수 누락

비교 어려움. `Err.Error()` default 분기에서 텍스트는 표시되나 `errors.Is` 사용 시 실패. 추가 권장.

---

#### M11. Gateway sensor profile parser가 schema strict 검증 안 함

`encoding/json` 기본 unmarshal은 unknown field 무시. server는 strict, gateway는 관대 → 비대칭. `json.Decoder.DisallowUnknownFields()` 또는 별도 jsonschema validator 추가 권장.

---

#### M12. Profile의 `default_polling_interval_sec` 가 무용지물

Gateway는 항상 YAML `cfg.SensorChannel.PollingIntervalSec` 우선. Profile fallback 의미 없음. 의도가 "channel 미지정 시 profile 값 사용" 이라면 sensor.go에서 `if cfg == 0 { use profile.DefaultPollingSec }` 분기 추가.

---

#### M13. shared schema 경로 `parents[3]` 의존

Server를 패키지화하거나 다른 디렉터리로 이동 시 schema 못 찾음. 환경변수 `SCHEMA_PATH` 또는 importlib.resources 사용 권장.

---

#### M14. Topic 명명 일관성 부재

- `command/request` (slash) vs `command_response` (underscore) 가능성
- `state` (single word) vs `command/response` (path) 혼재

향후 `config/desired/{section}` 추가 시 worker `[a-z_/]+` regex만으로는 의미 분기 어려움. 토픽 명명 규약 문서화 권장.

---

### 🔵 BETTER ALTERNATIVES

#### B1. Sensor Profile schema → 코드 자동 생성 (REVIEW_PHASE1_PHASE2 B1 재확인)

`datamodel-code-generator` (Pydantic) + `quicktype` (Go struct) CI 도입. 양측 parser 코드 손작성 제거.

---

#### B2. 토픽 식별자에 `serial_number` 사용 + provisioning 정형화

현재 슬러그 vs UUID 갈등의 근본 원인. 명시적 provisioning workflow + protocol contract:
- Gateway boot → serial_number로 server에 register 요청 → server가 UUID 발급 + 서명된 token 반환
- 이후 모든 토픽은 `gw/{UUID}/...` 로 통일
- `sensor_channels.id`, `actuator_channels.id` 도 같은 방식으로 server 발급

---

#### B3. JSON Schema 버전 필드 (`schema_version: "1"`) 도입

향후 wire protocol 변경 시 호환성. payload header에 `version: int` 또는 토픽에 `gw/v2/{id}/...` prefix.

---

#### B4. broker shared subscription 도입 (Phase 5+)

Worker N대 scale-out 시 `$share/iot/gw/+/+` 패턴으로 broker가 부하 분산. REVIEW_PHASE1_PHASE2 H3 (worker queue) 와 결합 시 효과 극대화.

---

## G. 권장 수정 우선순위

| 순위 | 항목 | 영향 layer | 예상 시간 |
|---|---|---|---|
| 1 | C1 + C4: ID 형식 통일 (provisioning workflow + worker dispatcher 변경) | gateway YAML + server worker + DB lookup | 4-6h |
| 2 | C2: worker subscribe wildcard `gw/+/#` 또는 multi-pattern | server worker 1줄 | 5min |
| 3 | C3: LWT timestamp 제거 + server-side stamping | gateway mqtt + server state.py | 30min |
| 4 | H2: gateway expires_at 파싱 RFC3339Nano fallback | gateway actuator.go | 15min |
| 5 | H1: gateway-id mismatch reject 추가 | gateway actuator.go | 10min |
| 6 | H5: command idempotency 캐시 | gateway actuator.go + SQLite | 1-2h |
| 7 | H4: profile data_type/length 분기 처리 | gateway sensor.go | 2h |
| 8 | H6+M5: state payload에 firmware/config_version 발행 | gateway health.go | 30min |
| 9 | M1+M3: event handler / message_id dedup | server worker | 1-2h |
| 10 | M11: gateway DisallowUnknownFields + jsonschema | gateway config.go | 1h |
| 11 | M9+M10: HAL modem wrapper + ErrInternal 상수 | gateway hal.go | 30min |
| 12 | B2: provisioning workflow 정형화 (Phase 3-4 작업) | server + gateway | 1-2 sprint |

**합계 즉시 fix (1-7번):** 약 8-12시간 → **1-2 sprint day 내 wire 일관성 회복 가능**.

---

## H. Conclusion

**현 상태 평가: Wire schema 정합성 BROKEN — 양 layer가 독립적으로 컴파일/배포되었으나 실제 메시지 단 하나도 round-trip 못 함.** 4개 CRITICAL 이슈 (C1: gateway-id slug↔UUID, C2: worker wildcard sub-path 부재, C3: LWT timestamp, C4: sensor_channel_id slug↔UUID) 가 결합하여 telemetry 0건 INSERT, command response 0건 수신, online 상태 영구 false. HAL ABI ↔ Go binding은 modem 3개 함수와 ErrInternal 상수를 제외하면 매핑 정확하므로 **하단 layer는 견고하나 상단 wire 계약이 부재한 상태**.

**근본 원인:** 3개 layer가 독립 개발되며 "gateway_id 가 무엇인가"에 대한 단일 정의가 없었음. Server 모델은 `Gateway.id (UUID) + Gateway.serial_number (text)` 분리, gateway는 `gateway.id` 슬러그 단일, 둘 사이 sync 메커니즘 (provisioning) 미설계. 이 설계 공백이 connection-string-like 문자열 (slug) 과 식별자 (UUID) 의 혼선을 유발. **도메인 모델 + provisioning protocol** 을 다음 sprint 첫 작업으로 두지 않으면 fix 후에도 OTA/config push 도입 시 같은 문제 재발.

**다음 sprint 권고:**
1. **Sprint Day 1 오전:** C2 (5분), C3 (30분), H2 (15분), H1 (10분), M9+M10 (30분) — 작은 수정 묶음으로 즉시 정합성 일부 회복
2. **Sprint Day 1 오후 ~ Day 2:** C1+C4+B2 통합 작업 — provisioning protocol 설계 + serial_number-기반 dispatcher + sensor_channels 슬러그 컬럼 추가 (alembic migration). 이 작업이 wire schema 정합성의 backbone
3. **Sprint Day 3:** H4 (sensor data_type 처리), H5 (idempotency), H6+M5 (state 확장 발행), M1+M3 (event/message_id)
4. **이후:** REVIEW_PHASE1_PHASE2 의 C1/C2/H1-H6 작업과 병합. 본 리뷰의 B2 (provisioning) 가 끝나야 그 위에 OTA/config push (Phase 5+) 안정 구축 가능

**좋은 신호:** HAL ABI 문서화 우수 (gw_hal.h ↔ HAL_ABI.md 100% 일치), Go binding 깔끔 (error code 매핑 정확), sensor profile JSON schema가 양측 SoT로 명시 설계됨. **인프라는 견고**, wire layer만 수정하면 시스템 전체가 즉시 가동 가능.
