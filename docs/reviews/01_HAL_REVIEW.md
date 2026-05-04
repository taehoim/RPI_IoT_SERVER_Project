# Review: HAL Layer (C, libgw_hal.so)

> 작성일: 2026-05-04
> 범위: hal/include + hal/src + hal/tests (총 7개 C 파일, ~1,003줄)
> 형태: review only — 구현 0줄, 의사결정 자료
> 발견 이슈: 🔴 3 · 🟠 4 · 🟡 5 · 🔵 3

---

## 🔴 CRITICAL

### C1. `gw_hal_cleanup()`이 `gw_gpio_cleanup()` 없이 libgpiod 라인 leak

**파일:** `hal/src/common.c:22-27`, `hal/src/platform_pi4.c:193-204`

**증상:** `gw_hal_cleanup()` 호출 시 `gw_gpio_assert_safe_state()`만 호출하고, `g_chip` 핸들과 `g_lines[]`에 있는 모든 `gpiod_line` 핸들이 `gpiod_line_release()` / `gpiod_chip_close()` 없이 누수된다. Go 에이전트가 재시작(crash→restart) 시 cgo를 통해 `gw_hal_cleanup()` + `gw_hal_init()` 재호출하면, 두 번째 `gw_gpio_init()`이 g_gpio_initialized 체크를 통과해 `gpiod_chip_open()` 재호출이 차단되지만 첫 번째 세션의 chip 핸들은 정리가 되지 않아 파일 디스크립터를 계속 점유한다. `gw_hal_cleanup()`이 `g_gpio_initialized = 0`(common.c:25)으로 리셋하지만 `g_chip`과 `g_lines[]`는 nil로 초기화되지 않는다.

**근거:**
```c
// common.c:22-27
int gw_hal_cleanup(void) {
    gw_gpio_assert_safe_state();
    atomic_store(&g_initialized, 0);  // gpio 상태는 건드리지 않음
    return GW_OK;
}

// platform_pi4.c: gw_gpio_cleanup() 함수 자체가 존재하지 않음
// g_chip, g_lines[i].line 에 대한 해제 코드 없음
```

**영향:** 장기 운영 중 프로세스 재시작(watchdog reboot 제외) 시 `/dev/gpiochip0` FD 누수. 재시작 N회 후 `open()` 실패 가능. Pi 4에서 `/dev/gpiochip0` FD 한도(일반적으로 1024)에 도달하면 `gw_gpio_init()` 영구 실패.

**해결안:**
- (A) `gw_hal_cleanup()` 내부에서 `gw_gpio_cleanup_internal()` 호출 추가. 이 함수에서 mutex lock → `gpiod_line_release(g_lines[i].line)` for 루프 → `gpiod_chip_close(g_chip)` → `g_chip = NULL`, `g_gpio_initialized = 0` 순서로 정리.
- (B) `platform_pi4.c`에 `gw_gpio_cleanup(void)` 함수를 공개 ABI로 추가하고 `gw_hal.h`에 선언 (ABI 추가는 minor 버전 업 필요).

**권장:** (A). ABI 변경 없이 `common.c`의 cleanup 경로에서 플랫폼 내부 함수를 직접 호출. `platform_r1124.c`에도 동일 stub 추가 필요.

---

### C2. `read_with_timeout()` — 타임아웃이 매 `read()` 마다 리셋되지 않고 전체 타임아웃이 분할 소진됨 (실제로는 선택 호출마다 동일 timeout_ms 재사용)

**파일:** `hal/src/rs485.c:101-125`

**증상:** `read_with_timeout()` 루프 내에서 `select()` 호출마다 `tv.tv_sec` / `tv.tv_usec` 를 항상 `timeout_ms`에서 다시 계산한다. 즉 느린 슬레이브가 패킷을 여러 청크로 분할해서 전송하는 경우, 각 청크 사이 대기마다 완전한 `timeout_ms`를 다시 허용한다. 결과적으로 126바이트 응답(length=125 최대)을 1바이트씩 전송하면 이론상 최대 `126 × timeout_ms` 동안 블록된다.

