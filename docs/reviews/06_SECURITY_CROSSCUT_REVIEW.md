# Review: Security Cross-Cut (HAL + Gateway + Deploy + Shared)

> 작성일: 2026-05-04
> 범위: HAL(C) / Gateway(Go) / 배포 스크립트 / 공유 스키마 + 기존 server-side 리뷰 보완
> 중복 제외: REVIEW_PHASE1_PHASE2.md의 C1(sd_notify), C2(JWT verify off), H5(install-server.sh curl|sh), I2(backend MQTT user) — 해당 항목은 "[기존 리뷰 Cx/Hx 참조]"로만 표기
> 발견 이슈: 🔴 3 · 🟠 5 · 🟡 6 · 🔵 3

---

## Threat Model 요약

| Adversary | 가정한 능력 | 이 시스템에 대한 주요 위협 |
|---|---|---|
| 네트워크 공격자 | LAN 접근, MQTT 자격증명 없음 | MQTT 평문 도청, 인증 없는 command 주입, telemetry 위조 |
| 손상된 게이트웨이 | Pi root 권한 | 다른 Pi로 lateral movement, SQLite 비밀 탈취, 커널 WDT 조작 |
| 손상된 클라우드 계정 | 저권한 user | 다른 tenant relay 조작, sensor profile 공급망 주입 |
| 공급망 | 악의적 profile JSON / apt 패키지 | 자동 배포 후 모든 gateway에 악성 Modbus 명령 발생 |
| 내부자 | 운영자 권한 (SSH + MQTT 직접 접근) | 감사 로그 없이 relay 조작, 이력 은폐 |

---

## STRIDE 매트릭스

| Threat | HAL | Gateway | Deploy | Schema | Cross |
|---|---|---|---|---|---|
| Spoofing | 🟡 RS485 slave 사칭 불가 (물리 버스) | 🔴 MQTT command 발신자 무검증 (C1) | — | — | 🔴 평문 MQTT broker — 누구든 발행 가능 (C1) |
| Tampering | 🟡 FD_CLOEXEC 미설정 (M3) | 🟠 command_id 중복 검사 DB에 있으나 actuator에서 미호출 (H2) | 🟠 curl\|sh 공급망 [기존 H5 참조] | 🟠 scale 0.0 허용 → NaN 증폭 (H4) | 🟠 MQTT 평문 → telemetry 위조 (H1) |
| Repudiation | — | 🟡 command_log 미기록 (M4) | — | — | 🟡 relay 조작 감사 로그 없음 (M4) |
| Info Disclosure | 🟡 FD 상속 (M3) | 🟡 MQTT password YAML 0640 (M1), 로그 노출 (M5) | 🟡 config.yaml 0640 적절하나 sample에 plain credential (M1) | — | 🟡 heartbeat에 hostname 노출 (M5) |
| DoS | 🟡 watchdog FD timeout > kernel max (M6) | 🟠 SQLite 무한 성장 → crash (H3) | — | 🟠 length=125 고주파 polling profile (H4) | 🟠 broker down → SQLite 폭주 (H3) |
| Elevation | 🔴 /dev/watchdog root 소유, iot user 접근 불가 (C3) | — | 🔴 install-pi4.sh curl\|sh (C2) | — | — |

---

## 🔴 CRITICAL (신규)

### C1. MQTT 명령 채널 — 인증 없음, 누구든 relay ON/OFF 가능

**위치:** `gateway/internal/actuator/actuator.go:79-85`, `deploy/scripts/install-pi4.sh:94-103`

**증상:**
```go
// actuator.go:79
topic := fmt.Sprintf("gw/%s/command/request", m.gatewayID)
if err := m.mq.Subscribe(topic, m.handleCommand); err != nil { ... }
```
```bash
# install-pi4.sh:96-99
listener 1883 0.0.0.0
allow_anonymous true
```

