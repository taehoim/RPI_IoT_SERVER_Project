/**
 * gw_hal.h — Gateway Hardware Abstraction Layer ABI
 *
 * Phase 0 platform: Raspberry Pi 4 (BCM2711)
 * Future platforms: Seeed reComputer R1124-10, 자체 PCB
 *
 * 모든 함수는 thread-safe 가정. cgo binding (Go) 또는 직접 C에서 호출.
 * 반환 0 = 성공, 음수 = gw_err_t (에러 코드)
 *
 * 안전 원칙:
 *   - gw_gpio_assert_safe_state()는 panic/abort/init 시 반드시 호출
 *   - NC(Normally Closed) 와이어링 가정: pin LOW = relay open = safe
 */

#ifndef GW_HAL_H
#define GW_HAL_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ===== Error codes (음수만 사용) ===== */
typedef enum {
    GW_OK            =  0,
    GW_ERR_TIMEOUT   = -1,
    GW_ERR_CRC       = -2,
    GW_ERR_IO        = -3,
    GW_ERR_INVALID   = -4,   /* 잘못된 파라미터 */
    GW_ERR_NOT_INIT  = -5,   /* gw_*_init() 호출 전 */
    GW_ERR_BUSY      = -6,
    GW_ERR_PERM      = -7,   /* permission denied (예: gpio chip) */
    GW_ERR_INTERNAL  = -99,
} gw_err_t;

/* ===== Lifecycle ===== */

/** 라이브러리 초기화. 멱등 (여러 번 호출해도 안전). */
int gw_hal_init(void);

/** 라이브러리 정리. assert_safe_state도 호출됨. */
int gw_hal_cleanup(void);

/** ABI/build 정보. version_buf >= 64. */
int gw_hal_version(char* version_buf, size_t buf_size);

/* ===== GPIO (DI / DO) ===== */

/**
 * GPIO 초기화. /dev/gpiochip0 (Pi 4 default) 오픈.
 * @return GW_OK 또는 GW_ERR_PERM (group 'gpio' 멤버 아님), GW_ERR_IO
 */
int gw_gpio_init(void);

/**
 * 단일 라인을 OUTPUT으로 reserve + 초기 값 설정.
 * @param pin BCM 핀 번호 (예: 17)
 * @param initial_value 0 또는 1
 * @return GW_OK 또는 GW_ERR_BUSY (이미 reserve됨), GW_ERR_INVALID
 */
int gw_gpio_request_output(int pin, int initial_value);

/**
 * 단일 라인을 INPUT으로 reserve.
 * @param pin BCM 핀 번호
 * @param pull 0=none, 1=pull-up, -1=pull-down
 */
int gw_gpio_request_input(int pin, int pull);

/** Output pin에 값 쓰기. */
int gw_gpio_set(int pin, int value);

/** Input pin 값 읽기. value_out에 0 또는 1 저장. */
int gw_gpio_get(int pin, int* value_out);

/**
 * 모든 reserve된 OUTPUT pin을 NC 안전 상태(0)로 강제.
 * panic / abort / cleanup / watchdog timeout 시 호출.
 * 이 함수는 절대 실패하지 않음 (best-effort, 실패해도 0 반환).
 * 시그널 핸들러 안전 (trylock 사용).
 */
int gw_gpio_assert_safe_state(void);

/**
 * 모든 line release + gpio chip close + 내부 상태 리셋.
 * gw_hal_cleanup에서 assert_safe_state 직후 호출됨. 멱등.
 * 미호출 시 fd 누수 + 재초기화 경로의 dangling pointer UB.
 */
int gw_gpio_cleanup(void);

/* ===== RS-485 / Modbus RTU ===== */

/**
 * RS-485 시리얼 포트 오픈.
 * @param dev "/dev/ttyUSB0" 등
 * @param baud 9600, 19200, 38400, 115200
 * @param parity 'N', 'E', 'O'
 * @param data_bits 7 또는 8
 * @param stop_bits 1 또는 2
 * @return file descriptor (>= 0) 또는 GW_ERR_*
 */
int gw_rs485_open(const char* dev, int baud, char parity, int data_bits, int stop_bits);

/**
 * Modbus RTU read holding registers (function code 0x03).
 * out 버퍼는 length × uint16_t 만큼 할당되어야 함.
 * CRC 자동 검증, mismatch 시 GW_ERR_CRC.
 * @param timeout_ms 응답 대기 시간 (보통 200ms)
 */
int gw_rs485_modbus_read(int fd, uint8_t slave, uint8_t function_code,
                         uint16_t register_addr, uint16_t length,
                         uint16_t* out, int timeout_ms);

/** Modbus RTU write single register (function code 0x06). */
int gw_rs485_modbus_write(int fd, uint8_t slave, uint16_t register_addr,
                          uint16_t value, int timeout_ms);

/** RS-485 포트 닫기. */
int gw_rs485_close(int fd);

/* ===== Kernel Watchdog (/dev/watchdog) ===== */

/**
 * /dev/watchdog 오픈 + timeout 설정.
 * @param timeout_sec BCM2835 WDT는 최대 15초
 * @return file descriptor 또는 GW_ERR_*
 */
int gw_watchdog_open(int timeout_sec);

/** Watchdog kick. timeout 내 호출 안하면 hardware reboot. */
int gw_watchdog_kick(int fd);

/** Watchdog 닫기. magic close (V) 전송하여 disable. */
int gw_watchdog_close(int fd);

/* ===== 4G Modem (Phase 1+ stub, R1124-10에서 구현) ===== */

/**
 * AT 명령 전송 + 응답 수신.
 * Phase 0에서는 GW_ERR_NOT_INIT 반환 (구현 안됨).
 */
int gw_modem_at(const char* cmd, char* response_out, size_t resp_size, int timeout_ms);

/** Modem soft reset (AT+CFUN=1,1). Phase 0 stub. */
int gw_modem_reset_soft(void);

/** Modem hard reset (GPIO power-cycle). 자체 PCB만 가능. Phase 0 stub. */
int gw_modem_reset_hard(void);

#ifdef __cplusplus
}
#endif

#endif /* GW_HAL_H */