**근거:**
```c
// rs485.c:101-125
static int read_with_timeout(int fd, uint8_t* buf, int want, int timeout_ms) {
    int got = 0;
    while (got < want) {
        struct timeval tv;
        tv.tv_sec  = timeout_ms / 1000;   // ← 매 반복마다 전체 timeout 재할당
        tv.tv_usec = (timeout_ms % 1000) * 1000;
        int r = select(fd + 1, &rfds, NULL, NULL, &tv);
        ...
    }
}
```

**영향:** 정상 센서가 전기적 노이즈로 간헐적으로 부분 응답만 내보낼 때, Go 에이전트가 기대한 `timeout_ms` 안에 반환되지 않아 상위 레이어의 컨텍스트 타임아웃 초과로 이어질 수 있다. 특히 watchdog kick 스레드가 같은 고루틴에 있으면 kick 지연 → reboot 위험.

**해결안:**
- (A) `clock_gettime(CLOCK_MONOTONIC)`으로 진입 시각을 기록한 뒤, 각 `select()` 전에 남은 시간을 재계산하여 `tv` 설정. 남은 시간이 0 이하면 `GW_ERR_TIMEOUT` 즉시 반환.
- (B) `timeout_ms` 를 `int deadline_ms` (절대 시각)로 전달하도록 내부 인터페이스 변경.

**권장:** (A). 20줄 수정으로 inter-chunk 타임아웃 어큐뮬레이션을 방지. Linux `clock_gettime(CLOCK_MONOTONIC)` 사용 (NTP 조정에 영향 없음).

---

### C3. `gw_rs485_modbus_read()` — exception response 수신 시 버퍼 overflow 가능

**파일:** `hal/src/rs485.c:153-170`

**증상:** exception response는 5바이트(slave+fn|0x80+code+CRC_lo+CRC_hi)이지만, `read_with_timeout(fd, resp, expected, ...)` 호출에서 `expected = 5 + 2 * length`로 전체 정상 응답 크기를 기대한다. 슬레이브가 exception 응답(5바이트)을 보내고 침묵하면 `GW_ERR_TIMEOUT` 반환으로 정상 처리된다. 그러나 만약 테스트 시나리오처럼 exception 응답 직후 추가 바이트가 오거나, 동일 버스에 다른 슬레이브가 혼선으로 데이터를 보내면 `resp[]`를 `expected`만큼 채우게 된다. 이때 `resp[1]`에 `0x80` 비트가 있어야 exception으로 인식하지만(rs485.c:157), 실제로는 이미 `read_with_timeout`이 `expected` 바이트를 다 읽은 후에만 그 검사에 도달하므로 예외 응답 5바이트 후 남은 `2*length` 바이트를 다른 곳의 데이터로 채우게 된다. `resp[]`는 `uint8_t resp[256]`으로 고정 크기이고 `expected` 최대는 `5 + 250 = 255`로 bound 내지만, exception 판별을 위해 **1바이트만 먼저 read**하는 구조가 아니므로 정상적인 exception 처리 흐름이 깨진다.

실제 핵심 문제: exception response 검사(line 157)가 `read_with_timeout` **이후**에 있어서, exception 응답(5바이트)이 왔을 때 나머지 `expected - 5` 바이트를 기다리다가 `GW_ERR_TIMEOUT`만 반환하고 `GW_ERR_IO` (exception 코드)는 **절대 반환되지 않는다**.

**근거:**
```c
// rs485.c:153-157
int rc = read_with_timeout(fd, resp, expected, timeout_ms);
if (rc < 0) return rc;  // TIMEOUT이 여기서 반환됨

if ((resp[1] & 0x80) != 0) return GW_ERR_IO;  // 여기에 절대 도달 불가
```