**근거:** Phase 0 mosquitto가 `allow_anonymous true`로 `0.0.0.0:1883`에 바인딩됨. 동일 LAN에 있는 공격자는 자격증명 없이 `gw/GW-DEV01/command/request`에 임의 JSON을 발행할 수 있다. `handleCommand`는 JSON 파싱 후 `gateway_id` 매칭조차 없이 (`execute` 내에서 `req.ActuatorChannelID` 존재 여부만 확인) relay를 제어한다. `expires_at` 검증은 있지만, 공격자가 미래 시각을 설정하면 통과된다.

**공격 시나리오:**
```bash
# LAN 공격자 — credentials 불필요
mosquitto_pub -h 192.168.1.42 -t "gw/GW-DEV01/command/request" \
  -m '{"command_id":"atk1","actuator_channel_id":"relay-spray",
       "action":"ON","expires_at":"2099-01-01T00:00:00Z","require_ack":false}'
# 살균 분무기가 즉시 ON → max_on_duration(60초) 후 꺼지지만, 반복 발행 가능
```

**영향:** 가축 피해·화재 위험. 여러 번 반복 발행 시 max_on_duration bypass 가능 (매 60초마다 재발행). 공격자가 relay를 원하는 패턴으로 조작.

**해결 (단계별):**
1. **즉시 (Phase 0 현실적 최소):** mosquitto를 `127.0.0.1` 전용으로 바인딩. 서버→게이트웨이 직접 연결 시 WireGuard/VPN 터널 내부로 제한.
   ```
   listener 1883 127.0.0.1
   allow_anonymous false
   password_file /etc/mosquitto/passwd
   ```
2. **Phase 1 (VerneMQ 이전):** per-gateway VerneMQ ACL — 게이트웨이는 자신의 토픽만 subscribe/publish 가능. 서버만 `gw/+/command/request` 발행 권한.
3. **Phase 7:** TLS + X.509 클라이언트 인증서. 설계상 이미 예정됨.
4. **Gateway 측 추가 방어:** command payload에 HMAC-SHA256 서명 필드 추가. `secret`은 per-gateway 공유 키. 서버가 서명해서 발행, gateway가 검증. (TLS 이전 임시 방어층)

**검증 방법:** LAN 외부 기기에서 `mosquitto_pub`로 command 발행 → 차단 확인. ACL 위반 시 mosquitto 로그에 `not authorized` 기록.

---

### C2. install-pi4.sh — curl|sh 패턴 없지만, Go 바이너리를 repo 내에서 빌드 시 go mod download가 외부 네트워크에 의존

**위치:** `deploy/scripts/install-pi4.sh:73-75`

```bash
cd "$REPO_ROOT/gateway"
go mod download          # 외부 sum.golang.org / proxy.golang.org 호출
CGO_ENABLED=1 go build ...
```

**근거:** `go mod download`는 인터넷 연결 환경에서 외부 Go module proxy에서 패키지를 내려받는다. Pi 현장 설치 환경에서 proxy가 침해되거나 MITM이 발생하면 악성 모듈이 빌드에 포함될 수 있다. `go.sum`이 존재하나, 설치 스크립트가 `go.sum` 파일 존재 여부를 검증하지 않으며, `GONOSUMCHECK` 또는 `GONOSUMDB` 환경 변수가 설정된 경우 checksum 검증이 우회된다.

추가로, install-server.sh의 `curl -LsSf https://astral.sh/uv/install.sh | sh` [기존 리뷰 H5 참조]도 동일 계열 위험.

**영향:** 공급망 공격. 빌드된 바이너리에 backdoor 포함 가능.

**해결:**
```bash
# go.sum 존재 강제
[[ -f "$REPO_ROOT/gateway/go.sum" ]] || { echo "go.sum missing — aborting"; exit 1; }
# vendor 모드 사용 (온라인 불필요)
go mod vendor
CGO_ENABLED=1 go build -mod=vendor ...
# 또는 GOFLAGS=-mod=vendor 환경변수 설정
```
현장 설치 전 개발 환경에서 `go mod vendor` 실행 후 vendor/ 디렉터리를 배포 패키지에 포함시킨다.

**검증 방법:** 인터넷 없는 환경에서 `-mod=vendor` 빌드 성공 확인.

