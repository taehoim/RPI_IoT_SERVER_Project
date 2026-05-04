//go:build simulation
// +build simulation

// Package hal — SIMULATION backend (cgo 없음, libgw_hal.so 불필요).
//
// 모든 HAL 호출이 noop 성공으로 반환됨. WSL/x86 Ubuntu 등 비-Pi 환경에서 wire 흐름
// (MQTT publish/subscribe, SQLite buffer, sd_notify, sensor profile 파싱 등)을
// 검증할 수 있도록 한다.
//
// sensor.go / actuator.go는 별도로 config.Simulation.Enabled 플래그를 보고
// HAL 호출 자체를 우회하면서 합성 데이터를 생성한다.
//
// 빌드:
//
//	go build -tags simulation ./cmd/gateway-agent
package hal

import "fmt"

// Err — 동일 ABI (real과 같은 enum, 같은 값)
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
		return "hal-sim: timeout"
	case ErrCRC:
		return "hal-sim: CRC mismatch"
	case ErrIO:
		return "hal-sim: I/O error"
	case ErrInvalid:
		return "hal-sim: invalid argument"
	case ErrNotInit:
		return "hal-sim: not initialized"
	case ErrBusy:
		return "hal-sim: busy"
	case ErrPerm:
		return "hal-sim: permission denied"
	case ErrInternal:
		return "hal-sim: internal error"
	default:
		return fmt.Sprintf("hal-sim: unknown error %d", int(e))
	}
}

// ===== Lifecycle =====

func Init() error {
	return nil
}

func Cleanup() error {
	return nil
}

func Version() (string, error) {
	return "libgw_hal SIMULATION (no hardware)", nil
}

// ===== GPIO =====

func RequestOutput(pin int, initial int) error {
	return nil
}

func RequestInput(pin int, pull int) error {
	return nil
}

func GPIOSet(pin int, value int) error {
	return nil
}

func GPIOGet(pin int) (int, error) {
	return 0, nil
}

func AssertSafeState() {
	// noop — sim mode는 실제 핀이 없어 fail-safe 의미 없음
}

// ===== RS-485 / Modbus RTU =====

// RS485Open — sim에서는 fd 자리만 잡고 0 반환. sensor.go가 sim 모드면 ModbusRead 호출 안 함.
func RS485Open(dev string, baud int, parity byte, dataBits, stopBits int) (int, error) {
	return 0, nil
}

func ModbusRead(fd int, slave byte, fn byte, reg uint16, length uint16, timeoutMs int) ([]uint16, error) {
	// 0으로 채운 더미. sensor.go sim 분기에서 우회되므로 정상 운영 시 도달 안 함.
	out := make([]uint16, length)
	return out, nil
}

func ModbusWrite(fd int, slave byte, reg uint16, value uint16, timeoutMs int) error {
	return nil
}

func RS485Close(fd int) error {
	return nil
}

// ===== Watchdog =====

func WatchdogOpen(timeoutSec int) (int, error) {
	// sim mode에서는 fd 자리만 (음수 아님 → main.go가 enabled=true 분기 진입)
	return 0, nil
}

func WatchdogKick(fd int) error {
	return nil
}

func WatchdogClose(fd int) error {
	return nil
}

// ===== 4G Modem (Phase 1+ stub) =====

func ModemAT(cmd string, respSize int, timeoutMs int) (string, error) {
	return "", ErrNotInit
}

func ModemResetSoft() error {
	return ErrNotInit
}

func ModemResetHard() error {
	return ErrNotInit
}
