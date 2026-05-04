# 전체 시스템 개념 구성도

> System Concept Architecture · v0.1.0
> Phase 0 (CM4 eMMC 검증) → Phase 1+ (R1124-10 양산 + 자체 PCB)
> 작성일: 2026-05-03

## 6-Layer Top-Down View

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                           전체 시스템 개념 구성도                                   ║
║              유기보호소 환경 모니터링 + 방제 IoT Gateway Platform                   ║
║                                                                                    ║
║   측정값:  온도(℃) · 습도(%) · PM10(㎍/㎥) · PM2.5(㎍/㎥) · NH3(ppm) · CO2(ppm)   ║
║   제어:    환기팬 · 살균 분무기 · (선택) 로봇청소기                                 ║
╚══════════════════════════════════════════════════════════════════════════════════╝


┌────────────────────────────────────────────────────────────────────────────────┐
│   ① USER LAYER                                                                  │
│                                                                                  │
│   ┌──────────┐  ┌────────────┐  ┌────────────┐  ┌─────────┐  ┌──────────┐     │
│   │ System   │  │ 관리회사   │  │ 고객사     │  │ Site    │  │ Operator │     │
│   │ Admin    │  │ Admin      │  │ Admin      │  │ Manager │  │ /Viewer  │     │
│   └─────┬────┘  └──────┬─────┘  └──────┬─────┘  └────┬────┘  └─────┬────┘     │
│         │              │               │             │             │           │
│         └──────────────┴───────────────┴─────────────┴─────────────┘           │
│                                       │                                          │
│                                       │  HTTPS  (브라우저 / 모바일 웹)            │
└───────────────────────────────────────┼──────────────────────────────────────────┘
                                        │
                                        ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│   ② WEB PORTAL  (React + Vite SPA · Apache ECharts)                             │
│                                                                                  │
│   ┌────────────┐  ┌────────────────┐  ┌──────────────┐  ┌──────────────┐       │
│   │ 내 게이트웨이│  │ Gateway 상세    │  │ Sensor 추가   │  │ 관리자        │       │
│   │ 목록·상태  │  │ 시계열·제어     │  │ Wizard (8단계)│  │ User/Site/Bulk│       │
│   └────────────┘  └────────────────┘  └──────────────┘  └──────────────┘       │
│                                       │                                          │
│                                       │  HTTPS  (Bearer JWT)                     │
└───────────────────────────────────────┼──────────────────────────────────────────┘
                                        │
                                        ▼
╔════════════════════════════════════════════════════════════════════════════════╗
║   ③ SELF-HOSTED SERVER  (Ubuntu 24.04 LTS · systemd · Docker 미사용)            ║
║                                                                                  ║
║   ┌─────────────────────────────────────────────────────────────────────┐       ║
║   │              Nginx :443  (HTTPS reverse proxy + 정적 파일)           │       ║
║   │           ──/auth → 8080 ── /api → 8000 ── / → frontend──           │       ║
║   └────┬────────────────────┬────────────────────┬─────────────────────┘       ║
║        │                    │                    │                              ║
║        ▼                    ▼                    ▼                              ║
║  ┌────────────┐    ┌──────────────────┐   ┌──────────────────────────────┐    ║
║  │ Keycloak   │    │ Backend API      │   │ Worker · Scheduler             │    ║
║  │ :8080      │    │ FastAPI :8000    │   │ (Python asyncio)               │    ║
║  │            │    │ ─ JWT 검증        │   │ ─ telemetry 수신·저장         │    ║
║  │ Realm:     │    │ ─ 권한 매핑       │   │ ─ alarm rule 평가              │    ║
║  │ iot-       │    │ ─ Gateway/Sensor │   │ ─ command timeout             │    ║
║  │ platform   │    │ ─ Command publish│   │ ─ partition 정리               │    ║
║  │ + 7 roles  │    │ ─ Config 발행    │   │ ─ backup / report             │    ║
║  └─────┬──────┘    └────────┬─────────┘   └─────────┬──────────────────┘      ║
║        │                    │                       │                            ║
║        └────────────────────┼───────────────────────┘                            ║
║                             │                                                    ║
║         ┌───────────────────┼───────────────────┐                                ║
║         ▼                   ▼                   ▼                                ║
║   ┌──────────┐      ┌──────────────┐    ┌───────────────────┐                  ║
║   │PostgreSQL│      │ VerneMQ      │    │ /var/lib/         │                  ║
║   │ :5432    │      │ MQTT Broker  │    │ iot-platform/     │                  ║
║   │          │      │ :1883 / :8883│    │  ─ firmware       │                  ║
║   │ ─iot_db  │      │              │    │  ─ gateway-configs│                  ║
║   │ ─keycloak│      │ Phase 1 plain│    │  ─ backups        │                  ║
║   │ ─RLS     │      │ Phase 7 TLS  │    │  ─ log-bundles    │                  ║
║   │  (Phase  │      │ + X.509 ACL  │    │                   │                  ║
║   │   6+)    │      │              │    │                   │                  ║
║   └──────────┘      └──────┬───────┘    └───────────────────┘                  ║
╚═════════════════════════════│════════════════════════════════════════════════════╝
                              │
                              │  MQTT  (gw/{id}/...)
                              │
       ┌──────────────────────┼──────────────────────┐
       ▼                      ▼                      ▼