---

### C3. /dev/watchdog — iot 사용자 접근 권한 없음 → kernel WDT 동작 안 함

**위치:** `deploy/systemd/iot-gateway.service:9-11`, `hal/src/watchdog.c:25-28`

```ini
# iot-gateway.service
User=iot
Group=iot
SupplementaryGroups=dialout gpio
# 'watchdog' group 없음
```
```c
// watchdog.c:25
int fd = open(WDT_DEV, O_WRONLY);
if (fd < 0) {
    return (errno == EACCES || errno == EPERM) ? GW_ERR_PERM : GW_ERR_IO;
}
```

**근거:** `/dev/watchdog`은 기본적으로 `root:root crw-------` (0600) 또는 `root:root crw-r-----` 권한이다. `iot` 사용자는 `watchdog` 그룹에 속하지 않는다. `gw_watchdog_open`은 `GW_ERR_PERM`을 반환하고, `main.go:103-110`에서는 이를 `WARN` 로그로만 처리하고 계속 진행한다:

```go
// main.go:104-109
if cfg.Watchdog.KernelWDTEnabled {
    wdtFd, err = hal.WatchdogOpen(cfg.Watchdog.KernelWDTTimeoutSec)
    if err != nil {
        log.Printf("WARN: kernel watchdog disabled: %v", err)
    } else { ... }
}
```

결과: `kernel_wdt_enabled: true` 설정이지만 실제로 WDT가 열리지 않는다. 게이트웨이가 hang 상태에 빠졌을 때 systemd WatchdogSec은 정상 동작하지만, 커널 하드웨어 WDT가 비활성화된 상태이므로 systemd 자체가 hang되면 복구 불가.

**영향:** 커널 panic 또는 systemd 데드락 시 Pi가 무한 hang. 가축 모니터링이 완전 중단.

**해결:**
```bash
# install-pi4.sh에 추가
# udev rule로 watchdog 그룹 접근 허용
echo 'SUBSYSTEM=="watchdog", GROUP="iot", MODE="0660"' > /etc/udev/rules.d/99-iot-watchdog.rules
udevadm control --reload && udevadm trigger
# 또는 systemd unit에 추가
```
```ini
# iot-gateway.service
SupplementaryGroups=dialout gpio
# watchdog 접근: CapabilityBoundingSet에 CAP_SYS_BOOT 또는 udev group 방식 권장
```

**검증 방법:** `sudo -u iot ls -la /dev/watchdog` 접근 가능 확인. 서비스 시작 후 `journalctl`에 "kernel watchdog disabled" 경고 없는지 확인.

---

## 🟠 HIGH (신규)

### H1. MQTT 평문 전송 — 산업 환경 telemetry 무결성/기밀성 없음

**위치:** `gateway/internal/config/config.go:34`, `deploy/sample-config.yaml:17`

```go
// config.go:34
// Phase 0은 plain 1883, Phase 7부터 TLS
Broker string `yaml:"broker"` // tcp://127.0.0.1:1883
```
```yaml
# sample-config.yaml:17
broker: tcp://127.0.0.1:1883
```

**근거:** 현재 게이트웨이→브로커, 서버→브로커 모든 통신이 평문 TCP. 동일 네트워크의 공격자는 tcpdump로 모든 telemetry(NH3/CO2/온도)를 수신하고, command를 위조할 수 있다.

**가축 농장 맥락에서의 위험:** NH3/CO2 값이 평문으로 전송되면 경쟁 업체가 생산 데이터를 수집하거나, 규제 보고용 데이터가 위조될 수 있다.

**현실적 Phase 0 완화:** WireGuard를 게이트웨이-서버 간 tunnel로 구성하면 앱 레이어 코드 변경 없이 transport 보안 확보. Phase 7 TLS 전 임시 방어로 적합.

**해결:** WireGuard VPN 터널 구성 + mosquitto `127.0.0.1`만 바인딩 (C1 해결의 부산물). Phase 7에서 `ssl://` 브로커 URL + 클라이언트 인증서로 전환.