**영향:** Modbus exception (illegal function, illegal address 등) 을 timeout 오류와 구분 불가. 슬레이브 오동작 vs 통신 단절을 구분하지 못해 상위 레이어가 잘못된 fault 처리 경로를 탄다. 테스트 `test_exception` 케이스가 이를 `GW_ERR_IO or TIMEOUT` 모두 허용(test_rs485_pty.c:200)함으로써 버그를 숨기고 있다.

**해결안:**
- (A) 헤더 2바이트(slave + fn)를 먼저 읽고, `fn & 0x80`이면 exception 전용 3바이트를 추가 read 후 `GW_ERR_IO` 반환. 정상이면 `byte_count` 1바이트 read 후 나머지를 읽는다.
- (B) 타임아웃으로 부분 수신된 경우에도 `resp[1]` 검사를 `got >= 2` 조건 하에 즉시 수행하도록 `read_with_timeout` 콜백 구조로 변경.

**권장:** (A). exception path를 명시적으로 구분하면 상위 레이어가 슬레이브 상태를 정확히 진단 가능.

---

## 🟠 HIGH

### H1. `gw_gpio_assert_safe_state()` — signal context에서 mutex deadlock 가능

**파일:** `hal/src/platform_pi4.c:193-204`

**증상:** `gw_gpio_assert_safe_state()`가 `pthread_mutex_lock(&g_mu)` 를 호출한다. 이 함수는 panic / abort 경로에서 호출되도록 설계되어 있는데(gw_hal.h:11), SIGABRT 또는 SIGTERM 핸들러에서 호출하면, 핸들러 진입 시점에 같은 스레드(또는 다른 스레드)가 이미 `g_mu`를 보유하고 있을 경우 **deadlock**이 된다. Go 런타임이 cgo 함수 내에서 신호를 전달하는 방식(goroutine stack에서 직접 C 함수 호출 중 SIGTERM 수신)을 고려하면 실제 발생 가능한 시나리오다.

**근거:**
```c
// platform_pi4.c:195
int gw_gpio_assert_safe_state(void) {
    pthread_mutex_lock(&g_mu);  // ← 신호 핸들러에서 안전하지 않음
    ...
    pthread_mutex_unlock(&g_mu);
}
```

**영향:** Watchdog이 만료되거나 SIGTERM으로 Go 에이전트가 종료될 때 `AssertSafeState()`가 mutex 대기 중 hang → relay가 마지막 state(ON)로 고정 → NC fail-safe 원칙 위반. 정확히 C1 IRON RULE을 무력화하는 경로.

**해결안:**
- (A) `pthread_mutex_trylock()` 사용 후 실패해도 루프 강행 (best-effort 유지). 이미 주석에 "best-effort" 명시되어 있으므로 의미론적으로 일관.
- (B) signal handler에서는 `gw_gpio_assert_safe_state()`를 호출하지 말고, `sig_atomic_t` flag만 설정 후 main loop에서 처리.
- (C) `gw_gpio_assert_safe_state()`에서 mutex 없이 `g_lines` 직접 접근 (torn read 위험 있지만 panic path에서는 차선).

**권장:** (A). `pthread_mutex_trylock` + 실패 시 lock 없이 강행. panic 경로에서 데이터 일관성보다 릴레이 OFF가 우선.

---

### H2. `gw_hal_init()` / `gw_gpio_init()` — 동시 호출 시 이중 초기화 경쟁 조건

**파일:** `hal/src/common.c:14-20`, `hal/src/platform_pi4.c:67-88`

**증상:** `gw_hal_init()`은 `atomic_compare_exchange_strong`으로 보호되지만, `gw_gpio_init()`은 `pthread_mutex_lock` + `g_gpio_initialized` 정수 플래그로 보호된다. Go 에이전트의 `Init()` 함수(hal.go:74-79)는 `gw_hal_init()`과 `gw_gpio_init()`을 연속으로 호출하는데, 두 번의 goroutine에서 동시에 `Init()`을 호출하면:

1. G1: `gw_hal_init()` 통과 (atomic CAS 성공)
2. G2: `gw_hal_init()` 통과 (CAS 실패 → 이미 1, 그냥 OK 반환)
3. G1: `gw_gpio_init()` 진입, mutex lock, `g_chip` open 시작
4. G2: `gw_gpio_init()` 진입, mutex lock 대기 → G1 완료 후 `g_gpio_initialized=1` 확인 → OK 반환 (정상)

