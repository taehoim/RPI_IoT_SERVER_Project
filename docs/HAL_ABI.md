# HAL ABI 명세 (gw_hal.h v0.1.0)

## 설계 원칙

1. **플랫폼 무관성** — gw_hal.h는 Pi 4 / CM4 (eMMC) / R1124-10 / 자체 PCB 모두에서 동일.
2. **명시적 에러** — 모든 함수는 `int` 반환 (0=성공, 음수=`gw_err_t`).
3. **Thread-safe** — C 측 mutex로 보호, Go에서 동시 호출 안전.
4. **Best-effort safe state** — `gw_gpio_assert_safe_state()`는 절대 실패하지 않음 (panic 경로 보호).
5. **NC wiring 가정** — DO pin 0 = relay open = safe state.

## Error codes

| 코드 | enum | 의미 |
|---|---|---|
| 0 | GW_OK | 성공 |
| -1 | GW_ERR_TIMEOUT | RS485 응답 timeout |
| -2 | GW_ERR_CRC | Modbus CRC mismatch |
| -3 | GW_ERR_IO | 일반 I/O 오류 |
| -4 | GW_ERR_INVALID | 잘못된 파라미터 |
| -5 | GW_ERR_NOT_INIT | init 미호출 또는 platform 미지원 |
| -6 | GW_ERR_BUSY | pin 이미 reserve, slot 부족 |
| -7 | GW_ERR_PERM | permission denied (group 미가입 등) |
| -99 | GW_ERR_INTERNAL | 내부 오류 (snprintf 실패 등 호출자 영향 없는 자체 결함) |

## Lifecycle

```c
int gw_hal_init(void);                              // 멱등
int gw_hal_cleanup(void);                           // assert_safe_state 호출 보장
int gw_hal_version(char* buf, size_t size);         // "libgw_hal 0.1.0-pi4-phase0 (built ...)"
```

## GPIO

```c
int gw_gpio_init(void);                             // /dev/gpiochip0 open
int gw_gpio_request_output(int pin, int initial);   // BCM 0-53, init 0|1
int gw_gpio_request_input(int pin, int pull);       // pull: 0=none, 1=up, -1=down
int gw_gpio_set(int pin, int value);                // 이미 reserve된 OUTPUT만
int gw_gpio_get(int pin, int* value_out);           // INPUT or OUTPUT
int gw_gpio_assert_safe_state(void);                // 모든 OUTPUT 0 (signal-handler safe, trylock)
int gw_gpio_cleanup(void);                          // line/chip release + 상태 리셋 (멱등)
int gw_gpio_assert_safe_state(void);                // 모든 OUTPUT을 0으로, 항상 GW_OK
```

**플랫폼별:**
- `platform_pi4.c`: BCM2711 SoC 기반 — **Pi 4 (microSD) + CM4 (eMMC) 공통**. libgpiod v1.x, Bookworm apt 기본. `/dev/gpiochip0`, `/dev/watchdog`, `/dev/ttyUSB*` 모두 동일 ABI.
- `platform_r1124.c`: Phase 1+ stub. R1124-10도 같은 BCM2711이지만 carrier board의 IO expander (MCP23017 등) 매핑 추가 필요.

> **Pi 5는 별도** — `/dev/gpiochip4` 사용. 향후 `platform_pi5.c` 추가 예정.

## RS-485 / Modbus RTU

```c
int gw_rs485_open(const char* dev, int baud, char parity, int data, int stop);
//   dev: "/dev/ttyUSB0"
//   baud: 9600, 19200, 38400, 57600, 115200
//   parity: 'N' | 'E' | 'O'
//   data_bits: 7 | 8
//   stop_bits: 1 | 2
//   반환: fd >= 0 또는 GW_ERR_*

int gw_rs485_modbus_read(int fd, uint8_t slave, uint8_t fc,
                         uint16_t register, uint16_t length,
                         uint16_t* out, int timeout_ms);
//   fc: 0x03 (holding) | 0x04 (input)
//   length: 1-125
//   timeout_ms: 보통 200ms

int gw_rs485_modbus_write(int fd, uint8_t slave, uint16_t register,
                          uint16_t value, int timeout_ms);
//   function code 0x06 (write single register)

int gw_rs485_close(int fd);
```

USB-RS485 어댑터(FT232/CH340 + MAX485)는 자동 DE/RE 토글.
자체 GPIO DE/RE 제어가 필요한 경우 platform_*.c 에서 wrapper 추가.

## Watchdog (kernel /dev/watchdog)

```c
int gw_watchdog_open(int timeout_sec);    // 1-60초, BCM2835 max ~15
int gw_watchdog_kick(int fd);             // 주기 호출 필수
int gw_watchdog_close(int fd);            // magic 'V' close → WDT disable
```

## 4G modem (Phase 1+)

Phase 0에서는 모두 `GW_ERR_NOT_INIT` 반환 (stub).

```c
int gw_modem_at(const char* cmd, char* response, size_t size, int timeout_ms);
int gw_modem_reset_soft(void);    // AT+CFUN=1,1
int gw_modem_reset_hard(void);    // GPIO power-cycle (자체 PCB만)
```

## ABI 변경 정책

- **patch (0.1.x):** 새 enum 값, 새 함수 추가 (기존 ABI 유지)
- **minor (0.x.0):** 기존 함수 시그니처는 deprecated 마킹 + 새 함수 추가, 한 minor 후 제거
- **major (x.0.0):** 모든 호출자 동시 재컴파일 필요

`gw_hal_version()` 결과 첫 토큰을 항상 확인할 것.

## Cgo binding (Go)

```go
package hal
/*
#cgo CFLAGS: -I${SRCDIR}/../../../hal/include
#cgo LDFLAGS: -lgw_hal -lpthread
#include <stdlib.h>
#include <gw_hal.h>
*/
import "C"
```

빌드 환경:
```bash
# install 후 (gw_hal.h → /usr/local/include, libgw_hal.so → /usr/local/lib)
CGO_ENABLED=1 go build ./...

# 또는 install 없이 in-place:
CGO_CFLAGS="-I$REPO/hal/include" \
CGO_LDFLAGS="-L$REPO/hal/build -lgw_hal" \
LD_LIBRARY_PATH="$REPO/hal/build" \
go build ./...
```

## 테스트 전략

- `hal/tests/test_rs485_pty.c` — PTY pair로 Modbus RTU master/slave 시뮬, CRC/timeout/exception
- `hal/tests/test_gpio_mock.c` — ABI 호환성 + invalid input 거부 (libgpiod 안 link)
- `hal/tests/test_safe_state.c` — IRON RULE C1, mock backend로 NC 강제 검증
- 진짜 libgpiod backend는 CM4/Pi 4 디바이스 통합 테스트(smoke_test.sh)로 검증