---

### H2. actuator — command_id 중복 실행 방지 미연결 (idempotency 미동작)

**위치:** `gateway/internal/actuator/actuator.go:138-218`, `gateway/internal/localdb/sqlite.go:207-212`

**증상:**
```go
// localdb/sqlite.go:207 — CommandSeen 함수가 존재하지만
func (d *DB) CommandSeen(commandID string) (bool, error) { ... }

// actuator.go:138 — execute()에서 CommandSeen 호출 없음
func (m *Manager) execute(req *CommandRequest) *CommandResponse {
    // command_id 중복 검사 없음
    if req.CommandID == "" { ... }
    // expires_at 검사만 있음
```

**근거:** `localdb.CommandSeen()`이 구현되어 있음에도 `actuator.execute()`에서 호출하지 않는다. MQTT QoS 1은 "at-least-once" 보장이므로 브로커 재연결 시 동일 command가 재전달될 수 있다. 이 경우 relay가 이미 OFF인 상태에서 다시 ON 명령이 중복 실행된다.

**공격 시나리오 (C1와 결합):** 공격자가 유효한 command_id를 재발행하면 반복 실행. 정상 QoS 1 재전송에서도 의도치 않은 중복 실행 발생.

**해결:**
```go
// execute() 시작 부분에 추가
if seen, err := m.db.CommandSeen(req.CommandID); err == nil && seen {
    resp.Status = "rejected"
    resp.Reason = "duplicate command_id"
    return resp
}
// 실행 후 LogCommand 호출로 기록
```

**검증 방법:** 동일 command_id로 두 번 발행 → 두 번째는 `rejected` + `duplicate command_id` 응답.

---

### H3. SQLite 오프라인 버퍼 — 브로커 장애 시 max_queue_rows 도달 후 oldest 삭제 누락

**위치:** `gateway/internal/localdb/sqlite.go:94-121`

```go
// sqlite.go:104-113
var count int
if err := d.conn.QueryRow("SELECT COUNT(*) FROM queued_messages").Scan(&count); err != nil {
    return fmt.Errorf("count: %w", err)
}
if count >= d.maxQueueRows {
    if _, err := d.conn.Exec(
        "DELETE FROM queued_messages WHERE id IN " +
        "(SELECT id FROM queued_messages WHERE priority=3 ORDER BY created_at ASC LIMIT 1000)",
    ); err != nil {
        log.Printf("[localdb] drop oldest telemetry failed: %v", err)
    }
}
```

**근거 (두 가지 문제):**

1. **경쟁 조건:** count 확인과 INSERT 사이에 잠금이 없다. 여러 goroutine이 동시에 Enqueue를 호출하면 (sensor 채널 수가 많을 때) count 체크 후 INSERT 전에 다른 goroutine이 INSERT할 수 있어 max_queue_rows를 초과한다. SQLite WAL 모드이지만 고레벨 트랜잭션이 없음.

2. **DoS via broker hang:** 공격자가 broker를 의도적으로 down시키면 (C1 환경에서 직접 SIGKILL 가능) gateway가 10초마다 telemetry를 SQLite에 쌓는다. max_queue_rows=100000 달성 후 priority=3만 삭제하는데, command_response(priority=2)와 event(priority=1)는 보호되므로 실제로는 삭제가 안 될 수 있다. 결국 SQLite 파일이 수 GB로 성장 → Pi의 SD 카드 용량 초과 → 파일시스템 full → 게이트웨이 crash.

**해결:**
```go
// 트랜잭션으로 count+insert를 원자화
// 디스크 사용량 경고(DiskUsageWarnPct)를 Enqueue 시점에 연동
// priority와 무관하게 전체 count가 max_queue_rows 80% 이상이면 오래된 모든 row 삭제
```

---

### H4. sensor profile JSON — schema 검증 없이 직접 Modbus 호출

**위치:** `gateway/internal/sensor/sensor.go:62-79`, `gateway/internal/sensor/sensor.go:171-184`