GPIO는 mutex로 보호되므로 실제로 이중 초기화는 발생하지 않는다. **그러나** `gw_hal_cleanup()` + `gw_hal_init()` 재초기화 시퀀스에서 `g_gpio_initialized`는 cleanup에서 `0`으로 리셋되지 않기 때문에(C1 이슈와 동일 원인), 재초기화 시 `gw_gpio_init()`이 멱등 동작(early return GW_OK)으로 `gpiod_chip_open()`을 건너뛴다.

**근거:**
```c
// common.c:25
atomic_store(&g_initialized, 0);  // g_gpio_initialized는 건드리지 않음

// platform_pi4.c:69-72
if (g_gpio_initialized) {  // 여전히 1 → chip 재오픈 안 됨
    pthread_mutex_unlock(&g_mu);
    return GW_OK;           // 스텔스 무동작
}
```

**영향:** cleanup → init 재시작 후 GPIO 함수들이 GW_OK를 반환하지만 실제로는 `g_chip`이 닫힌 채 이전 포인터가 dangling 상태. `gpiod_chip_get_line()` 호출 시 UB.

**해결안:** `gw_hal_cleanup()`에서 `gw_gpio_cleanup_internal()` 호출 (C1 해결안과 동일). 이 함수 안에서 `g_gpio_initialized = 0` 및 `g_chip = NULL` 설정.

---

### H3. `gw_rs485_modbus_read()` — slave 주소 0 및 247 초과 미검증

**파일:** `hal/src/rs485.c:130`

**증상:** Modbus RTU 표준에서 slave 주소 0은 브로드캐스트(응답 없음), 248-255는 예약됨. 현재 `slave` 파라미터에 대한 범위 검증이 없다. `slave=0`으로 read 요청을 보내면 응답이 오지 않아 항상 `GW_ERR_TIMEOUT` 반환 — 이는 오류 메시지가 오해를 일으킨다.

**근거:**
```c
// rs485.c:130
int gw_rs485_modbus_read(int fd, uint8_t slave, uint8_t function_code, ...) {
    if (fd < 0 || !out || length == 0 || length > 125) return GW_ERR_INVALID;
    if (function_code != 0x03 && function_code != 0x04) return GW_ERR_INVALID;
    // slave 범위 검사 없음
```

`gw_rs485_modbus_write()` (rs485.c:174-175) 도 동일: `if (fd < 0) return GW_ERR_INVALID;`만 있고 slave 검증 없음.

**영향:** 센서 프로필 잘못 설정(slave=0) 시 HAL이 `GW_ERR_INVALID`가 아닌 `GW_ERR_TIMEOUT`을 반환해 상위 레이어가 "통신 단절"로 오해하고 불필요한 재시도 루프를 반복.

**해결안:** 두 함수 모두 `if (slave == 0 || slave > 247) return GW_ERR_INVALID;` 추가.

---

### H4. 테스트: `test_safe_state.c`가 mock backend를 검증하고 실제 `platform_pi4.c` 경로를 전혀 테스트하지 않음

**파일:** `hal/tests/test_safe_state.c:1-146`, `hal/Makefile:64-65`

**증상:** `test_safe_state` 바이너리는 `platform_pi4.c`를 링크하지 않고 테스트 파일 내의 mock 구현만 링크한다(Makefile:64). mock의 `gw_gpio_assert_safe_state()`(test_safe_state.c:66-73)는 자체적으로 정확히 구현되어 있지만, 이것은 **실제 `platform_pi4.c`의 `gw_gpio_assert_safe_state()`가 libgpiod를 통해 핀을 LOW로 설정하는지를 전혀 검증하지 않는다.**

핵심 우려: `platform_pi4.c`의 `gw_gpio_assert_safe_state()` 내 mutex deadlock(H1) 및 libgpiod 오류 무시 동작(best-effort)은 mock으로는 드러나지 않는다.

