# Review: Gateway Agent (Go)

> 작성일: 2026-05-04
> 범위: gateway/cmd + gateway/internal (2,010줄 Go)
> 형태: review only — 구현 0줄, 의사결정 자료
> 발견 이슈: 🔴 3 · 🟠 5 · 🟡 7 · 🔵 4

---

## 🔴 CRITICAL — 배포 전 반드시 수정

### C1. defer 순서 역전 — panic 시 AssertSafeState가 Cleanup보다 늦게 실행

**파일:** `gateway/cmd/gateway-agent/main.go:79-91`
**증상:** Go defer는 LIFO 순서로 실행된다. 두 defer 블록이 등록된 순서는:
```go
// main.go:79  — 먼저 등록 → 나중에 실행 (LIFO)
defer func() {
    hal.AssertSafeState()        // 2번째로 실행됨
    if err := hal.Cleanup(); err != nil { ... }
}()

// main.go:85  — 나중에 등록 → 먼저 실행 (LIFO)
defer func() {
    if r := recover(); r != nil {
        hal.AssertSafeState()    // 1번째로 실행됨
        panic(r)
    }
}()
```
**영향:** panic이 발생하지 않는 정상 종료에서는 문제 없다. 그러나 recover defer가 panic을 잡고 `panic(r)`로 re-panic하면, 이미 첫 번째 defer(AssertSafeState + Cleanup)는 LIFO 상 이미 실행 완료된 뒤다. 실제 문제는 `recover()` 안에서도 `hal.AssertSafeState()`를 중복 호출하지만, **relay가 이미 켜진 채로 HAL Cleanup → RS485 닫기 순서**가 보장되지 않을 수 있다.

더 심각한 문제: Cleanup 내부에서 `gw_hal_cleanup()` 이 `AssertSafeState`를 내부 호출한다(헤더 주석)지만, Go 측 `hal.AssertSafeState()` 를 명시적으로 Cleanup **전에** 호출해야 하는 설계 의도(`IRON RULE` 주석)를 현재 defer 순서가 지키지 않는다.

**해결안:** 단일 defer로 통합하거나 순서를 뒤집는다.
```go
// 올바른 순서: recover를 먼저 등록(나중에 실행) — AssertSafeState는 가장 먼저
defer func() {
    hal.AssertSafeState()
    if err := hal.Cleanup(); err != nil { ... }
}()
defer func() {  // 이 defer는 위의 것보다 나중에 등록 → 먼저 실행
    if r := recover(); r != nil {
        log.Printf("PANIC: %v", r)
        panic(r)
    }
}()
```
**권장:** recover + AssertSafeState + Cleanup + re-panic을 단일 defer로 통합. 설계 의도와 실제 실행 순서를 코드 수준에서 명시적으로 일치시켜라.

---

### C2. 명령 idempotency가 실제로 동작하지 않음 — CommandSeen 후 LogCommand 누락

**파일:** `gateway/internal/actuator/actuator.go:138-218`, `gateway/internal/localdb/sqlite.go:207-213`
**증상:** `DB.CommandSeen()`과 `DB.LogCommand()` API는 구현되어 있지만, `actuator.execute()`에서 전혀 호출되지 않는다.
```go
// actuator.go:138 — execute 함수 전체 어디에도 CommandSeen/LogCommand 호출 없음
func (m *Manager) execute(req *CommandRequest) *CommandResponse {
    // ...CommandSeen 호출 없음...
    if err := hal.GPIOSet(state.cfg.GPIOPin, value); err != nil { ... }
    // ...LogCommand 호출 없음...
}
```
네트워크 재연결 후 브로커가 QoS 1 미확인 메시지를 재전송하면(`clean_session=false`), 동일 `command_id`가 relay를 두 번 ON/OFF할 수 있다. 펌프/살균기 같은 actuator에서 의도치 않은 이중 작동은 **하드웨어 안전 사고 위험**이다.