```go
// sensor.go:62 — LoadProfile
func LoadProfile(path string) (*Profile, error) {
    data, err := os.ReadFile(path)
    // ...
    var p Profile
    if err := json.Unmarshal(data, &p); err != nil { ... }
    if len(p.Measurements) == 0 { ... }  // 유일한 검증
    // modbus.function_code, register, length 범위 검증 없음
}

// sensor.go:171-183 — 실제 HAL 호출
r, err := hal.ModbusRead(c.fd, byte(c.cfg.SlaveID),
    byte(meas.Modbus.FunctionCode),  // 0xFF도 통과
    uint16(meas.Modbus.Register),    // 0 ~ 65535 무검증
    uint16(meas.Modbus.Length),      // 0도 통과 가능
    200)
```

**근거:** JSON schema 파일(`shared/sensor_profile_schema.json`)은 존재하지만 Go `LoadProfile`에서 이를 검증하지 않는다. `function_code`는 int로 파싱되며 `byte()`로 캐스팅되어 HAL에 전달된다.

악의적인 profile 예:
```json
{
  "measurements": [{
    "key": "x", "unit": "x", "data_type": "int",
    "modbus": {"function_code": 16, "register": 0, "length": 125}
  }]
}
```
- `function_code: 16` (0x10 = write multiple registers): HAL이 `function_code != 0x03 && function_code != 0x04`를 거부(`GW_ERR_INVALID`)하므로 실제 쓰기는 차단됨. 그러나 `function_code: 6` (0x06) write single register는 HAL이 차단하지 않는다 — `gw_rs485_modbus_read`는 `0x03/0x04`만 허용하지만, `gw_rs485_modbus_write`는 별도 함수이고 sensor 경로에서는 호출되지 않으므로 실질 위험은 낮음.
- **실제 위험:** `length=125`로 설정된 profile → 매 폴링마다 250바이트 Modbus 요청 발생. 10초 폴링 × 다수 채널 = RS485 버스 포화 → 정상 센서 응답 지연/누락.
- **scale=0.0** 허용: `sensor.go:74-76`에서 scale=0을 1.0으로 보정하나, schema 자체는 0.0을 허용. 위조된 profile에서 scale=Infinity를 설정하면 Go float64 overflow → `+Inf` 또는 `NaN` telemetry 발행.

**해결:** `LoadProfile`에서 `jsonschema` 라이브러리로 schema 파일 대비 검증. 또는 최소한:
```go
if meas.Modbus.FunctionCode != 3 && meas.Modbus.FunctionCode != 4 {
    return nil, fmt.Errorf("measurement %s: invalid function_code %d", meas.Key, meas.Modbus.FunctionCode)
}
if meas.Modbus.Length < 1 || meas.Modbus.Length > 125 {
    return nil, fmt.Errorf("measurement %s: length out of range", meas.Key)
}
if math.IsNaN(meas.Scale) || math.IsInf(meas.Scale, 0) || meas.Scale == 0 {
    return nil, fmt.Errorf("measurement %s: invalid scale", meas.Key)
}
```

---

### H5. install-pi4.sh — mosquitto를 0.0.0.0에 anonymous 모드로 영구 배포

**위치:** `deploy/scripts/install-pi4.sh:94-103`

```bash
cat > /etc/mosquitto/conf.d/iot-gateway-phase0.conf <<EOF
listener 1883 0.0.0.0
allow_anonymous true
...
EOF
```

**근거:** 이 설정이 `systemctl enable --now mosquitto`로 부팅 시 자동 시작되므로, Phase 0 이후 업그레이드 없이 운영하면 영구적으로 LAN에 인증 없는 MQTT 브로커가 노출된다. C1의 근본 원인.

**추가 문제:** `ufw allow 1883/tcp`로 방화벽까지 열린다. 설치 스크립트가 Phase 0 개발 편의성을 위한 설정을 production에서도 유지하게 만든다.

