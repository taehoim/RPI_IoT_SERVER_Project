//go:build !simulation
// +build !simulation

// Package hal — cgo binding to libgw_hal.so
//
// 모든 HAL 함수는 thread-safe (C 측 mutex로 보호).
// 에러는 GW_OK(0) 외 음수, gw_err_t enum.
//
// 빌드:
//
//	CGO_ENABLED=1 CGO_LDFLAGS="-L../../hal/build -lgw_hal" \
//	  LD_LIBRARY_PATH=../../hal/build go build ./...
//
// 또는 hal/Makefile install 후:
//
//	go build ./cmd/gateway-agent
//
// 시뮬레이션 빌드 (cgo + libgw_hal.so 불필요):
//
//	go build -tags simulation ./cmd/gateway-agent
//	→ hal_sim.go가 사용됨 (모든 HAL 호출이 noop 성공)
package hal

/*
#cgo CFLAGS: -I${SRCDIR}/../../../hal/include
#cgo LDFLAGS: -lgw_hal -lpthread
#include <stdlib.h>
#include <gw_hal.h>
*/
import "C"

import (
	"fmt"
	"unsafe"
)

// Err — HAL 에러 (음수 코드)
type Err int

const (
	OK          Err = 0
	ErrTimeout  Err = -1
	ErrCRC      Err = -2
	ErrIO       Err = -3
	ErrInvalid  Err = -4
	ErrNotInit  Err = -5
	ErrBusy     Err = -6
	ErrPerm     Err = -7
	ErrInternal Err = -99
)

func (e Err) Error() string {
	switch e {
	case OK:
		return "ok"
	case ErrTimeout:
		return "hal: timeout"
	case ErrCRC:
		return "hal: CRC mismatch"
	case ErrIO:
		return "hal: I/O error"
	case ErrInvalid:
		return "hal: invalid argument"
	case ErrNotInit:
		return "hal: not initialized"
	case ErrBusy:
		return "hal: busy"
	case ErrPerm:
		return "hal: permission denied (check 'gpio' group / udev rule)"
	case ErrInternal:
		return "hal: internal error"
	default:
		return fmt.Sprintf("hal: unknown error %d", int(e))
	}
}

func wrap(rc C.int) error {
	if rc == 0 {
		return nil
	}
	return Err(int(rc))
}

// ===== Lifecycle =====

// Init — HAL 초기화. main 시작 시 1회 호출.
func Init() error {
	if rc := C.gw_hal_init(); rc != 0 {
		return wrap(rc)
	}
	return wrap(C.gw_gpio_init())
}

// Cleanup — HAL 정리. defer 또는 shutdown 시 호출.
// 내부적으로 AssertSafeState 호출 보장.
func Cleanup() error {
	return wrap(C.gw_hal_cleanup())
}

// Version — 라이브러리 버전 문자열
func Version() (string, error) {
	buf := make([]byte, 64)
	rc := C.gw_hal_version((*C.char)(unsafe.Pointer(&buf[0])), 64)
	if rc != 0 {
		return "", wrap(rc)
	}
	// null terminator 위치 찾기
	for i, b := range buf {
		if b == 0 {
			return string(buf[:i]), nil
		}
	}
	return string(buf), nil
}

// ===== GPIO =====

// RequestOutput — output pin reserve + 초기 값 설정
func RequestOutput(pin int, initialValue int) error {
	return wrap(C.gw_gpio_request_output(C.int(pin), C.int(initialValue)))
}

// RequestInput — input pin reserve. pull: 0=none, 1=up, -1=down
func RequestInput(pin int, pull int) error {
	return wrap(C.gw_gpio_request_input(C.int(pin), C.int(pull)))
}

// GPIOSet — output pin 값 쓰기
func GPIOSet(pin int, value int) error {
	return wrap(C.gw_gpio_set(C.int(pin), C.int(value)))
}

// GPIOGet — input pin 값 읽기
func GPIOGet(pin int) (int, error) {
	var v C.int
	if rc := C.gw_gpio_get(C.int(pin), &v); rc != 0 {
		return 0, wrap(rc)
	}
	return int(v), nil
}