**영향:**
- MQTT QoS 1 재전송 시 동일 명령 중복 실행
- `max_on_duration` 타이머 이중 등록 → 타이머 메모리 누수
- DB의 `command_log` 테이블이 영구 비어 있음 → 운영 감사 추적 불가

**해결안:** `execute()` 진입 시:
```go
if seen, err := m.db.CommandSeen(req.CommandID); err == nil && seen {
    resp.Status = "rejected"
    resp.Reason = "duplicate command_id"
    return resp
}
defer m.db.LogCommand(req.CommandID, req.ActuatorChannelID, req.Action, ...)
```

---

### C3. 오프라인 큐 flush 로직 미구현 — SQLite에 쌓인 데이터가 영구적으로 클라우드에 전달되지 않음

**파일:** `gateway/internal/localdb/sqlite.go:94-122`, `gateway/internal/sensor/sensor.go:229-236`
**증상:** sensor.go에서 MQTT 실패 시 SQLite 큐에 적재하지만:
```go
// sensor.go:229-235
if err := m.mq.Publish(topic, bs); err != nil {
    _ = m.db.Enqueue(localdb.QueuedMessage{
        Topic:   topic,
        Payload: bs,
        Priority: 3,
    })
}
```
어디에도 `PeekBatch()` + `Delete()` 를 호출하여 큐를 flush하는 코드가 없다. `main.go`, `mqtt/client.go`의 `OnConnect` 콜백, `health.go` 어디에도 flush 루프가 없다.

**영향:** MQTT가 5분 단절된 후 재연결되어도, 5분치 telemetry는 SQLite에 영구 잔류한다. `max_queue_rows` 도달 시 이후 데이터는 drop되며, 재연결 이후에도 cloud에 전달되지 않는다. 설계 의도(오프라인 버퍼링 → 복귀 시 backlog flush)가 전혀 구현되지 않은 상태다.

**해결안:** `mqtt.Client`의 `OnConnect` 콜백에서 flush goroutine을 시작하거나, `health.Agent.Run()` 루프에 flush 로직을 추가한다.
```go
// mqtt/client.go의 OnConnect에서 flush 시작
pahoOpts.OnConnect = func(c paho.Client) {
    cl.connected.Store(true)
    if cl.OnConnect != nil {
        cl.OnConnect()  // main.go가 여기에 flush goroutine 시작 등록
    }
}
```

---

## 🟠 HIGH — 운영 안정성 위협

### H1. Gateway ID에 MQTT 토픽 와일드카드 문자 삽입 가능 — 토픽 인젝션

**파일:** `gateway/internal/mqtt/client.go:84`, `gateway/internal/actuator/actuator.go:79`, `gateway/internal/sensor/sensor.go:227`
**증상:** `gateway_id`는 `config.yaml`에서 그대로 읽어 토픽 문자열에 삽입된다. validation이 없다.
```go
// mqtt/client.go:84
lwtTopic := fmt.Sprintf("gw/%s/state", opts.GatewayID)

// actuator.go:79
topic := fmt.Sprintf("gw/%s/command/request", m.gatewayID)
```
Gateway ID에 `+`, `#`, `/` 같은 문자가 포함되면 (`GW-TEST/+`) MQTT 토픽이 `gw/GW-TEST/+/command/request` 형태가 되어 **다른 gateway의 토픽을 subscribe하거나 브로커 동작을 교란**할 수 있다.

**영향:** Phase 0은 단일 게이트웨이 + 로컬 브로커라 실제 노출 가능성은 낮다. 그러나 동일 코드가 Phase 1+ 에서 원격 VerneMQ에 연결될 때 즉시 보안 문제가 된다.

**해결안:** `config.Validate()`에 ID 패턴 검증 추가:
```go
// config/config.go Validate()에 추가
import "regexp"
var validID = regexp.MustCompile(`^[A-Za-z0-9_-]+$`)
if !validID.MatchString(c.Gateway.ID) {
    return fmt.Errorf("gateway.id must match [A-Za-z0-9_-]+")
}
```