**해결:**
```bash
# Phase 0 설정에 경고 배너 추가
cat > /etc/mosquitto/conf.d/iot-gateway-phase0.conf <<EOF
# WARNING: Phase 0 development config. NOT for production.
# Phase 1+에서 allow_anonymous false + 인증서로 교체 필요.
listener 1883 127.0.0.1
allow_anonymous true
...
EOF
# ufw에서 1883은 LAN 서브넷만 허용
ufw allow from 192.168.0.0/16 to any port 1883/tcp
```

---

## 🟡 MEDIUM (신규)

### M1. config.yaml 내 MQTT password 평문 저장

**위치:** `gateway/internal/config/config.go:37`, `deploy/sample-config.yaml:17-18`

```go
Password string `yaml:"password,omitempty"`
```
```yaml
# sample-config.yaml에 username/password 필드 없음 — 현재는 OK
# 그러나 Phase 1에서 password 추가 시 config.yaml에 평문 저장됨
```

**근거:** `config.yaml`은 `install -m 640 ... chown root:iot`으로 배포된다. 640 권한이면 `iot` 그룹 멤버 전체가 읽기 가능. Pi에 SSH 접근한 `iot` 그룹 사용자가 MQTT credential을 취득할 수 있다. Phase 1 VerneMQ 이전 시 이 경로가 현실화된다.

**해결:** systemd `EnvironmentFile` 패턴 적용. `config.yaml`에서 `mqtt.password` 제거 → `GATEWAY_MQTT_PASSWORD` 환경변수로 주입.
```ini
# iot-gateway.service
EnvironmentFile=/etc/iot-gateway/secrets.env  # chmod 600, owner root
```

---

### M2. gw_rs485_open — FD_CLOEXEC 미설정 (파일 디스크립터 상속)

**위치:** `hal/src/rs485.c:55`

```c
int fd = open(dev, O_RDWR | O_NOCTTY | O_NONBLOCK);
// O_CLOEXEC 플래그 없음
```

**근거:** `O_CLOEXEC` 없이 open된 FD는 `fork()+exec()` 시 자식 프로세스에 상속된다. Go runtime은 내부적으로 subprocess를 사용할 수 있고 (예: `os/exec`), cgo 경계에서 goroutine이 OS 스레드를 생성할 때 FD가 의도치 않게 노출된다. RS485 FD가 상속되면 자식 프로세스가 직접 시리얼 포트에 쓰기를 시도할 수 있다 (Modbus 버스 오염).

**해결:**
```c
int fd = open(dev, O_RDWR | O_NOCTTY | O_NONBLOCK | O_CLOEXEC);
```
`gw_watchdog_open` (`watchdog.c:25`)도 동일하게 `O_CLOEXEC` 추가 필요.

---

### M3. assert_safe_state — pthread_mutex_lock 재귀 데드락 위험

**위치:** `hal/src/platform_pi4.c:193-204`

```c
int gw_gpio_assert_safe_state(void) {
    pthread_mutex_lock(&g_mu);  // 이미 잠긴 상태에서 호출 시 데드락
    for (int i = 0; i < MAX_GPIO_LINES; i++) {
        if (g_lines[i].line && g_lines[i].is_output) {
            (void)gpiod_line_set_value(g_lines[i].line, 0);
        }
    }
    pthread_mutex_unlock(&g_mu);
    return GW_OK;
}
```

**근거:** `gw_gpio_set` 실행 중 시그널 핸들러가 `assert_safe_state`를 호출하는 시나리오에서 데드락 발생. Go runtime의 panic recovery path (`main.go:85-91`)에서도 `AssertSafeState` 호출 전에 HAL mutex가 잠겨 있을 수 있다.

현재 `pthread_mutex_t g_mu = PTHREAD_MUTEX_INITIALIZER`는 기본 non-recursive mutex이므로, 같은 스레드에서 두 번 lock 시 undefined behavior (대부분 데드락).

**해결:**
```c
// PTHREAD_MUTEX_RECURSIVE 사용
pthread_mutexattr_t attr;
pthread_mutexattr_init(&attr);
pthread_mutexattr_settype(&attr, PTHREAD_MUTEX_RECURSIVE);
pthread_mutex_init(&g_mu, &attr);
```
또는 `assert_safe_state`를 mutex 없이 raw `gpiod_line_set_value`만 호출하는 별도 내부 함수로 분리.