┌────────────────┐   ┌────────────────┐   ┌────────────────┐
│ ④ MQTT Topic   │   │ ④ MQTT Topic   │   │ ④ MQTT Topic   │
│ 패턴 (per gw)  │   │ 패턴 (per gw)  │   │ 패턴 (per gw)  │
└────────────────┘   └────────────────┘   └────────────────┘

  Gateway → Server (publish):                Server → Gateway (subscribe):
  ─ gw/{id}/telemetry      (10초 주기)      ─ gw/{id}/config/desired
  ─ gw/{id}/state          (online/offline)  ─ gw/{id}/command/request
  ─ gw/{id}/heartbeat      (30초 주기)       ─ gw/{id}/ota/request
  ─ gw/{id}/event          (알람/에러)
  ─ gw/{id}/config/reported
  ─ gw/{id}/command/response
  ─ gw/{id}/ota/status

                              │
       ┌──────────────────────┴──────────────────────┐
       ▼                                              ▼
╔═══════════════════════════════════╗   ╔═══════════════════════════════════╗
║ ⑤ GATEWAY  GW-001                  ║   ║ ⑤ GATEWAY  GW-002 ... GW-N         ║
║   유기보호소 #1                     ║   ║   유기보호소 #2 ... #N             ║
║                                     ║   ║                                     ║
║  ┌───────────────────────────────┐ ║   ║  ┌───────────────────────────────┐ ║
║  │ CM4 (eMMC) + Waveshare carrier│ ║   ║  │ (Phase 1+: R1124-10)          │ ║
║  │ Pi OS Lite 64 + systemd       │ ║   ║  │ 동일 SoC, 동일 SW stack       │ ║
║  │                                │ ║   ║  └───────────────────────────────┘ ║
║  │ ┌───────────────────────────┐ │ ║   ║                                     ║
║  │ │ Go Agent (단일 정적 binary)│ │ ║   ║                                     ║
║  │ │ ─ mqtt · sensor · actuator│ │ ║   ║                                     ║
║  │ │ ─ rule-engine (offline)   │ │ ║   ║                                     ║
║  │ │ ─ local-db (SQLite)       │ │ ║   ║                                     ║
║  │ │ ─ health · OTA agent      │ │ ║   ║                                     ║
║  │ └────────────┬──────────────┘ │ ║   ║                                     ║
║  │              │ cgo            │ ║   ║                                     ║
║  │              ▼                │ ║   ║                                     ║
║  │ ┌──────────────────────────┐ │ ║   ║                                     ║
║  │ │ libgw_hal.so (C)         │ │ ║   ║                                     ║
║  │ │ ─ libgpiod (BCM2711)     │ │ ║   ║                                     ║
║  │ │ ─ termios + Modbus CRC   │ │ ║   ║                                     ║
║  │ │ ─ /dev/watchdog (15s)    │ │ ║   ║                                     ║
║  │ └────────────┬─────────────┘ │ ║   ║                                     ║
║  │              │                │ ║   ║                                     ║
║  │ ┌────────────┴────────────┐  │ ║   ║                                     ║
║  │ │ 로컬 mosquitto :1883    │  │ ║   ║                                     ║
║  │ │ (Phase 0 dev only)      │  │ ║   ║                                     ║
║  │ └─────────────────────────┘  │ ║   ║                                     ║
║  └────────────┬─────────────────┘ ║   ║                                     ║
╚═══════════════│════════════════════╝   ╚═════════════════════════════════════╝
                │
                │  RS-485 Modbus RTU  +  GPIO  +  (LAN: 로봇청소기)
                │
                ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│   ⑥ FIELD I/O  (유기보호소 현장 장비)                                            │