---

### H2. actuator.Run() defer 순서 버그 — panic 시 assertAllOff가 recover보다 먼저 실행

**파일:** `gateway/internal/actuator/actuator.go:68-86`
**증상:**
```go
func (m *Manager) Run(ctx context.Context) {
    defer func() {
        m.assertAllOff()    // 등록 순서 1 → LIFO 상 나중에 실행
        if r := recover(); r != nil {  // recover는 이 블록 안에 있지만...
            hal.AssertSafeState()
            panic(r)
        }
    }()
    // ...
}
```
C1과 다른 구조적 문제: `assertAllOff()`와 `recover()`가 **같은 defer 블록에 있다**. `recover()`는 panic 발생 시에만 실행되는 조건부 코드다. 그런데 `assertAllOff()` 가 먼저 실행되고, 그 안에서 `hal.GPIOSet()` 가 panic을 발생시키면 내부의 `recover()`가 잡지 못한다 — recover는 자신을 포함한 defer 함수 안에서 발생한 panic만 잡을 수 없다.

**해결안:** `recover()`를 별도 defer로 분리해 먼저 등록한다(나중에 실행):
```go
defer m.assertAllOff()
defer func() {
    if r := recover(); r != nil {
        hal.AssertSafeState()
        panic(r)
    }
}()
```

---

### H3. Enqueue가 트랜잭션 없음 — 동시 접근 시 max_queue_rows 초과 가능

**파일:** `gateway/internal/localdb/sqlite.go:95-122`
**증상:** COUNT → 조건 확인 → DELETE → INSERT 시퀀스가 하나의 트랜잭션이 아니다.
```go
// sqlite.go:105-118 — TOCTOU race
var count int
d.conn.QueryRow("SELECT COUNT(*) FROM queued_messages").Scan(&count)
if count >= d.maxQueueRows {
    d.conn.Exec("DELETE FROM queued_messages WHERE id IN (...)")
}
_, err := d.conn.Exec("INSERT INTO queued_messages...")
```
100개 센서가 동시에 MQTT 실패 → 100개 goroutine이 동시 Enqueue → 모두 COUNT 읽은 뒤 INSERT → max_queue_rows를 최대 100배 초과 가능.

**영향:** SQLite busy_timeout=5000ms로 직렬화되므로 실제 동시성은 낮지만, `conn.SetMaxOpenConns(1)` 설정이 없어 여전히 TOCTOU 가능. 또한 WAL 모드는 동시 읽기/쓰기를 허용하므로 COUNT 이후 INSERT 사이에 다른 writer가 끼어들 수 있다.

**해결안:**
```go
tx, err := d.conn.Begin()
defer tx.Rollback()
// COUNT, DELETE, INSERT를 tx 안에서 수행
tx.Commit()
```
또한 `conn.SetMaxOpenConns(1)` 을 Open()에서 설정하면 SQLite single-writer 특성과 정합된다.

---

### H4. MQTT 재연결 시 Subscribe 재등록 없음 — 명령 수신 중단

**파일:** `gateway/internal/actuator/actuator.go:68-86`, `gateway/internal/mqtt/client.go:93-112`
**증상:** paho의 `SetAutoReconnect(true)`는 Transport 재연결만 처리한다. `CleanSession=false`로 설정되었으나, **브로커가 재시작**되거나 세션이 만료되면 subscription이 사라진다. 현재 코드는 `Run()`에서 최초 1회만 Subscribe를 호출한다:
```go
// actuator.go:80
if err := m.mq.Subscribe(topic, m.handleCommand); err != nil {
    log.Printf("[actuator] subscribe failed: ... (will retry on reconnect via paho)")
}
// OnConnect 콜백에 재등록 로직 없음
```
paho 내장 AutoReconnect가 `CleanSession=false` 에서 이전 세션 subscription을 자동 복원하는 것은 **브로커가 세션을 유지했을 때만** 성립한다.