**영향:** IRON RULE C1 ("NC fail-safe") 의 실제 구현 검증이 "Pi 4 디바이스 통합 테스트(smoke_test.sh)"에만 의존 — 이 통합 테스트 파일이 리포지토리에 존재하지 않는다(docs/HAL_ABI.md:133에서 언급만 함). CI 환경에서 C1이 실제로 테스트되지 않는 상태.

**해결안:** `libgpiod`를 직접 mock할 수 있는 thin wrapper layer 또는 `LD_PRELOAD`를 이용한 `libgpiod_mock.so`를 만들어, `platform_pi4.c`를 실제로 링크한 채 safe_state 동작을 검증하는 테스트 추가. 최소한 `smoke_test.sh`를 리포지토리에 추가하고 CI 스크립트에 포함.

---

## 🟡 MEDIUM

### M1. `gw_hal_version()` — `__DATE__`/`__TIME__` 재현 불가능 빌드

**파일:** `hal/src/common.c:31`

**증상:**
```c
snprintf(buf, size, "libgw_hal %s (built %s %s)", HAL_VERSION, __DATE__, __TIME__);
```
`__DATE__`와 `__TIME__`은 컴파일 시간에 따라 달라져 동일 소스의 두 번 빌드가 다른 버전 문자열을 생성한다. Docker 재현 빌드, 이진 동일성 검사 실패 원인.

**해결안:** `SOURCE_DATE_EPOCH` 환경변수 기반 결정론적 빌드 타임스탬프 사용, 또는 Makefile에서 `-DBUILD_TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"` 주입.

---

### M2. `gw_gpio_request_output()` / `gw_gpio_request_input()` — `alloc_slot()` 후 `gpiod_chip_get_line()` 실패 시 슬롯 정리 불완전

**파일:** `hal/src/platform_pi4.c:100-117`

**증상:** `alloc_slot()`이 성공하면 `g_lines[i].pin = pin`이 설정된다. 이후 `gpiod_chip_get_line()` 또는 `gpiod_line_request_output()` 실패 시 `slot->pin = -1`로 롤백하지만 `slot->line = NULL` 설정은 없다. `alloc_slot()`은 `g_lines[i].line == NULL`을 기준으로 빈 슬롯을 찾는데(platform_pi4.c:57), `line`이 NULL인 채로 `pin`만 -1로 롤백되면 이후 `alloc_slot()`이 해당 슬롯을 정상적으로 재사용하므로 실제 문제는 없다. 그러나 `find_slot()`(platform_pi4.c:47-52)은 `g_lines[i].pin == pin && g_lines[i].line != NULL` 둘 다 체크하므로 OK. **실제 문제는 없지만** 의도가 불명확해 유지보수 시 버그 유입 가능.

**해결안:** 실패 경로에서 `slot->pin = -1; slot->line = NULL; slot->is_output = 0;`로 명시적 전체 리셋하거나, `memset(slot, 0, sizeof(*slot)); slot->pin = -1;`로 일관.

---

### M3. `gw_err_t` enum에 명시적 정수값 있으나 `GW_ERR_INTERNAL = -99` — 범위 불연속

**파일:** `hal/include/gw_hal.h:26-36`

**증상:** 에러 코드가 -1 ~ -7 이후 -99로 점프. Go 바인딩(hal.go:31-38)도 -99는 명시적으로 처리하지 않아 `default: fmt.Sprintf("hal: unknown error %d", ...)` 경로로 빠진다. 운영 로그에서 -99가 나타나면 "unknown error"로 표시.

**해결안:** Go 바인딩에 `ErrInternal Err = -99` 상수 추가 및 `Error()` switch에 포함. 또는 ABI 문서에 -99의 의미를 명확히 서술.

---

### M4. `Makefile` — 테스트 빌드에 `-Werror` 누락, `test_safe_state` / `test_gpio_mock`에 `-lgpiod` 불필요 링크 확인 불가

