# Phase 0 Runbook (운영 절차)

## 개요

Phase 0 = CM4 (eMMC, 권장) 또는 Pi 4 (microSD) + USB-RS485 + 릴레이 1개로 Gateway Agent 소프트웨어 stack 검증. SoC가 같은 BCM2711이라 코드는 동일, storage 매체만 차이.
부팅·telemetry·command·watchdog·SQLite buffer·24hr burn-in 7건.

## 빠른 명령 reference

```bash
# 시작 / 종료 / 재시작
sudo systemctl start  iot-gateway
sudo systemctl stop   iot-gateway
sudo systemctl restart iot-gateway

# 상태 / 로그
sudo systemctl status iot-gateway --no-pager -l
sudo journalctl -fu iot-gateway          # 실시간 follow
sudo journalctl -u iot-gateway --since "1 hour ago"
sudo journalctl -u iot-gateway -p err    # error만

# config 적용
sudo nano /etc/iot-gateway/config.yaml
sudo systemctl restart iot-gateway

# SQLite 큐 직접 조회
sudo sqlite3 /var/lib/iot-gateway/local.db
  > .tables
  > SELECT topic, priority, created_at FROM queued_messages ORDER BY id DESC LIMIT 10;
  > SELECT * FROM sensor_health;
  > SELECT * FROM command_log ORDER BY requested_at DESC LIMIT 10;

# MQTT 외부 모니터링 (PC에서)
mosquitto_sub -h <pi-ip> -t 'gw/+/#' -v
mosquitto_sub -h <pi-ip> -t 'gw/GW-DEV01/telemetry'
mosquitto_sub -h <pi-ip> -t 'gw/GW-DEV01/event'

# 수동 command 발행
mosquitto_pub -h <pi-ip> -t 'gw/GW-DEV01/command/request' -m '{
  "command_id": "manual-1",
  "actuator_channel_id": "relay-01",
  "action": "ON",
  "expires_at": "'$(date -u -d '+10 seconds' +%Y-%m-%dT%H:%M:%SZ)'",
  "require_ack": true
}'
```

## 부팅 흐름 (14단계)

main.go가 다음 순서로 진행:

1. config 로드 (실패 → exit 1, sd_notify STATUS=fatal)
2. HAL init (libgw_hal.so 로드, GPIO chip open, gpio group 검증)
3. Watchdog open (kernel WDT, 권한 없으면 warn 후 진행)
4. Local SQLite open + schema migrate
5. MQTT client 생성 (LWT 등록)
6. **systemd READY (sd_notify) → local-ready**
7. Sensor channels 초기화 (RS485 open + Profile 로드)
8. Actuator channels 초기화 (GPIO request_output, default state)
9. Sensor polling 루프 시작 (각 채널 별 goroutine)
10. Actuator subscribe 시작 (gw/{id}/command/request)
11. Health/heartbeat 루프 시작
12. **MQTT CONNACK 수신 → cloud-ready** (state online retained publish)
13. SIGTERM/SIGINT 대기
14. shutdown — assert_safe_state + cleanup + sd_notify STOPPING

## 정상 동작 패턴

```
[gateway-agent] 14:30:01 loaded config: gateway=GW-DEV01, sensors=1, actuators=2
[gateway-agent] 14:30:01 HAL: libgw_hal 0.1.0-pi4-phase0 (built May  3 2026 17:22:31)
[gateway-agent] 14:30:01 sd_notify READY sent (local-ready)
[gateway-agent] 14:30:01 [actuator relay-01] reserved gpio=17 initial=off
[gateway-agent] 14:30:01 [actuator relay-02] reserved gpio=27 initial=off
[gateway-agent] 14:30:01 [sensor sensor-01] polling every 10s on /dev/ttyUSB0 slave=1
[gateway-agent] 14:30:01 [mqtt] connected to tcp://127.0.0.1:1883
[gateway-agent] 14:30:01 [actuator] subscribed to gw/GW-DEV01/command/request
[gateway-agent] 14:30:11 (10초 후 첫 telemetry publish — log에는 안 찍힘, journalctl로만)
```

## 자주 마주칠 문제

