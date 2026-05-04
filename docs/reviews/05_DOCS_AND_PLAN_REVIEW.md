# Review: Docs / Plan / Diagrams 정합성

> 작성일: 2026-05-04
> 범위: 계획서 41-section + README + 5개 운영 docs + 7개 다이어그램 + 배포 스크립트
> 형태: review only — 구현 0줄
> 발견 이슈: 🔴 4 · 🟠 8 · 🟡 11 · 🔵 5

---

## A. Plan vs Implementation 매트릭스 (전 41 섹션)

| § | 제목 | Phase | 약속 (1줄) | 구현 상태 | 증거 / 비고 |
|---|---|---|---|---|---|
| 1 | 프로젝트 개요 | 전체 | 자체호스팅 IoT Gateway Fleet Mgmt + 10가지 핵심 기능 | ✅ 비전만 일치 | plan.md:11-29; 코드는 1-9 부분 충족 |
| 2 | 전제 조건 | 전체 | Docker 미사용 / systemd / Ubuntu LTS / FastAPI 등 | ✅ 일치 | install-server.sh + iot-backend.service uvicorn 사용 확인 |
| 3 | 핵심 설계 철학 | 전체 | Gateway 중심 / Profile 기반 / 중앙 config / systemd | ⚠️ 부분 — Profile/Gateway 중심 OK, **중앙 config (3.3) 미구현 (Phase 5 연기)** | gateway_configs 테이블·router 코드 부재 |
| 4 | 시스템 아키텍처 (mermaid) | 전체 | 7-node 데이터 흐름도 | ✅ 일치 | DEPLOYMENT_AND_USAGE_GUIDE.md:42-80에 동일 ASCII 재구성 |
| 5 | 서버 구성 (8+9 service) | 1 | nginx/vernemq/postgresql/keycloak/iot-backend/iot-worker/iot-scheduler/web-portal | ✅ 6/8 구현 (web-portal·prometheus 제외) | server/deploy/systemd/{iot-backend,iot-worker,iot-scheduler}.service 존재 |
| 6 | 서버 디렉터리 구조 | 1 | /opt/iot-platform/{backend,worker,scheduler,frontend,releases} + /etc/iot-platform/*.env | ⚠️ 부분 — install-server.sh는 단일 폴더 `/opt/iot-platform/server`로 통합, `frontend/` `releases/` 미사용 | install-server.sh:9 |
| 7 | Backend 구성 (16 역할) | 2 | 16개 backend 역할 + worker 9 역할 + scheduler 7 역할 | ✅ 핵심 일치, 일부 연기 | `app/routers/`에 핵심 router 존재 (gateway-permissions·OTA·alarm·audit·bulk 미구현) |
| 8 | 사용자 / 권한 모델 | 2 | 7 role + user_company_roles + user_site_permissions + user_gateway_permissions | ⚠️ 부분 — `user_gateway_permissions` 만 구현, **user_site_permissions 미구현** | DEPLOYMENT_AND_USAGE_GUIDE.md:807-815 |
| 9 | Keycloak 구성 | 1 | iot-platform realm + 4 group + 7 role | ⚠️ 자동화 부분 — install-server.sh가 client만 자동, **realm/role/group은 수동** | install-server.sh:64-97 |
| 10 | PostgreSQL 데이터 모델 | 2 | 12-table ER 다이어그램 | ✅ alembic migration 0001로 일치 | REVIEW_PHASE1_PHASE2.md:71 |
| 11 | DB 테이블 5종 | 2 | companies/sites/users/user_company_roles/user_gateway_permissions | ✅ 모두 구현 | DEPLOYMENT_AND_USAGE_GUIDE.md:443-447 + 802-815 |
| 12 | Gateway Profile | 2 | gateway_profiles 테이블 + JSON hardware_schema | ❌ **미구현 — 코드/테이블 부재** | DEPLOYMENT_AND_USAGE_GUIDE.md:611-614에서 gateway_profile_id 사용 안 함 |
| 13 | gateways 테이블 + 등록 시나리오 9단계 | 2 | gateways CREATE TABLE + 등록 9단계 | ✅ 테이블 존재, 절차는 부분 (자동등록 인증서 단계 없음) | |
| 14 | sensor_profiles + JSON Profile 예시 | 2/3 | 온습도/기울기 등 Profile 예시 + 테이블 | ✅ 테이블 + JSON Schema 일치, **livestock 6-in-1은 plan에 없음** (스코프 추가) | shared/examples/livestock_6in1_rs485.json |
| 15 | sensor_channels | 2/3 | sensor_channels 테이블 | ✅ 일치 | |
| 16 | Actuator Profile/Channel | 4 | actuator_profiles + actuator_channels + safety_config | ⚠️ 부분 — actuator_channels 구현 (Phase 4 일찍), **actuator_profiles 부재** | DEPLOYMENT_AND_USAGE_GUIDE.md:641-644 |
| 17 | Telemetry (PARTITION + telemetry_latest) | 2 | telemetry PARTITION BY RANGE(ts) + telemetry_latest | ✅ alembic 0001; **H1 이슈 — partition 하드코딩 2026-05/06만** | REVIEW_PHASE1_PHASE2.md:67-83 |
| 18 | Gateway Config (desired/reported + version) | 5 | gateway_configs + gateway_config_history | ❌ 미구현 (Phase 5 연기, 의도된 deferral) | |
| 19 | MQTT Topic 설계 | 2 | gw/{id}/{telemetry,state,heartbeat,event,config/desired,config/reported,command/{request,response},ota/{request,status},log/upload} 11종 | ⚠️ 부분 — 6종 사용, **config/* + ota/* + log/upload 미구현** | sample-config.yaml + smoke_test.sh + diagram 01 |
| 20 | MQTT Payload (telemetry/state) | 2 | message_id + values[] envelope, state 11 fields | ✅ telemetry envelope 일치, **state는 plan과 약간 다름** | diagram 03 + plan.md:1090-1108 |
| 21 | 원격 제어 명령 (sequenceDiagram + 안전 조건 8가지) | 4 | command flow 11단계 + 8 safety condition | ✅ Gateway 측 구현 완료 (smoke_test #4-5) | smoke_test.sh:80 + #5 expired |
| 22 | 알람 + 자동 제어 Rule | 4 | alarm_rules 테이블 + control rule | ❌ 미구현 (Phase 4 연기) | PHASE0_RUNBOOK.md:186 |
| 23 | Web Portal 화면 (3종) | 3 | 사용자/Gateway상세/관리자 화면 | ❌ 미구현 (Phase 3 연기) | DEPLOYMENT_AND_USAGE_GUIDE.md:14 |
| 24 | 센서 추가 Wizard (8단계) | 3 | UI 8단계 마법사 | ❌ 미구현 (Phase 3 연기) | |
| 25 | Dashboard 자동 생성 | 3 | measurement_key → Widget 매핑표 | ❌ 미구현 (Phase 3 연기) | |
| 26 | Gateway Template (양식장/어선 예시) | 6 | gateway_templates 테이블 | ❌ 미구현 (Phase 6 연기) | |
| 27 | Bulk Operation (8종) | 6 | bulk_jobs 테이블 + 8 작업 종류 | ❌ 미구현 (Phase 6 연기) | |
| 28 | Gateway Agent 구현 (10 모듈) | 0 | /opt/iot-gateway/{gateway-agent,sensor-service,...} | ⚠️ 부분 — install-pi4.sh가 단일 binary로 통합. 모듈은 internal/{mqtt,sensor,actuator,localdb,health} (ota-agent·rule-engine 부재) | install-pi4.sh:53,75 |
| 29 | Gateway Safety (8 기능 + Safety MCU) | 0/7 | fail-safe/max_on/expiry/manual override/interlock/watchdog/output feedback/E-stop | ⚠️ 부분 — fail-safe(NC)/max_on/expiry/watchdog 구현, **나머지 4종은 Safety MCU와 함께 Phase 7** | sample-config.yaml + smoke #5 |
| 30 | API 설계 | 2 | 5개 그룹 약 25 endpoint | ✅ ~80% 구현, /api/configs/* (Phase 5), /api/audit-logs (Phase 6) 미구현 | DEPLOYMENT_AND_USAGE_GUIDE.md:411 |
| 31 | systemd 서비스 예시 | 1/2 | iot-{backend,worker,scheduler}.service ini | ✅ 일치 + 추가 (WatchdogSec 등 강화) | server/deploy/systemd/ |
| 32 | Nginx 구성 | 1 | HTTPS reverse proxy + /api/ /auth/ / | ✅ DEPLOYMENT_AND_USAGE_GUIDE.md:248-280 동등 (`/`는 Phase 3 React 대기) | |
| 33 | 보안 설계 | 1+ | TLS / JWT / RBAC+ABAC / RLS / Audit | ⚠️ 부분 — TLS는 web만 (MQTT plain), JWT verify on, **RLS 미적용 (Phase 6+)**, **Audit 미구현** | DEPLOYMENT_AND_USAGE_GUIDE.md:887 |
| 34 | RLS 적용 검토 | 6 | gateways/sensor/actuator/telemetry/commands/audit_logs RLS | ❌ 미구현 (Phase 6 연기) | diagram 06 L5 명시 |
| 35 | 운영 관리 (백업/모니터링/장애대응) | 1+ | pg_dump 매일, gateway online 모니터링 | ⚠️ 부분 — pg_dump는 수동 명령만, **자동 백업 cron/timer 없음**, offline 감지 OK | scheduler/jobs/offline_detector.py |
| 36 | 개발 로드맵 (1-7단계) | 전체 | 1: 인프라, 2: 다중GW권한, 3: Sensor Profile, ... | ⚠️ **편차** — 코드/문서는 "Phase 0/1/2/3..."로 0-based, plan은 1-7 | README.md:18, diagram 07 |
| 37 | 테스트 계획 | 전체 | 22 시나리오 | ⚠️ 부분 — 7건 smoke + 일부 unit. **보안 테스트 6건 자동화 없음** | smoke_test.sh |
| 38 | 라이선스 검토 | 7 | OSS Notice + SBOM | ❌ 미구현 (Phase 7 연기) | README.md:57 |
| 39 | 최종 구현 우선순위 | 전체 | 최우선 6 + 중간 6 + 제품화 6 | ⚠️ 일치도 검토 — 1-4번은 ✅, 5-6은 부분 | |
| 40 | 최종 결론 | 전체 | 7가지 설계 반영 + 권장 stack | ✅ 비전 일치 | plan.md:2150-2165 |
| 41 | 참고 출처 | 전체 | 9 외부 링크 | ✅ 그대로 | |

**요약:**
- **Phase 0/1/2 약속 中 구현률 ~75%** (35 section 中 ~26 구현 또는 부분 구현)
- 미구현은 의도된 Phase 3-7 deferral 다수
- §12 gateway_profiles, §16 actuator_profiles, §22 alarm_rules, §35 자동 백업, §36 phase 번호 체계 5건이 plan과 명시적 차이
- **§36 phase number 시스템 충돌** = 가장 큰 정합성 hole

---

## B. README 정확성

| 항목 | 약속 | 검증 결과 | 라인 |
|---|---|---|---|
| `gateway/` 디렉터리 | Go gateway agent | ✅ install-pi4.sh:73-75 build | README.md:11 |
| `hal/` 디렉터리 | C HAL shared library | ✅ install-pi4.sh:59 make | README.md:12 |
| `shared/` | Sensor Profile JSON Schema | ✅ install-pi4.sh:80 복사 | README.md:13 |
| `deploy/` | systemd unit + scripts | ✅ deploy/{systemd,scripts}/ | README.md:14 |
| `docs/` | 운영/설계 문서 | ✅ docs/ 8 파일 + diagrams/ 9 파일 | README.md:15 |
| Phase 0 acceptance #1: 1초 내 ready | systemd start → ready | ⚠️ 검증 자동화 부재 — smoke #1 is-active만 (시간 미측정) | README.md:23 |
| Phase 0 acceptance #2: 10초 주기 publish | telemetry 10s | ✅ smoke #3 round trip | README.md:24 |
| Phase 0 acceptance #3: command 1초 내 toggle | command latency | ⚠️ 부분 — smoke #4 executed 확인 (latency 측정 안 함) | README.md:25 |
| Phase 0 acceptance #4: SIGSTOP → 30초 내 재시작 | watchdog | ✅ smoke #6 (45초 budget) | README.md:26 |
| Phase 0 acceptance #5: 24시간 burn-in | RSS<5% | ⚠️ 수동 절차만 (PHASE0_RUNBOOK.md:153-176), CI/cron 자동화 없음 | README.md:27 |
| `mosquitto_pub` 예시 actuator_channel_id="relay-01" | command payload | ⚠️ sample-config.yaml은 `relay-vent`/`relay-spray` 사용 — README 예시는 sample 미반영 | README.md:43 vs sample:104,112 |
| `~/.gstack/projects/...` 경로 | 추가 설계 문서 | ⚠️ 외부 경로 — 본 repo에 포함 안 됨, 검증 불가 | README.md:62-63 |

**🟠 H — README mosquitto_pub 예시 (line 43) `relay-01`은 plan §16.3 예시값이지만 실제 sample-config.yaml은 `relay-vent`. 첫 사용자 잘못 안내.**

---

## C. PHASE0_RUNBOOK / PI4_SETUP / EMMC_FLASH 발견사항

### C.1 PHASE0_RUNBOOK.md
- **L77 actuator subscribe 명령**: ✅ smoke_test.sh:62와 일치
- **L185 alarm threshold 표**: Phase 0에는 없는 기능 명시. "Phase 4 이연" 명시되어 OK, 단 섹션 제목이 마치 구현된 듯 오해 소지
- **L137 eMMC vs microSD 부팅 시간**: 측정 근거 불명. iot-gateway.service 부팅 timeout 설정 없음
- **L211 자동 제어 시나리오 ASCII diagram**: alarm rule engine 호출이 plan §22 (Phase 4 연기). 문서 신뢰도 저하 위험
- 🟡 **`local_ready_timeout: 30`** (sample-config.yaml:14) 키 코드 사용 검증 필요

### C.2 PI4_SETUP.md
- **L74-87 결선 표 (Pin 11 BCM 17, Pin 13 BCM 27)**: ✅ sample-config.yaml:107,115와 일치
- **L150 git clone `<YOUR_REPO_URL>`**: placeholder. README.md:33도 동일 — 사용자가 실제 URL 모름. 🟡 **placeholder 명시 필요**
- **L61 `dd if=raspios-lite-arm64.img`**: 실제 파일명 placeholder. EMMC_FLASH.md:71과 일관성 부족
- **L26-30 CM4 Lite 모델 표**: "❌ Phase 0 부적합" 표시한 CM4002000은 RAM 2GB이지 eMMC 0이 문제 — 표 해석 헷갈림

### C.3 EMMC_FLASH.md
- **L16 `apt-get install build-essential`**: ✅
- **L41 `sudo ./rpiboot`**: ✅
- **L113 `commit=60` mount option**: ✅ 정상
- **L165-173 백업 복원**: SQLite `.dump` → 새 OS 부팅 후 복원. install-pi4.sh가 `/var/lib/iot-gateway/local.db` 자동 생성 안함 → service 한 번 기동 필요. 문서 명시 없음
- 🟡 **L202 명명 규칙 자기 모순**: 정리 필요

---

## D. HAL_ABI.md vs gw_hal.h

| 항목 | HAL_ABI.md | gw_hal.h | 일치? |
|---|---|---|---|
| GW_OK = 0 | ✅ | line 27 | ✅ |
| GW_ERR_TIMEOUT = -1 | ✅ | line 28 | ✅ |
| GW_ERR_CRC = -2 | ✅ | line 29 | ✅ |
| GW_ERR_IO = -3 | ✅ | line 30 | ✅ |
| GW_ERR_INVALID = -4 | ✅ | line 31 | ✅ |
| GW_ERR_NOT_INIT = -5 | ✅ | line 32 | ✅ |
| GW_ERR_BUSY = -6 | ✅ | line 33 | ✅ |
| GW_ERR_PERM = -7 | ✅ | line 34 | ✅ |
| **GW_ERR_INTERNAL = -99** | ❌ HAL_ABI.md 표에 빠짐 | line 35 존재 | ⚠️ doc 누락 |
| `gw_hal_init/cleanup/version` | ✅ | line 41/44/47 | ✅ |
| `gw_gpio_*` | ✅ | line 55-83 | ✅ |
| `gw_rs485_*` | ✅ | line 96-113 | ✅ |
| `gw_watchdog_*` | ✅ | line 122-128 | ✅ |
| `gw_modem_*` | ✅ "Phase 0 stub" 명시 | line 136-142 | ✅ |
| `gw_modem_reset_soft` 시그니처 | doc은 시그니처 없음 | line 139 | 🟡 추가 권장 |
| ABI 변경 정책 | ✅ HAL_ABI.md:96-101 | header 없음 | ✅ doc 전용 |
| Cgo binding 예시 | ✅ HAL_ABI.md:104-114 | header N/A | ✅ doc 전용 |

**🟡 M — HAL_ABI.md에 GW_ERR_INTERNAL = -99 추가 필요.**

---

## E. DEPLOYMENT_AND_USAGE_GUIDE 분석

**가정 Phase**: 혼재 — Phase 0 (Gateway agent) + Phase 1 (인프라) + Phase 2 (server app). 문서 §5에서 명시.

**TOC**: 0(Q&A) / 1(시스템 한눈에) / 2(사전 요구사항) / 3(Phase 1 인프라) / 4(Phase 2 server app) / 5(Phase 0 Gateway) / 6(사용 가이드 — Swagger) / 7(운영 작업) / 8(Troubleshooting) / 9(현재 한계) / 10(빠른 reference) / 부록 A(30분 quickstart).

**주요 발견:**
- 🟠 **L165-185 VerneMQ 설치**: `vernemq-2.0.1.jammy.x86_64.deb` → Ubuntu 24.04 (noble)에 jammy 설치 의존성 문제 가능
- 🟠 **L194-241 Keycloak 26.0.5**: 수동 단계. install-server.sh에 Keycloak 설치 없음 → 별도 install-keycloak.sh 필요
- 🟡 **L286 `certbot --nginx -d iot-platform.example.com`**: example.com placeholder
- 🟠 **L319 `KC_BASE_URL=https://iot-platform.example.com`**: install-server.sh:15 default `http://127.0.0.1:8080`. 순서 의존성 문서 명시 약함
- 🟡 **L340-355 PG user 생성**: install-server.sh가 자동 생성 못한다 명시 (왜 자동화 안 했나 의문)
- 🟠 **L417-431 JWT 토큰 발급**: audience mismatch 시 401. mapper 수동 설정 별도 필요 (L834에만 troubleshooting 언급)
- 🟠 **L443-447 첫 user provisioning SQL**: ✅ 정답 (REVIEW C2 fix 후)
- 🟡 **L621 sensor profile body**: `$(cat shared/examples/...)` cwd 의존
- 🟡 **L778-780 pg_dump cron**: 안내 텍스트만, timer unit 미제공
- 🔴 **L798-815 사용자 추가 절차**: 3-step 분리 (Keycloak UI + DB INSERT × 2). 일관성 깨짐 위험
- 🟡 **L887 MQTT TLS Phase 7**: 정직하게 명시 ✅
- 🟡 **L957 `/etc/iot-gateway/config.yaml`**: ✅ install-pi4.sh:11-12와 일치
- 🟡 **L996 부록 A 체크리스트**: 30분 안에 안 끝남 (rpiboot 5-10분 추가)

---

## F. 다이어그램 ↔ 코드 정합성

### F.1 01_system_concept
**라벨:** USER LAYER (5 role) / WEB PORTAL (4 화면) / SELF-HOSTED SERVER (8 컴포넌트) / MQTT TOPIC (publish 7 + subscribe 3) / GATEWAY (Go agent + cgo + libgw_hal.so + 로컬 mosquitto + GW-N) / FIELD I/O (6-in-1 센서 + 환기팬 + 살균기 + 로봇청소기).

**매칭:**
- ✅ Server 6/8 구현 (web portal, prometheus 제외)
- ✅ Gateway 5 모듈 (mqtt/sensor/actuator/localdb/health) — diagram 02와 1:1
- ⚠️ "로봇청소기 (Phase 4+)"는 코드 없음, plan에도 없음
- ⚠️ 01_system_concept.md:34 "React + Vite SPA" — 미구현
- 🟡 plan §3.4 7개 systemd vs 다이어그램 8개 (storage 추가)

### F.2 02_detailed_architecture
**라벨:** server 7 모듈 + gateway internal (`internal/mqtt/client.go` 등) + libgw_hal.so 5 source + WDT 3-layer + 부팅 14단계.

**매칭:**
- ✅ `internal/{mqtt,sensor,actuator,localdb,health}` 모두 존재
- ❌ **`internal/ruleengine`** — diagram 명시 but plan §22 Phase 4 연기 → **다이어그램이 미구현 모듈 표시 = doc 부풀리기**
- ⚠️ `platform_r1124.c` Phase 1+ stub — HAL_ABI.md:45와 일치
- ✅ paho.mqtt.golang autoreconnect/LWT/QoS 1/clean_session=false — sample 일치
- 🟡 "uvicorn workers=4" 단언 → 실제 코드 검증 필요
- ⚠️ env file 명명이 plan §6과 다름 (3개 vs 6개)

### F.3 03_data_flow_telemetry
**라벨:** 7 actor lifeline (Sensor / C HAL / sensor-service / MQTT / Worker / PostgreSQL / Web Portal) + 8 step + payload JSON + offline 분기 box.

**매칭:**
- ✅ `gw/{id}/telemetry` topic + JSON envelope (plan §20.1과 일치)
- ✅ Worker → INSERT + UPSERT
- ⚠️ **"⑧ Web Portal ECharts 갱신"** Phase 3 미구현. diagram이 마치 동작하는 듯 표시
- ⚠️ 오프라인 분기 box: max_queue_rows 100000, retention 7일 ✅. priority order plan §28.4와 일치

### F.4 04_data_flow_command
**라벨:** 8 actor + 11 step + safety check box (idempotency / expires / channel exists / max_on_duration) + auto OFF box.

**매칭:**
- ✅ Command request payload schema plan §21.2와 일치 + smoke #4-5
- ✅ Safety check 4 항목 — smoke #5 expired 거부 검증
- ⚠️ **"② User → Web Portal (React)"** Phase 3 미구현. 실제는 Swagger/curl
- ✅ command/request + command/response topic
- ✅ ⑪ `defer hal.AssertSafeState()` ABI 일치
- 🟡 ⑨ Worker → DB UPDATE — REVIEW에서 확인됨

### F.5 05_failure_modes
**10 failure × 4열:** RS485 invalid CRC / USB-RS485 disconnect / cgo HAL segfault (CRITICAL) / Application hang (CRITICAL) / MQTT broker disconnect / SQLite full (CRITICAL) / Expired command / Relay never released (CRITICAL) / +2 (잘림).

**검증:**
- ✅ F1: GW_ERR_CRC 일치, test_rs485_pty.c 인용
- ⚠️ F2 USB unplug: smoke #4 인용 부정확 (실제 #4는 command round trip — manual unplug 자동화 없음)
- ✅ F3: defer hal.AssertSafeState (NC LOW) + Restart=always — service 일치
- ✅ F4: smoke #6 (kill -SIGSTOP)
- ✅ F5: LWT + autoreconnect + smoke #7 (mosquitto restart)
- ✅ F6 SQLite full: max_queue_rows 100000 ✅. Test sqlite_test.go::TestDropOldest 존재 여부 미검증
- ✅ F7-F8: smoke #5 + sample-config max_on_duration_sec 일치
- 🟡 다이어그램 잘림 — F9, F10 미확인

### F.6 06_security_layers
**8 layer:** L1 ufw → L2 TLS → L3 Keycloak OIDC → L4 Backend RBAC+ABAC → L5 PostgreSQL RLS (Phase 6+) → L6 MQTT ACL (Phase 7) → L7 Command Safety → L8 Electrical Fail-Safe.

**검증:**
- ✅ L1: install-pi4.sh:122-124, DEPLOYMENT_AND_USAGE_GUIDE.md:127-130
- ⚠️ L2 "MQTT TLS는 Phase 7부터" 명시 ✅
- ✅ L3 Keycloak: install-server.sh:64-97 + JWT verify on
- ✅ L4 Backend: auth.py 인용. ABAC는 부분 (RBAC만)
- ❌ **L5 RLS (Phase 6+)**: 미구현 명시 ✅, 그러나 다이어그램은 동작하는 듯 표시
- ❌ **L6 MQTT ACL (Phase 7)**: install-pi4.sh `allow_anonymous true`
- ✅ L7-L8: smoke #5 + HAL_ABI.md:8-11
- 🟡 **REVIEW C2 (JWT verify default OFF)가 다이어그램 L3에 반영 안 됨**
- 🟡 audit_logs 테이블 (우하단 dashed) 코드 부재 (Phase 6)

### F.7 07_phase_roadmap
**8 column:** P0 (SW Validation, 현재 ✅) → P1 (Server 인프라) → P2 (다중 Gateway 권한) → P3 (Sensor Profile) → P4 (Actuator) → P5 (Config Versioning + OTA) → P6 (관리 편의 + RLS) → P7 (제품화).

**검증 vs plan §36:**
- 🔴 **체계 충돌**: plan §36은 1-7. diagram 07은 0-7. plan §36 미갱신
- → README.md:18 "Phase 0", DEPLOYMENT_AND_USAGE_GUIDE.md §9 "Phase 3+" 모두 0-based 사용. **plan §36이 stale**
- 🔴 **Phase 2 정의 충돌**: plan/diagram = "권한 모델" vs 운영 docs = "backend skeleton" — 정의 자체가 분기
- ⚠️ "P0 → P1: smoke 7/7 PASS + 24hr burn-in" — README acceptance와 일치 ✅
- ⚠️ "P2 진입조건: 첫 customer 인터뷰 완료" — DEPLOYMENT_AND_USAGE_GUIDE.md:893-896과 다름

---

## G. 배포 스크립트 ↔ systemd ↔ runbook 일관성

| 항목 | install-pi4.sh | iot-gateway.service | sample-config.yaml | RUNBOOK | 일치? |
|---|---|---|---|---|---|
| binary path | `/opt/iot-gateway/bin/gateway-agent` (75) | line 15 동일 | n/a | DEPLOY:917 | ✅ |
| config path | `/etc/iot-gateway/config.yaml` (84) | `--config /etc/...` (15) | n/a | RUNBOOK:24 | ✅ |
| user/group | iot:iot + dialout, gpio (47,50) | User=iot Group=iot SupplementaryGroups=dialout gpio (9-11) | n/a | PI4_SETUP:184 | ✅ |
| WatchdogSec | n/a | 30 (18) | sd_notify_interval_sec: 10 (32) | RUNBOOK:83 "30초 후 재시작" | ✅ |
| binary lib 위치 | LIB_DIR=/var/lib/iot-gateway (14) | ReadWritePaths=/var/lib/iot-gateway (29) | db_path: /var/lib/iot-gateway/local.db (26) | RUNBOOK:27 | ✅ |
| log 디렉터리 | LOG_DIR=/var/log/iot-gateway (14) | StandardOutput=journal (35) — log dir 미사용 | (logging은 journal로) | EMMC_FLASH:148 logrotate config | 🟡 **불일치** — install이 `/var/log/iot-gateway/` 만들지만 service는 journal로만. logrotate는 수동 |
| LD_LIBRARY_PATH | install 후 ldconfig (63) | `LD_LIBRARY_PATH=/usr/local/lib` (14) | n/a | n/a | ✅ |
| Type=notify | n/a | Type=notify (8) | n/a | RUNBOOK:91 sd_notify | ✅ Gateway 측은 1초 ready 검증 |
| MQTT broker URL | mosquitto local 1883 (96-102) | n/a | broker: tcp://127.0.0.1:1883 (17) | RUNBOOK:34 mosquitto_sub | ✅ |
| MQTT auth | allow_anonymous true (98) | n/a | (없음 — anonymous) | DEPLOY:172-185 (Phase 1 password file) | 🟡 **편차** — Phase 0 anonymous OK, server-gateway 통합 시 sample-config에 username/password 부재 |

**서버 측:**

| 항목 | install-server.sh | iot-backend.service | 비고 |
|---|---|---|---|
| install prefix | `/opt/iot-platform/server` (9) | WorkingDirectory 일치 (11) | ✅ |
| env file | `/etc/iot-platform/{name}.env` (110-130) | EnvironmentFile (12) | ✅ |
| binary | `.venv/bin/iot-backend` (13) | ExecStart (13) | ✅ |
| WatchdogSec | n/a | 30 (15) | 🔴 **REVIEW C1 — sd_notify 코드 없음 → 30초 무한 재시작** |
| user/group | iot (44) | iot (9-10) | ✅ |
| MemoryMax | n/a | 512M (28) | 🟡 worker/scheduler alarm 처리 시 부족 가능 |
| .pg_password | /etc/iot-platform/.pg_password (100, 0600 root:iot) | n/a | DEPLOY:951 일치 |
| Keycloak client | iot-backend client + secret (64-97) | KC_AUDIENCE=iot-backend in env | ✅ |
| alembic upgrade | line 137-140 | (start time 미실행) | DEPLOY:336 자동 + L353 fallback |

**🔴 C2 (REVIEW)** — server iot-backend.service의 Type=notify + WatchdogSec=30이 코드 sd_notify 미구현 상태에서 부팅 직후 30초마다 재시작. install-server.sh sleep 5초 << WatchdogSec 30 → silent failure.

---

## H. 누락된 다이어그램 (개발 가속용)

| 다이어그램 | 근거 (왜 필요) | 예상 작성 시간 |
|---|---|---|
| **DB ER diagram** | plan §10 mermaid 일부, alembic 0001이 SoT인데 diagram 없음. 12+ 테이블 관계 | 60분 |
| **MQTT topic 토폴로지** | plan §19 11종 topic, diagram 01 ④에 일부. publish 7 + subscribe 3 + ACL 매핑 + Worker wildcard 패턴 | 30분 |
| **Keycloak realm 구조도** | plan §9 + diagram 06 L3에 텍스트만. realm + group + role + client + audience mapper 관계도 | 45분 |
| **배포 토폴로지** | server (단일) + N gateway (LAN) + customer 외부 (HTTPS) + 방화벽 port. plan §32에 흩어짐 | 30분 |
| **Sensor Profile schema 흐름** | shared/sensor_profile_schema.json (server pydantic ↔ gateway Go) + 등록 → DB → desired_config → 적용 → reported 회신 | 45분 |
| **Watchdog 3-layer time sequence** | diagram 02 + 06에 텍스트, 실제 timeline (kernel 15s vs systemd 30s vs application defer) 시각화 없음 | 30분 |

**우선순위:** DB ER (가장 큰 payoff) > MQTT topology > Keycloak realm > 배포 topology.

---

## I. 발견 이슈

### 🔴 CRITICAL

#### C1. Phase number 체계 충돌 (plan §36 1-7 vs README/diagram 0-7)
**위치:** plan.md §36.1-36.7 (1823-2017) ↔ README.md:18, diagrams/07_phase_roadmap.excalidraw, DEPLOYMENT_AND_USAGE_GUIDE.md §9.
**증상:** plan은 1-based, 운영 docs는 0-based. **Phase 2 정의 충돌:** plan §36.2 = "다중 Gateway 권한", 운영 docs = "Backend API + Worker + Scheduler".
**근거:** plan.md:1853 vs DEPLOYMENT_AND_USAGE_GUIDE.md:6.
**영향:** 신규 개발자/계약자 혼란. PR/이슈의 "Phase X" 의미가 사람마다 다름.
**해결:** plan §36 0-based로 갱신 + Phase 2 정의 명확화.

#### C2. iot-backend.service Type=notify + WatchdogSec=30 — 코드 sd_notify 미구현 (REVIEW C1 재확인)
**위치:** server/deploy/systemd/iot-backend.service:8,15.
**증상:** 부팅 후 30초마다 재시작 무한 루프. install-server.sh:151-164 sleep 5초 << WatchdogSec 30 → silent failure.
**해결:** REVIEW 권장 (B) — `python-systemd` + main.py lifespan에 READY + asyncio task로 WATCHDOG.

#### C3. DEPLOYMENT_AND_USAGE_GUIDE 사용자 추가 (3-step 분리)
**위치:** DEPLOYMENT_AND_USAGE_GUIDE.md §7.5 (798-815).
**증상:** Keycloak admin UI + DB INSERT users + DB INSERT user_gateway_permissions. 중간 fail 시 일관성 깨짐.
**해결:** add-user.sh 스크립트 또는 backend `/api/admin/users` POST endpoint + transaction.

#### C4. install-server.sh가 Keycloak realm/role/group 자동 생성 안 함
**위치:** install-server.sh:64-97 (client만), DEPLOYMENT_AND_USAGE_GUIDE.md:236-240 (수동).
**증상:** plan §9 + diagram 06 L3 약속과 달리 수동 작업. 복구/재배포 시 매번 반복.
**해결:** provision-keycloak.sh 분리 추가 (kcadm.sh로 realm + 7 role + 4 group + audience mapper 자동).

### 🟠 HIGH

#### H1. README mosquitto_pub 예시 actuator_channel_id 불일치
**위치:** README.md:43 vs sample-config.yaml:104,112.
**증상:** README는 `relay-01`, sample은 `relay-vent`/`relay-spray`. 첫 사용자 잘못 안내.
**해결:** README를 sample-config 값으로 일치.

#### H2. install-pi4.sh anonymous mosquitto vs DEPLOYMENT_AND_USAGE_GUIDE password file
**위치:** install-pi4.sh:97-101 vs DEPLOY:172-185.
**해결:** sample-config.yaml에 주석 처리된 username/password + DEPLOY §5.4에서 명시.

#### H3. DEPLOYMENT_AND_USAGE_GUIDE Ubuntu 24.04에 jammy(22.04) deb
**위치:** DEPLOY:168 `vernemq-2.0.1.jammy.x86_64.deb`.
**해결:** noble용 .deb 또는 다른 install 방식 + version pinning.

#### H4. diagram 02 `internal/ruleengine` 표시 — 코드 부재 가능성
**위치:** docs/diagrams/02_detailed_architecture.excalidraw rule_mod box.
**해결:** rule_mod box "(Phase 4 stub)" 또는 dashed.

#### H5. Telemetry partition 하드코딩 — 2026-07 이후 INSERT 실패 (REVIEW H1)
**위치:** server/alembic/versions/0001_initial.py:194-196.
**증상:** 현재 2026-05-04 → 약 2개월 시한폭탄.
**해결:** DEFAULT partition + scheduler N+1, N+2 자동.

#### H6. Phase 2 정의 분기
C1과 동시 처리.

#### H7. DEPLOYMENT_AND_USAGE_GUIDE 자동 백업 timer/cron 미제공
**위치:** DEPLOY:778-783 (pg_dump 명령만), plan §35.1.
**해결:** deploy/systemd/iot-backup.{service,timer} 추가.

#### H8. diagram 06 L5 (RLS) + L6 (MQTT ACL) 미구현 표시 부족
**위치:** 06_security_layers.excalidraw L5_t, L6_t.
**증상:** Phase 6+/7 텍스트는 박스 내부지만 visual weight 동일 → 마치 8 layer 모두 active.
**해결:** Phase 6+/7 박스를 dashed border + opacity 50%.

### 🟡 MEDIUM

#### M1. HAL_ABI.md 표에 GW_ERR_INTERNAL = -99 누락
docs/HAL_ABI.md:14-22 vs hal/include/gw_hal.h:35.

#### M2. README "Phase 0 acceptance #1: 1초 내 ready" 자동 검증 부재
README.md:23, smoke_test.sh #1.

#### M3. README + PI4_SETUP placeholder `<YOUR_REPO_URL>`
README.md:33, PI4_SETUP.md:150, EMMC_FLASH.md:101, DEPLOY:315,489.

#### M4. PHASE0_RUNBOOK 자동 제어 시나리오 (Phase 4 미구현 표시 부족)
PHASE0_RUNBOOK.md:211-238.

#### M5. EMMC_FLASH.md L202 명명 규칙 자기 모순

#### M6. diagram 02 server backend "uvicorn workers=4" 단언
실제 코드 검증 필요.

#### M7. install-pi4.sh LOG_DIR vs service journal 불일치
logrotate config 자동 배포 또는 LOG_DIR 제거.

#### M8. sample-config.yaml `local_ready_timeout: 30` 키 사용 검증 필요

#### M9. DEPLOYMENT_AND_USAGE_GUIDE 시간 추정 (30-60분) 낙관적
60-120분으로 갱신.

#### M10. plan §19.3 publish 권한 7 vs §19.4 subscribe 3 — 합 10 (실제 11 중 log/upload 누락)

#### M11. diagram 05 F2 test cover 잘못 인용 (smoke #4가 USB unplug 아님)
05_failure_modes.excalidraw f2c vs smoke_test.sh:55-99.

### 🔵 BETTER ALTERNATIVES

#### B1. install-server.sh가 PostgreSQL DB user 생성 통합

#### B2. plan에 phase별 "이미 구현 / 미구현" 태그 추가
각 헤더에 `[Phase X | Status: ✅/⚠️/❌]`.

#### B3. DB ER 다이어그램 자동 생성 (alembic → mermaid/dbml)
`eralchemy` 또는 `dbml-cli`.

#### B4. diagram에 "Last verified: <date>, against commit <sha>" 메타데이터

#### B5. add-user.sh + provision-keycloak.sh 보조 스크립트 (C3, C4 fix)

---

## J. 권장 수정 우선순위

| 순위 | 항목 | 작업 위치 | 예상 시간 |
|---|---|---|---|
| 1 | C1: Phase 번호 체계 통일 | plan.md §36 | 90분 |
| 2 | C2: sd_notify 구현 (REVIEW C1) | server/app/main.py + pyproject.toml | 60분 |
| 3 | H5: telemetry partition DEFAULT + scheduler ahead | server/alembic + scheduler | 60분 |
| 4 | C4: provision-keycloak.sh | server/deploy/scripts/ | 90분 |
| 5 | C3: add-user.sh | server/deploy/scripts/ | 60분 |
| 6 | H1: README relay-01 → relay-vent | README.md:43 | 5분 |
| 7 | H2: sample-config username/password 주석 | deploy/sample-config.yaml + DEPLOY §5.4 | 15분 |
| 8 | H4: diagram 02 ruleengine "Phase 4 stub" | diagrams/02_detailed_architecture.excalidraw | 20분 |
| 9 | H3: VerneMQ noble (24.04) 안내 | DEPLOY:168 | 30분 |
| 10 | H7: deploy/systemd/iot-backup.{service,timer} | server/deploy/systemd/ | 60분 |
| 11 | H8: diagram 06 L5/L6 dashed border | diagrams/06_security_layers.excalidraw | 10분 |
| 12 | H6: Phase 2 정의 명확화 (C1과 동시) | plan + DEPLOY §1 | 15분 |
| 13 | M1-M11 잡일 batch | 여러 docs | 90분 |
| 14 | DB ER + MQTT topology + Keycloak realm 다이어그램 추가 | docs/diagrams/08-10 | 150분 |

**총 예상 시간:** 약 12-13시간 (1.5 working day).

---

## K. Conclusion

**핵심 발견:** plan/diagrams는 "vision/aspirational" 모드, 운영 docs (DEPLOYMENT_AND_USAGE_GUIDE + RUNBOOK)는 "현실 모드"로 분기. 다이어그램 7종은 시각적 완성도는 높으나 미구현 컴포넌트 (ruleengine, Web Portal, RLS, MQTT ACL)가 active 컴포넌트와 동일 visual weight로 표시되어 새 개발자/계약자가 "이미 구현됐다"고 오해할 위험. plan §36 phase 1-7 numbering이 README/diagram/운영 docs의 0-7과 충돌하는 것이 가장 큰 doc-truth 균열 (Phase 2 정의 자체가 분기). 41 섹션 中 Phase 0-2 약속은 ~75% 구현 (의도적 deferral 다수), 단 §12/§16/§22/§35/§36 5건은 plan과 코드 양쪽 다 "다음 phase" 표기 부재 = 의도적 deferral인지 망각인지 모호.

**다음 sprint 권장:**
1. **plan §36 갱신을 최우선** — Phase 0 추가 + Phase 2 정의 + 각 섹션 헤더 status 태그. 90분 투자로 후속 cross-check 비용 감소.
2. **DEPLOYMENT_AND_USAGE_GUIDE.md를 단일 SoT로** — 1007줄로 가장 정확. 단 사용자 추가 (C3) + Keycloak provisioning (C4) 자동화 스크립트가 추가되면 본 doc도 짧아짐.
3. **다이어그램 추가 우선순위는 DB ER → MQTT topology → Keycloak realm**. 현재 7개가 "system view"에 편중, "data view" 약함.