// AssertSafeState — 모든 OUTPUT pin을 NC 안전 상태(LOW)로 강제
// panic / abort / cleanup 경로에서 반드시 호출.
func AssertSafeState() {
	C.gw_gpio_assert_safe_state()
}

// ===== RS-485 / Modbus =====

// RS485Open — 시리얼 포트 오픈. 반환 fd는 ModbusRead/Write/Close에 사용.
func RS485Open(dev string, baud int, parity byte, dataBits, stopBits int) (int, error) {
	cdev := C.CString(dev)
	defer C.free(unsafe.Pointer(cdev))
	rc := C.gw_rs485_open(cdev, C.int(baud), C.char(parity), C.int(dataBits), C.int(stopBits))
	if rc < 0 {
		return -1, wrap(rc)
	}
	return int(rc), nil
}

// ModbusRead — function 0x03/0x04 holding/input registers 읽기
func ModbusRead(fd int, slave uint8, functionCode uint8, registerAddr, length uint16, timeoutMs int) ([]uint16, error) {
	if length == 0 || length > 125 {
		return nil, ErrInvalid
	}
	buf := make([]C.uint16_t, length)
	rc := C.gw_rs485_modbus_read(C.int(fd), C.uint8_t(slave), C.uint8_t(functionCode),
		C.uint16_t(registerAddr), C.uint16_t(length), &buf[0], C.int(timeoutMs))
	if rc != 0 {
		return nil, wrap(rc)
	}
	out := make([]uint16, length)
	for i := range out {
		out[i] = uint16(buf[i])
	}
	return out, nil
}

// ModbusWrite — function 0x06 single register 쓰기
func ModbusWrite(fd int, slave uint8, registerAddr, value uint16, timeoutMs int) error {
	return wrap(C.gw_rs485_modbus_write(C.int(fd), C.uint8_t(slave),
		C.uint16_t(registerAddr), C.uint16_t(value), C.int(timeoutMs)))
}

// RS485Close — 포트 닫기
func RS485Close(fd int) error {
	return wrap(C.gw_rs485_close(C.int(fd)))
}

// ===== Watchdog =====

// WatchdogOpen — /dev/watchdog open + timeout 설정
func WatchdogOpen(timeoutSec int) (int, error) {
	rc := C.gw_watchdog_open(C.int(timeoutSec))
	if rc < 0 {
		return -1, wrap(rc)
	}
	return int(rc), nil
}

// WatchdogKick — kick. timeout 내 호출 안하면 hardware reboot.
func WatchdogKick(fd int) error {
	return wrap(C.gw_watchdog_kick(C.int(fd)))
}

// WatchdogClose — magic close 후 닫기 (WDT disable)
func WatchdogClose(fd int) error {
	return wrap(C.gw_watchdog_close(C.int(fd)))
}

// ===== 4G Modem (Phase 0 stub, R1124-10 Phase 1+에서 구현) =====

// ModemAT — AT 명령 전송 + 응답 수신. Phase 0에서는 ErrNotInit 반환.
func ModemAT(cmd string, respSize int, timeoutMs int) (string, error) {
	if respSize <= 0 {
		respSize = 256
	}
	cCmd := C.CString(cmd)
	defer C.free(unsafe.Pointer(cCmd))
	buf := (*C.char)(C.malloc(C.size_t(respSize)))
	defer C.free(unsafe.Pointer(buf))
	rc := C.gw_modem_at(cCmd, buf, C.size_t(respSize), C.int(timeoutMs))
	if rc != 0 {
		return "", wrap(rc)
	}
	return C.GoString(buf), nil
}

// ModemResetSoft — AT+CFUN=1,1. Phase 0에서는 ErrNotInit.
func ModemResetSoft() error {
	return wrap(C.gw_modem_reset_soft())
}

// ModemResetHard — GPIO power-cycle. 자체 PCB만 가능. Phase 0에서는 ErrNotInit.
func ModemResetHard() error {
	return wrap(C.gw_modem_reset_hard())
}