### A. 부팅 직후 systemd가 30초 후 자동 재시작 루프

원인: sd_notify 가 안 보내짐 → systemd가 hang으로 판정.
확인: `journalctl -u iot-gateway` 에서 "READY" 라인 검색.

가능 원인:
1. `daemon` go module 빌드 누락 → main.go의 `daemon.SdNotify` 호출 실패
2. `Type=notify` 가 systemd unit에 없음
3. config.yaml 파싱 실패 → 14단계 도달 전 exit

해결: journalctl 첫 30초 로그 자세히 확인.

### B. MQTT 미연결 (계속 reconnecting)

```bash
sudo systemctl status mosquitto
mosquitto_pub -h 127.0.0.1 -t test -m "ping"     # broker 자체 검증
sudo ufw status                                  # 1883 허용 확인
```

mosquitto가 죽었으면 `sudo systemctl start mosquitto`. 망 외부에서 접근 시 ufw rule 추가.

### C. Modbus 응답 없음 (telemetry 안 옴)

확인 순서:
1. `ls -la /dev/ttyUSB0` — 디바이스 존재 + iot 사용자 group dialout
2. `dmesg | tail -20` — USB-RS485 인식 로그
3. simulator로 link layer 분리 검증 (실 센서 미사용 시 simulator 모드 사용)
4. 가스 센서 data sheet 재확인 (slave_id, baudrate, register map)

### D. 릴레이 toggle 안됨

```bash
# CLI로 직접 GPIO 제어 시도
gpioset gpiochip0 17=1
gpioset gpiochip0 17=0
```

이게 동작 안하면 결선 문제. 동작하면 actuator-service의 cgo binding 또는 권한 문제.

### E. SQLite 크기 폭증

```bash
ls -lh /var/lib/iot-gateway/local.db
sudo sqlite3 /var/lib/iot-gateway/local.db "PRAGMA wal_checkpoint(TRUNCATE);"
sudo sqlite3 /var/lib/iot-gateway/local.db "VACUUM;"
```

retention_days를 줄이거나 max_queue_rows 한도 점검.

### F. eMMC vs microSD 운영 차이

| 항목 | eMMC (CM4) | microSD (Pi 4) |
|---|---|---|
| 부팅 시간 | 8-12초 | 12-18초 |
| Random IOPS | ★★★ | ★ |
| Write endurance | 수천 P/E cycle | 수백 P/E |
| Power-loss safety | 내장 fail-safe write | filesystem 의존 |
| 24hr burn-in 영향 | 미미 | telemetry × 8640건/일 누적 시 SD 마모 |
| 재플래시 절차 | rpiboot + USB-C | SD 빼서 imager |

**권장 운영 패턴 (eMMC):**
- `/etc/fstab` 에 `noatime,nodiratime,commit=60` 추가 (불필요 write 감소)
- `journald` 영구 저장 비활성화 (`/etc/systemd/journald.conf` Storage=volatile) — 또는 `SystemMaxUse=100M`
- SQLite WAL checkpoint 주기 (Phase 0 코드는 자동, 별도 cron 불필요)

**권장 운영 패턴 (microSD):**
- 위 동일 + `Storage=volatile` 강력 권장 (SD 카드 가장 빠른 사망 원인)
- 6개월마다 SD 카드 교체 또는 dd 백업 후 새 카드로 swap 권장

## 24시간 burn-in 절차

```bash
# 1. 시작 시점 기록
date > /tmp/burnin_start.txt
ps -o rss,vsz,etime,cmd -p $(systemctl show -p MainPID --value iot-gateway) >> /tmp/burnin_start.txt

# 2. 24시간 후 비교
date > /tmp/burnin_end.txt
ps -o rss,vsz,etime,cmd -p $(systemctl show -p MainPID --value iot-gateway) >> /tmp/burnin_end.txt
diff /tmp/burnin_start.txt /tmp/burnin_end.txt

# 3. 메시지 수 확인 (10초 주기 × 8640건/일 ± 1% = 8553-8726)
mosquitto_sub -h 127.0.0.1 -t "gw/+/telemetry" -W 60 | wc -l
# 60초 동안 6건 ± 1 정상

# 4. 에러 로그 검사
sudo journalctl -u iot-gateway --since "24 hours ago" -p err | wc -l   # 0이면 통과
sudo journalctl -u iot-gateway --since "24 hours ago" | grep -i panic   # 없어야 함

# 5. 큐 상태 (SQLite)
sudo sqlite3 /var/lib/iot-gateway/local.db "SELECT COUNT(*) FROM queued_messages;"
# 0 또는 작은 수 (네트워크 잠깐 끊김 분량)
```