**파일:** `hal/Makefile:29`

**증상:**
```makefile
TEST_CFLAGS := -Wall -Wextra -O0 -g -std=c11 -Iinclude -pthread
```
`-Werror`가 없다. 프로덕션 빌드(`CFLAGS:11`)에는 `-Werror`가 있으나 테스트 빌드에는 없어, 테스트 소스의 경고가 조용히 무시된다.

또한 `test_safe_state`와 `test_gpio_mock`에서 `gw_rs485_*`, `gw_watchdog_*` stub을 직접 정의하는데, 향후 ABI에 함수 추가 시 stub 갱신을 잊으면 link 오류가 발생한다. `--whole-archive` 없이 link satisfaction stub을 수동 유지하는 패턴은 깨지기 쉽다.

**해결안:** `TEST_CFLAGS`에 `-Werror` 추가. 장기적으로 linker wrap (`-Wl,--wrap=gpiod_chip_open` 등) 또는 weak symbol 기반 mock으로 교체 검토.

---

### M5. ABI 문서 `HAL_ABI.md` vs 헤더 `gw_hal.h` 불일치: `gw_watchdog_open()` timeout 범위

**파일:** `hal/docs/HAL_ABI.md:80`, `hal/src/watchdog.c:23`

**증상:** 헤더 주석(gw_hal.h:120): `BCM2835 WDT는 최대 15초`. ABI 문서(HAL_ABI.md:80): `1-60초`. watchdog.c 구현(line:23): `if (timeout_sec < 1 || timeout_sec > 60)` — 60초까지 허용. BCM2835 WDT 하드웨어 최대는 약 15초이므로 `gw_watchdog_open(60)`은 GW_OK를 반환하지만 실제 하드웨어는 timeout을 15초로 clamp한다(`WDIOC_SETTIMEOUT` 후 `WDIOC_GETTIMEOUT`으로 읽으면 다른 값이 나올 수 있음). Go 에이전트가 60초를 설정하고 30초마다 kick하면 안전하다고 착각할 수 있다.

**해결안:** `WDIOC_SETTIMEOUT` 호출 후 `WDIOC_GETTIMEOUT`으로 실제 설정된 값을 읽고, 요청값과 다르면 로그 경고 또는 `GW_ERR_IO` 반환. 헤더 주석과 ABI 문서의 상한을 15초로 일치시키거나, "하드웨어가 clamp할 수 있음" 명시.

---

## 🔵 BETTER ALTERNATIVES

### B1. ABI 버전 필드 없음 — 런타임 버전 불일치 감지 불가

현재 `gw_hal.h`에 버전 숫자 상수(`GW_HAL_ABI_VERSION`)가 없다. Go 바인딩이 헤더 기준으로 컴파일되고 `.so`는 다른 버전이 설치되어 있어도 로드에 성공한다. `gw_hal_version()`이 문자열을 반환하지만 Go 측에서 파싱해서 비교하는 코드가 없다(hal.go 확인).

**권장 (Phase 1):** `#define GW_HAL_ABI_VERSION 1` 추가 + `gw_hal_get_abi_version(void)` 함수로 정수 반환. Go Init() 에서 버전 확인 후 불일치 시 fatal. 또는 소넷 ELF symbol versioning (`GLIBC_2.17` 패턴처럼 `GW_HAL_1.0` 버전 스크립트).

---

### B2. RS485 fd를 Go 레이어에서 int로 노출 — 실수로 잘못된 fd 전달 가능

`gw_rs485_open()`이 raw fd를 반환하고, `gw_rs485_modbus_read()` / `gw_rs485_close()` 모두 `int fd`를 받는다. Go 레이어(hal.go)도 `int`로 그대로 노출. cgo 호출 시 유효하지 않은 fd(`-1`, 이미 닫힌 fd, watchdog fd)를 실수로 전달해도 C 측에서는 `fd < 0` 체크만 한다. 열린 watchdog fd를 modbus_read에 전달하면 `/dev/watchdog`에 read를 시도해 `GW_ERR_IO`를 반환할 뿐 구분이 안 된다.