│                                                                                  │
│   ┌──────────────────────────────────────────────────────────────────────┐     │
│   │  📡 6-in-1 환경/가스 센서  (RS-485 Modbus, slave_id=1)                 │     │
│   │     ┌──────────┬──────────┬──────────┬──────────┬──────────┬────────┐ │     │
│   │     │ 온도      │ 습도      │ PM10      │ PM2.5     │ NH3       │ CO2    │ │     │
│   │     │ ℃        │ %        │ ㎍/㎥     │ ㎍/㎥     │ ppm       │ ppm    │ │     │
│   │     │ reg 0    │ reg 1    │ reg 2    │ reg 3    │ reg 4    │ reg 5  │ │     │
│   │     └──────────┴──────────┴──────────┴──────────┴──────────┴────────┘ │     │
│   └──────────────────────────────────────────────────────────────────────┘     │
│                                                                                  │
│   ┌──────────────────────────────┐    ┌──────────────────────────────┐         │
│   │  🌬️  환기팬 (Relay #1)         │    │  💧 살균 분무기 (Relay #2)     │         │
│   │     GPIO BCM 17               │    │     GPIO BCM 27               │         │
│   │     NC wiring (전원 차단=safe) │    │     NC wiring                 │         │
│   │     max_on_duration: 600s    │    │     max_on_duration: 60s      │         │
│   └──────────────────────────────┘    └──────────────────────────────┘         │
│                                                                                  │
│   ┌──────────────────────────────────────────────────────────────────────┐     │
│   │  🤖 로봇청소기 (선택, Phase 4+)                                          │     │
│   │     Roborock S7 + Valetudo flash → 같은 mosquitto에 합류                │     │
│   │     Topic: valetudo/<robot>/BasicControlCapability/operation/set       │     │
│   └──────────────────────────────────────────────────────────────────────┘     │
└────────────────────────────────────────────────────────────────────────────────┘
```

## Legend

| 기호 | 의미 |
|---|---|
| `──→` | 동기 데이터 흐름 (HTTPS / 함수 호출) |
| `═══` | 주요 시스템 경계 (server / gateway / field) |
| `cgo` | Go ↔ C 바인딩 |
| `①-⑥` | 계층 번호 (top-down) |

## 3개 핵심 boundary

| Boundary | 책임 분리 |
|---|---|
| **User ↔ Web Portal** | HTTPS + Bearer JWT (Keycloak이 token 발급, frontend가 호출) |
| **Web Portal ↔ Server** | REST API + 권한 매핑 (FastAPI가 Keycloak claim 검증 후 PostgreSQL DB로 실 권한 판단) |
| **Server ↔ Gateway** | MQTT (`gw/{id}/*` 패턴, Gateway별 ACL — Phase 7 X.509로 강화) |

## 3개 SoT (Single Source of Truth)

| SoT | 위치 | 비고 |
|---|---|---|
| **사용자 인증** | Keycloak | Token 발급만, 권한 판단 ❌ |
| **권한 매핑** | PostgreSQL `user_*_permissions` 테이블 | company/site/gateway 3축 |
| **Sensor Profile** | `shared/sensor_profile_schema.json` | server (Python pydantic) ↔ gateway (Go struct) 자동 생성 |

## 주요 데이터 흐름 시나리오

### 📊 Telemetry (10초 주기, 정상 운영)

```
6-in-1 센서 ──RS485──→ HAL.ModbusRead ──cgo──→ Go sensor-service
                                                       │
                                                       │ scale/offset 적용
                                                       │ + 6 measurement payload
                                                       ▼
   Local mosquitto ──MQTT──→ VerneMQ ──→ Worker ──→ PostgreSQL telemetry
                                                       │
                                                       │ telemetry_latest UPSERT
                                                       ▼
   Web Portal 실시간 ECharts 그래프  +  대시보드 카드 갱신
```

### 🎛️ 원격 제어 (User → Field)

```
User → Web Portal → Backend API (권한 검사 — User × Gateway × control)
   → command DB row 생성 (status=pending)
   → VerneMQ publish (gw/{id}/command/request)
   → Gateway mqtt-client subscribe → actuator-service
   → safety check (expires_at, max_on_duration, idempotency)
   → HAL.GPIOSet(BCM 17, 1) → Relay ON
   → 600s timer 시작
   → response publish (gw/{id}/command/response)
   → Worker → DB update (status=executed) → Web 표시
   → 600s 후 자동 OFF + audit event publish
```

### 🚨 자동 안전 제어 (NH3 > 25 ppm 임계 초과)

```
sensor-service: NH3 = 27.0 ppm (10초 주기 polling)
   → telemetry publish
   → 서버 alarm_rule_engine 평가 → critical (threshold 25)
   → command publish (gw/GW-001/command/request: relay-vent ON)
   → 환기팬 ON + 600s timer
   → 600s 후 자동 OFF
   → audit event publish (max_on_auto_off)
```

### 📴 오프라인 운영 (망 단절)

```
VerneMQ 연결 실패 (cloud-side)
   → Go agent SQLite 큐 적재
   → 우선순위: event (1) > command_response (2) > telemetry (3)

망 복귀
   → MQTT autoreconnect (paho.mqtt.golang)
   → backlog flush (oldest first within priority)

망 단절 중에도 동작:
   ─ 로컬 Rule engine (오프라인 자동 제어)
   ─ Local SQLite 7일 retention buffer
   ─ Sensor polling (계속)
   ─ Actuator local safety (max_on_duration 강제)
```

## Watchdog 3-Layer (안전 메커니즘)

```
Application (Go panic recover)        ◄── 즉시
        │  os.Exit(1) → systemd 재시작
        ▼
systemd WatchdogSec=30                ◄── 30s
        │  SIGABRT → core dump → 재시작
        ▼
Kernel WDT (BCM2835)                  ◄── 15s
        │  hardware reboot
        ▼
NC Wiring (전원 차단 = safe state)     ◄── 즉시
        │  electrical fail-safe
        ▼
   안전 상태 보장
```

각 상위 계층의 timeout은 하위보다 짧게 (30s > 15s가 시간 흐름 순서. 하지만 kernel WDT가 더 짧은 15s timeout이라 OS가 hang일 때 우선 firing).

## 핵심 기능 요약

| 기능 | 구현 위치 | Phase |
|---|---|---|
| 환경 측정 (6 measurement) | Go sensor-service + libgw_hal.so | Phase 0 |
| 액추에이터 제어 | Go actuator-service + GPIO | Phase 0 |
| MQTT broker | mosquitto (Phase 0 local) → VerneMQ (Phase 1+) | Phase 0/1 |
| Telemetry 영구 저장 | PostgreSQL partition | Phase 1 |
| Web Portal 대시보드 | React + Vite + ECharts | Phase 2 |
| Sensor Wizard | React (관리자 UI) | Phase 3 |
| Alarm Rule + 자동 제어 | 서버 alarm_rule_engine + Gateway local | Phase 4 |
| Gateway Config 버전 관리 | desired/reported 패턴 | Phase 5 |
| OTA | Mender community | Phase 5 |
| Safety MCU 외부 supervisor | STM32 Bluepill (자체 PCB) | Phase 7 |
| OSS Notice / SBOM | 제품 출시 직전 | Phase 7 |

## 향후 다이어그램 (예정)

- `02_detailed_architecture.md` — 서버 내부 모듈 + Gateway 내부 layered architecture (HAL/Go/cgo) 상세
- `03_data_flow_telemetry.md` — Telemetry 흐름 sequence + retry/buffer 처리
- `04_data_flow_command.md` — Command 흐름 sequence + 안전 검사 단계
- `05_failure_modes.md` — 10가지 실패 모드 + detection + recovery 흐름
- `06_security_layers.md` — TLS · JWT · ACL · RLS 다중 방어선
- `07_phase_roadmap.md` — Phase 0-7 단계별 시스템 진화
