# IoT Gateway Server (Phase 0 — CM4/Pi 4 BCM2711 Validation)

산업용 환경 모니터링 + 방제 IoT Gateway 제품의 Phase 0 (Raspberry Pi BCM2711 family) 소프트웨어 검증 환경.

**권장 하드웨어:** CM4 4GB Lite + eMMC 32GB + Waveshare CM4-IO-BASE-B (eMMC boot, Phase 1 R1124-10과 같은 SoC + storage class)
**대안:** Pi 4 4GB + microSD (저예산)

## 구조

```
gateway/    Go gateway agent (cgo HAL binding + -tags simulation 빌드 지원)
hal/        C/C++ HAL shared library (libgw_hal.so)
server/     Python FastAPI 서버 (backend + worker + scheduler + alembic)
shared/     Sensor Profile JSON Schema (server↔gateway SoT)
deploy/     systemd unit + install 스크립트 (실 Pi + 시뮬레이션 양쪽)
docs/       운영/설계 문서 + 다이어그램 + 통합 리뷰
```

## Phase 0 목표

CM4(eMMC, 권장) 또는 Pi 4(microSD) + USB-RS485 + 릴레이 모듈 1개로 다음 end-to-end loop 검증:

1. `systemctl start iot-gateway` → 1초 내 ready
2. Modbus RTU 가스 센서 값 10초 주기 MQTT publish
3. 외부 MQTT command publish → 1초 내 릴레이 toggle
4. SIGSTOP → 30초 내 systemd watchdog 재시작
5. 24시간 burn-in 무중단

## 빠른 시작

### 옵션 A — **하드웨어 없이 시뮬레이션** (Ubuntu 22.04/24.04 한 대에서 전체 wire 흐름 검증)

```bash
sudo bash deploy/scripts/install-sim.sh        # 5-15분 — mosquitto + postgres + 서버 + sim gateway + web (nginx)
sudo bash deploy/scripts/sim-verify.sh         # 7단계 자동 검증 (PASS/FAIL)
mosquitto_sub -h 127.0.0.1 -t 'gw/+/#' -v      # 합성 telemetry 실시간 관찰
```

브라우저에서 `http://localhost/` → `/login` → `sudo /opt/iot-sim/bin/sim-fake-jwt` 출력 붙여넣기 → Apple Home 톤 대시보드.

상세: `docs/SIMULATION_GUIDE.md`, `docs/USER_DASHBOARD_GUIDE.md`.

### 옵션 B — 실 라즈베리파이/CM4 + 센서 (Phase 0 production validation)

```bash
# Step 1: OS 굽기
#   CM4 (eMMC): docs/EMMC_FLASH.md 참조 (rpiboot + USB-C)
#   Pi 4 (SD): Raspberry Pi Imager로 microSD에 굽기

# Step 2: ssh 접속 후 설치
sudo bash deploy/scripts/install-pi4.sh   # CM4도 동일 (BCM2711 family)
sudo systemctl start iot-gateway
sudo journalctl -fu iot-gateway

# Step 3: PC에서 (mosquitto_clients 설치)
mosquitto_sub -h <ip> -t 'gw/+/#' -v
mosquitto_pub -h <ip> -t 'gw/test01/command/request' \
  -m '{"command_id":"c1","action":"ON","actuator_channel_id":"relay-vent","require_ack":true}'
```

## 문서

- `docs/SIMULATION_GUIDE.md` — **하드웨어 없이 단일 호스트 wire 검증** (`install-sim.sh`)
- `docs/PHASE0_RUNBOOK.md` — 실 Pi 운영 절차
- `docs/PI4_SETUP.md` — 하드웨어 BOM + OS 셋업 (CM4 eMMC + Pi 4 microSD 양쪽)
- `docs/EMMC_FLASH.md` — CM4 eMMC OS 굽기 (rpiboot 절차)
- `docs/HAL_ABI.md` — C HAL ABI 명세
- `docs/reviews/00_OVERVIEW.md` — 전체 구현 통합 점검 보고서
- `docs/diagrams/` — 시스템 다이어그램
  - `01_system_concept.md` — 전체 시스템 개념 구성도 (6-layer top-down)

## 라이선스

Apache 2.0 예정 (Phase 7 OSS Notice 시점에 확정).

## 배경

전체 41-section 계획서: `cm4_iot_gateway_no_docker_detailed_implementation_plan.md`
설계 문서: `~/.gstack/projects/iot-gateway-server/imth-r1124-design-*.md`
Phase 0 plan: `~/.gstack/projects/iot-gateway-server/imth-pi4-phase0-plan-*.md`