합격 조건:
- RSS 증가 < 5% (메모리 누수 없음)
- error log 0
- panic 0
- queue size 가 increment 만 되지 않고 줄어듬 (flush 작동)

## 유기보호소 측정값별 권장 alarm threshold

Phase 0 본문은 alarm rule을 plan에 포함하지 않으나(Phase 4 이연), 운영 참고로 권장값 명시.

| 측정값 | 단위 | 정상 범위 | 경고 (warning) | 위험 (critical) | 근거 |
|---|---|---|---|---|---|
| **온도** | °C | 18-26 | < 10 또는 > 30 | < 5 또는 > 32 | 가축 열스트레스 임계 (KS B 6361 류) |
| **습도** | % | 40-70 | < 30 또는 > 80 | > 90 | 곰팡이·호흡기 질환 |
| **PM10** | µg/m³ | 0-80 | 80-150 | > 150 | 환경부 대기환경기준 (24h) |
| **PM2.5** | µg/m³ | 0-35 | 35-75 | > 75 | 환경부 대기환경기준 (24h) |
| **NH3** | ppm | 0-10 | 10-25 | > 25 | OSHA PEL 25 ppm, 가축 보건 권장 |
| **CO2** | ppm | 400-1500 | 1500-3000 | > 3000 | 실내공기 1000ppm, 환기 강제 3000ppm |

### 자동 제어 rule 예시 (Phase 4에서 alarm_rules 도입 시 사용)

**환기팬 자동 ON (위험 임계 초과 시):**
- NH3 > 25 ppm OR CO2 > 3000 ppm OR PM2.5 > 75 µg/m³ → relay-vent ON
- max_on_duration_sec: 600 (10분 후 자동 OFF, 다시 측정 후 재ON 가능)

**살균 분무기 트리거:**
- PM10 > 150 µg/m³ AND 마지막 분무 30분 경과 → relay-spray ON 60초

**알림 (notify):**
- 온도 > 32°C OR < 5°C → critical (가축 위험)
- 습도 > 90% AND 12시간 지속 → warning (곰팡이 위험)

### 데이터 흐름 (자동 제어 시나리오)

```
[6-in-1 센서] ──RS485 Modbus──→ [CM4/Pi 4 Gateway Agent]
                                       │
                  10초 주기 polling   │
                                       ↓
              [ HAL_rs485_modbus_read register 0-5 ]
                                       ↓
              [ Sensor Profile scale/offset 적용 ]
                                       ↓
              [ telemetry payload 6 values ──→ MQTT publish ]
                                       │
                                       ↓
                  [ 서버 Alarm Rule Engine ]
                       │             │
            (NH3 > 25)  (CO2 > 3000)
                       ↓             ↓
              [ command publish: relay-vent ON ]
                                       ↓
              [ CM4/Pi 4 actuator-service ]
                       │
                  [ HAL_gpio_set BCM17 = 1 ]
                       │
                  [ 환기팬 가동 ]
                       │
            (max_on_duration_sec=600 timer 시작)
                       ↓
                  10분 후 자동 OFF + audit event publish
```

## Phase 1 진입 조건

다음이 모두 만족되면 R1124-10 발주 + Phase 1 spec 시작:

- [ ] smoke_test.sh 7건 모두 PASS
- [ ] 24시간 burn-in 합격 (위 4개 기준)
- [ ] 첫 paying customer 또는 LOI 1건 (office-hours assignment)
- [ ] Sensor Profile JSON Schema lock 결정
- [ ] FastAPI Backend 별도 spec 시작 동의