**권장 (Phase 1+):** Go 측에서 `RS485Handle` / `WatchdogHandle` 타입 wrapper struct로 fd를 감싸 타입 안전성 확보. C API는 변경 불필요.

---

### B3. `gw_rs485_open()` — 동일 포트를 두 번 열면 두 개의 fd 반환

현재 `gw_rs485_open()`은 `/dev/ttyUSB0`를 두 번 호출해도 두 개의 독립적인 fd를 반환한다. Go 에이전트가 실수로 포트를 두 번 열면 한 fd의 write가 다른 fd의 read와 충돌해 Modbus 프레임이 깨진다. USB 어댑터 재연결(udev rename `/dev/ttyUSB0` → `/dev/ttyUSB1` → 다시 `/dev/ttyUSB0`) 시 오래된 fd가 아직 열려 있으면 동일 상황 발생.

**권장:** HAL 내부에 열린 포트 경로 레지스트리(mutex로 보호된 `char*` 배열)를 두고 중복 open을 `GW_ERR_BUSY`로 거부. 또는 Go 레이어에서 한 번만 open하도록 강제하는 관리 패턴 문서화.

---

## 권장 수정 우선순위

| 순위 | 항목 | 예상 시간 |
|---|---|---|
| 1 | C1: `gw_gpio_cleanup_internal()` 추가, `gw_hal_cleanup()`에서 호출 | 1시간 |
| 2 | C3: exception response 먼저 읽기 + `GW_ERR_IO` 정확 반환 | 1시간 |
| 3 | H1: `pthread_mutex_trylock`으로 safe_state deadlock 방지 | 30분 |
| 4 | C2: `read_with_timeout()` 단조 시계 기반 전체 타임아웃 | 1시간 |
| 5 | H2: `gw_hal_cleanup()` ↔ `g_gpio_initialized` 리셋 (C1과 동일 수정) | 0분 (C1 포함) |
| 6 | H3: slave 주소 0 / 247 초과 검증 추가 | 15분 |
| 7 | M5: `WDIOC_GETTIMEOUT` 확인 + 문서 일치 | 30분 |
| 8 | H4: `smoke_test.sh` 리포지토리 추가 + CI 포함 | 2시간 |
| 9 | M1-M4 개선 | 1-2시간 |
| 10 | B1-B3 구조 개선 (Phase 1 검토) | Phase 1 Sprint |

**합계 (1~8):** 약 6-7시간.

---

## Conclusion

**현 상태 평가:** 구조는 탄탄하고 설계 원칙(NC fail-safe, mutex 보호, best-effort safe state)이 일관되게 유지되고 있다. CRC 구현, termios 설정, watchdog magic close, libgpiod v1 API 사용이 모두 정확하다. 테스트 커버리지도 정상 경로(read/write/CRC/timeout)를 잘 다루고 있다.

그러나 **CRITICAL 3건이 운영 안전성을 직접 위협한다.** C1(GPIO cleanup 누락)은 장기 운영에서 FD 고갈을 유발하고 재초기화 시 dangling 포인터 UB를 만든다. C2(타임아웃 누적)는 느린 센서 환경에서 watchdog kick 지연 → 의도치 않은 reboot을 일으킬 수 있다. C3(exception response 판별 불가)는 Modbus 오류 진단 능력을 근본적으로 약화시키고, 테스트에서 버그를 허용하는 `GW_ERR_IO or TIMEOUT` 이중 수용으로 숨겨져 있다.

**다음 sprint 우선순위:** C1+H2(동일 수정), C3, H1을 단일 작업으로 묶어 2-3시간 안에 해결 가능. 이 세 수정이 완료되면 Phase 0 Pi 4 운영에 적합한 수준에 도달한다. H3(slave 검증), M5(watchdog 범위 문서화)는 추가 30분으로 마무리. B1-B3는 Phase 1 R1124 플랫폼 추가 전에 ABI 설계 리뷰로 처리하길 권장한다.