**해결안:** `mqtt.Options`에 `ResubscribeTopics []string` 필드를 추가하거나, `OnConnect` 콜백에서 Subscribe를 재호출한다:
```go
// mqtt/client.go OnConnect 콜백에서
pahoOpts.OnConnect = func(c paho.Client) {
    cl.connected.Store(true)
    for _, resub := range cl.resubTopics {
        c.Subscribe(resub.topic, cl.qos, resub.handler)
    }
    if cl.OnConnect != nil { cl.OnConnect() }
}
```

---

### H5. PurgeOld가 호출되지 않음 — SQLite 파일이 무한 증가

**파일:** `gateway/internal/localdb/sqlite.go:152-161`
**증상:** `PurgeOld()` 메서드는 구현되어 있지만 어디서도 호출되지 않는다. `main.go`, `health.go`, `sensor.go` 전체 검색 결과 호출 0건.

**영향:** 7일 retention 정책이 config에 있으나 실제 삭제가 실행되지 않아 SQLite 파일이 무한 증가한다. Pi 4 SD 카드는 보통 8-32GB — 100 센서 × 10초 polling × 7일 × ~500 bytes = 약 3GB 적재 가능. flush 미구현(C3)과 결합하면 실질적으로 데이터가 계속 누적된다.

**해결안:** `health.Agent.Run()` 루프에 24시간 ticker 추가:
```go
// health.go Run() 내부
purgeTick := time.NewTicker(24 * time.Hour)
defer purgeTick.Stop()
// select 케이스에 추가
case <-purgeTick.C:
    if n, err := a.db.PurgeOld(); err != nil {
        log.Printf("[health] purge failed: %v", err)
    } else {
        log.Printf("[health] purged %d old records", n)
    }
```

---

## 🟡 MEDIUM — 개선 권장

### M1. `time.Sleep(50ms)` in pollOnce — context 무시

**파일:** `gateway/internal/sensor/sensor.go:183`
```go
time.Sleep(50 * time.Millisecond)
```
CRC retry 사이 sleep이 `context.Done()`을 체크하지 않는다. context 취소 후 최대 50ms 지연 발생. 100센서 기준 최대 5초 추가 shutdown 지연 가능.

**해결안:**
```go
select {
case <-ctx.Done():
    return nil, ctx.Err()
case <-time.After(50 * time.Millisecond):
}
```

---

### M2. sensor.go의 `m.mu` mutex가 사용되지 않음

**파일:** `gateway/internal/sensor/sensor.go:95-96`
```go
type Manager struct {
    // ...
    mu sync.Mutex  // 선언되어 있으나 어디서도 Lock/Unlock 호출 없음
}
```
`Manager.channels` 슬라이스는 `NewManager`에서만 append되고 이후 읽기 전용이므로 현재는 race가 없다. 그러나 불필요한 필드는 혼란을 야기한다 — 미래에 동적 채널 추가 기능이 생겼을 때 실수로 mutex 없이 접근할 위험이 있다.

**해결안:** mutex가 없어도 되면 제거하고 주석에 "channels은 NewManager 이후 읽기 전용"을 명시. 필요하면 실제 사용처에서 Lock/Unlock을 추가한다.

---

### M3. Sensor Profile JSON을 shared/sensor_profile_schema.json으로 검증하지 않음

**파일:** `gateway/internal/sensor/sensor.go:62-80`
```go
func LoadProfile(path string) (*Profile, error) {
    // JSON unmarshal만 수행 — schema 검증 없음
    if len(p.Measurements) == 0 {
        return nil, fmt.Errorf("profile has no measurements")
    }
}
```
`Profile` struct에 없는 필드(`display_group`, `order`, `endianness`)는 조용히 무시된다. `modbus.length` 가 2인 경우(uint32/float32) Phase 0 코드는 첫 번째 register만 읽는다는 TODO가 있으나, length=2로 설정된 profile 파일을 로드했을 때 **경고 없이 잘못된 값**을 계산한다.