---

### M4. relay command 감사 로그 부재

**위치:** `gateway/internal/actuator/actuator.go:138-218`

**증상:** `execute()`가 relay를 제어하지만 `db.LogCommand()`를 호출하지 않는다:
```go
// actuator.go:215
resp.Status = "executed"
// LogCommand 호출 없음
return resp
```

**근거:** `localdb.LogCommand()`와 `command_log` 테이블이 구현되어 있으나 호출하지 않는다. 한국 「가축전염병예방법」 등 규정에서 환경 제어 장치 작동 이력 보관을 요구할 수 있으며, 내부자 조작이나 오동작 디버깅 시 이력 없이는 원인 추적 불가.

**해결:** `execute()` 완료 후 `db.LogCommand` 호출 추가. rejected/failed 케이스도 기록.

---

### M5. heartbeat — hostname + 시스템 메트릭 MQTT 평문 발행

**위치:** `gateway/internal/health/health.go:74-103`

```go
hb := map[string]any{
    "hostname":               hostname,       // Pi 기기 이름 노출
    "go_alloc_mb":            ...,
    "goroutines":             runtime.NumGoroutine(),
    "disk_root_used_percent": diskPct,
    "cpu_temp_celsius":       cpuTemp,
}
```

**근거:** LAN 평문 MQTT 환경에서 `hostname`, 메모리 사용량, 고루틴 수, 디스크 사용률, CPU 온도가 네트워크에 노출된다. 공격자는 이를 통해 공격 대상 자원 현황 파악 및 취약 시점(예: 메모리 부족 시) 포착에 활용할 수 있다.

**해결:** TLS 이전까지는 heartbeat에서 hostname을 gateway_id로 대체. 메모리/디스크 메트릭은 서버 내부 모니터링 토픽(`gw/{id}/internal/metrics`)으로 분리하고 ACL로 서버만 구독 가능하게 제한.

---

### M6. watchdog timeout 상한 코드와 설정 불일치

**위치:** `hal/src/watchdog.c:23`, `gateway/internal/config/config.go:57`

```c
// watchdog.c:23
if (timeout_sec < 1 || timeout_sec > 60) return GW_ERR_INVALID;
// 상한을 60초로 설정했으나 주석은 "BCM2835 WDT 최대 약 15초"
```
```go
// config.go:57
KernelWDTTimeoutSec int `yaml:"kernel_wdt_timeout_sec"` // 15 (BCM2835 max)
```

**근거:** BCM2835/BCM2711 hardware WDT의 실제 최대 timeout은 15.996초다. `gw_watchdog_open`에서 `WDIOC_SETTIMEOUT` ioctl을 호출할 때 드라이버가 요청 값을 지원 범위로 클램핑하고 실제 설정된 값을 `timeout` 변수에 돌려준다 (`watchdog.c:31-34`). 그러나 코드는 반환된 실제 timeout을 확인하지 않는다. 사용자가 `kernel_wdt_timeout_sec: 60`을 설정하면 실제로는 15초로 클램핑되지만 코드는 60초로 kick한다 → WDT가 즉시 reboot 트리거.

**해결:**
```c
int actual_timeout = timeout_sec;
if (ioctl(fd, WDIOC_SETTIMEOUT, &actual_timeout) < 0) { ... }
if (actual_timeout != timeout_sec) {
    // 로그 경고
}
// actual_timeout을 호출자에게 반환하거나, HAL 수준에서 15초로 상한 고정
if (timeout_sec < 1 || timeout_sec > 15) return GW_ERR_INVALID;
```

---

## 🔵 BETTER ALTERNATIVES (Phase 7 보안 hardening 검토)

### B1. command payload HMAC 서명 — TLS 이전 임시 integrity 보호

**배경:** C1 해결을 위한 단기 대안. 서버가 command payload에 `HMAC-SHA256(secret, command_id+expires_at+action)`을 `sig` 필드로 포함해 발행하고, gateway가 검증. per-gateway shared secret은 배포 시 설정 파일에 주입. TLS 구현 전까지 command 위조 방지를 위한 실용적 방어층.