**해결안:** `LoadProfile`에서 `meas.Modbus.Length > 1` 감지 시 WARN 로그. Phase 1에서 `github.com/santhosh-tekuri/jsonschema/v5` 으로 shared schema 검증 추가.

---

### M4. `hal.Version()` 에러 무시 — 초기화 실패 숨김

**파일:** `gateway/cmd/gateway-agent/main.go:93-96`
```go
v, err := hal.Version()
if err == nil {
    log.Printf("HAL: %s", v)
}
// err != nil 시 무시
```
HAL이 정상 초기화되었다면 Version()은 성공해야 한다. 실패 시 `NotInit` 에러는 HAL 초기화 문제를 나타낼 수 있으므로 최소 WARN 로그가 필요하다.

---

### M5. `json.Marshal` 에러 무시 — 잠재적 empty payload 발행

**파일:** 다수 위치
```go
// sensor.go:223
bs, _ := json.Marshal(payload)

// actuator.go:132
bs, _ := json.Marshal(resp)

// mqtt/client.go:85
lwtPayload, _ := json.Marshal(...)

// health.go:103
bs, _ := json.Marshal(hb)
```
`map[string]any` 는 실제로 marshal 실패하지 않지만, 향후 구조체로 변경 시 `omitempty` + nil pointer 조합으로 실패 가능. `_` 로 버리지 말고 에러를 로그하는 패턴을 일관되게 사용해야 한다.

---

### M6. Health Agent가 DB 없이 동작 — 센서 health 통계 미포함

**파일:** `gateway/internal/health/health.go:30-40`
```go
func New(mq *mqttpkg.Client, gatewayID string, interval time.Duration) *Agent {
    // db *localdb.DB 파라미터 없음
}
```
heartbeat payload에 센서 health 상태(`ok/degraded/failed` 개수)가 포함되지 않는다. 클라우드에서 gateway 상태를 볼 때 센서 장애를 알 수 없다.

**해결안:** `health.New(mq, gatewayID, interval, db)` — DB를 주입받아 `publish()` 시 센서 health 집계 쿼리 포함.

---

### M7. config.yaml 파일 권한 체크 없음 + 로그에 MQTT password 누출 가능

**파일:** `gateway/internal/config/config.go:88-104`
MQTT `password` 필드가 config에 있으나 파일 모드 확인 없음(`os.Stat()` + mode check). 또한 `log.Printf("loaded config: ...")` 에서 config 구조체를 직접 출력하지는 않지만, 미래에 디버그 목적으로 cfg를 로그할 때 password가 노출될 위험이 있다.

**해결안:**
1. `Load()` 에서 파일 권한 확인: `info.Mode().Perm() & 0o077 != 0` 이면 WARN
2. `MQTTConfig.Password` 필드에 `String()` 메서드로 마스킹: `"[REDACTED]"`

---

## 🔵 BETTER ALTERNATIVES — Phase 1+ 검토

### B1. `errgroup.Group` 으로 goroutine 에러 전파

**파일:** `gateway/cmd/gateway-agent/main.go:161-198`
현재 goroutine들은 `sync.WaitGroup`으로 관리되며, 내부 에러를 반환하지 못한다. `golang.org/x/sync/errgroup` 을 사용하면 goroutine 내부 에러를 main까지 전파하고, 하나가 실패하면 다른 goroutine도 취소할 수 있다.

---

### B2. SQLite connection pool 단일화

**파일:** `gateway/internal/localdb/sqlite.go:38-58`
`sql.Open()` 후 `conn.SetMaxOpenConns(1)` 설정이 없다. modernc SQLite는 단일 파일 writer가 안전하다. `SetMaxOpenConns(1)` + `SetMaxIdleConns(1)` + `SetConnMaxLifetime(0)` 설정으로 SQLite의 단일 writer 특성에 명시적으로 정합시키면 busy_timeout 의존도를 줄일 수 있다.

---

### B3. Sensor Profile에 `data_type` 기반 decode 분기 추가

**파일:** `gateway/internal/sensor/sensor.go:192-195`
```go
// Phase 0 단순화 주석이 있지만, uint 타입도 signed 16-bit로 처리
val := float64(int16(raw[0])) // signed 16-bit 가정
```
profile schema의 `data_type: "uint"` 인 경우(예: NH3 0-100 ppm) `int16()`으로 처리하면 register 값 0x8000 이상에서 음수 값이 나온다. `length=1` 범위에서도 data_type 구분이 필요하다.

---

### B4. MQTT `ConnectToken` timeout에 context.Context 활용

**파일:** `gateway/internal/mqtt/client.go:116-124`
```go
func (cl *Client) Connect(ctx context.Context) error {
    tok := cl.c.Connect()
    select {
    case <-tok.Done():
        return tok.Error()
    case <-ctx.Done():
        return ctx.Err()
    }
}
```
`ConnectTimeout` 옵션을 paho에 이미 설정했으나, context timeout과 paho 내부 timeout이 독립적으로 존재한다. Phase 1+에서 `context.WithTimeout`을 명시적으로 사용하는 패턴으로 통일하면 타임아웃 로직이 단순해진다.

---

## 권장 수정 우선순위

| 순위 | 항목 | 이슈 | 예상 시간 |
|---|---|---|---|
| 1 | C3 오프라인 큐 flush 구현 | CRITICAL — 핵심 기능 미구현 | 2-3시간 |
| 2 | C2 CommandSeen + LogCommand 연동 | CRITICAL — 하드웨어 안전 | 1시간 |
| 3 | C1 defer 순서 수정 + 단일화 | CRITICAL — 안전 종료 보장 | 30분 |
| 4 | H5 PurgeOld 정기 호출 추가 | HIGH — 디스크 고갈 방지 | 30분 |
| 5 | H4 OnConnect Subscribe 재등록 | HIGH — MQTT 재연결 안정성 | 1시간 |
| 6 | H3 Enqueue 트랜잭션 + SetMaxOpenConns(1) | HIGH — SQLite race | 1시간 |
| 7 | H1 Gateway ID 패턴 검증 | HIGH — 토픽 인젝션 방지 | 20분 |
| 8 | H2 actuator defer 순서 수정 | HIGH — panic 안전 종료 | 20분 |
| 9 | M1-M7 코드 품질 수정 | MEDIUM | 3-4시간 |

**합계:** 약 10-14시간 → solo + AI pair로 1.5-2 sprint day.

---

## Conclusion

**현 상태 평가:** Code is **structurally well-designed but has critical functionality gaps**.

- 아키텍처 골격 (config → HAL → sensor/actuator → MQTT → SQLite → health) 설계 의도 명확하고 일관성 우수
- HAL cgo binding은 C 헤더와 정합되며 thread-safety 설명도 충실
- SQLite schema 설계 (우선순위 큐, sensor_health, command_log) 구조 적절
- 테스트는 happy path 및 일부 rejection path 커버 — 합격선

**그러나:**
- 🔴 **C3 (오프라인 큐 flush 미구현)**: "MQTT 재연결 시 backlog flush" 가 설계의 핵심 동작인데 구현 0줄. 현재 게이트웨이는 오프라인 버퍼 기능이 사실상 작동하지 않는다.
- 🔴 **C2 (command idempotency 누락)**: DB API는 있으나 실제 연결 없음. relay 이중 작동 시 산업 현장 안전 사고 위험.
- 🔴 **C1 (defer 순서)**: 설계 의도 (`IRON RULE`) 와 실제 실행 순서 불일치.

🟠 H 항목들은 시스템이 돌아가도 며칠 안에 드러날 문제들: SQLite 무한 증가, 브로커 재시작 후 명령 수신 중단, 토픽 인젝션 취약점.

**권장 next action:** C1, C2, C3 + H4, H5를 단일 sprint에서 수정 → 최소 운영 가능 상태 달성 후 burn-in 시작. M/B 항목은 Phase 1+ 로 자연 분배 가능.