### B2. sensor profile 서버 중앙 관리 + 서명 배포

**배경:** H4의 공급망 위험 대응. 서버가 profile을 PostgreSQL에 저장하고, gateway에 배포 시 관리자 private key로 서명. gateway는 공개 키로 서명 검증 후에만 profile 적용. JOSN Web Signature(JWS) 또는 minisign 활용.

### B3. per-gateway MQTT credential 자동 생성 및 회전

**배경:** 현재 Phase 0은 anonymous, Phase 1은 수동 password. 설치 스크립트가 gateway당 고유 credential을 자동 생성하고 VerneMQ API로 등록, gateway `secrets.env`에 주입하는 자동화 구현. credential 유효기간 90일 + 자동 회전 job 추가.

---

## 권장 보안 우선순위

| 순위 | 항목 | 영향 layer | 예상 시간 |
|---|---|---|---|
| 1 | C1 mosquitto LAN 노출 → 127.0.0.1 바인딩 + ACL | Deploy | 30분 |
| 2 | C3 /dev/watchdog udev 권한 → iot user 접근 허용 | Deploy | 15분 |
| 3 | H2 command_id 중복 검사 → CommandSeen 연결 | Gateway | 30분 |
| 4 | H4 sensor profile → function_code/length/scale 검증 | Gateway | 1시간 |
| 5 | M2 O_CLOEXEC → rs485/watchdog open에 추가 | HAL | 15분 |
| 6 | M4 relay command 감사 로그 → LogCommand 연결 | Gateway | 30분 |
| 7 | M3 assert_safe_state 재귀 mutex → RECURSIVE 또는 리팩터 | HAL | 30분 |
| 8 | C2 go mod vendor → offline 빌드 | Deploy | 1시간 |
| 9 | H1 WireGuard 터널 구성 (TLS 전 임시) | Deploy | 2시간 |
| 10 | M1 MQTT password → EnvironmentFile 분리 | Gateway/Deploy | 30분 |
| 11 | M6 watchdog timeout ioctl 반환값 검증 | HAL | 15분 |
| 12 | M5 heartbeat 민감 정보 분리 | Gateway | 30분 |
| 13 | B1 command HMAC 서명 (TLS 이전 임시) | Gateway/Server | 3시간 |

**합계:** 우선순위 1-8 (즉시 필요) ≈ 5시간. 전체 ≈ 10-12시간.

---

## Conclusion

**운영 가능 여부 판정: Phase 0 내부 개발망 한정 — 현장 산업 배포 불가.**

가장 심각한 구조적 결함은 **C1 (MQTT 인증 없음 + LAN 전체 노출)** 이다. 이는 HAL/Gateway 코드 품질 문제가 아니라 배포 설계의 문제로, install-pi4.sh 한 파일 수정으로 즉시 완화할 수 있다. mosquitto를 127.0.0.1에 바인딩하고 WireGuard 또는 VPN 터널을 구성하면 외부 공격자의 relay 직접 조작이 차단된다.

**C3 (watchdog 권한)** 는 산업 환경에서의 가용성 위협이다. 커널 WDT가 실제로 동작하지 않고 있어, systemd hang 시 하드웨어 복구 경로가 없다. udev rule 한 줄로 해결되므로 즉시 수정해야 한다.

**구조적으로 잘 설계된 부분:** HAL의 `assert_safe_state` (best-effort, mutex 내 전체 pin LOW), `max_on_duration_sec` 타이머 강제 OFF, `expires_at` 검증, `command_log` 테이블 설계. Gateway의 `defer hal.AssertSafeState()` + panic recovery 체인도 안전 설계 원칙에 충실하다. 기존 리뷰(REVIEW_PHASE1_PHASE2.md)에서 지적된 C2 JWT verify off와 함께, Phase 0→1 전환 전에 C1·C3·H2·H4를 반드시 해결해야 한다.
