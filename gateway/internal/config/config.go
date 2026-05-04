// Package config — YAML 설정 로딩 + 유효성 검증
//
// Gateway agent의 단일 진입 설정 파일. CLI flag --config 으로 경로 전달.
//
// 검증 실패 시 즉시 error 반환 → main이 systemd에 Failed status report.
package config

import (
	"fmt"
	"os"
	"regexp"

	"gopkg.in/yaml.v3"
)

// gatewayIDPattern — MQTT topic injection 차단.
// `+`/`#`/`/` 가 들어가면 와일드카드/계층 분리자로 해석되어 다른 gateway 토픽
// subscribe/publish 가능. 영숫자 + `-` + `_` 만 허용.
var gatewayIDPattern = regexp.MustCompile(`^[A-Za-z0-9_-]+$`)

// Config — 전체 게이트웨이 설정
type Config struct {
	Gateway    GatewayConfig     `yaml:"gateway"`
	MQTT       MQTTConfig        `yaml:"mqtt"`
	Storage    StorageConfig     `yaml:"storage"`
	Watchdog   WatchdogConfig    `yaml:"watchdog"`
	Sensors    []SensorChannel   `yaml:"sensors"`
	Actuators  []ActuatorChannel `yaml:"actuators"`
	Simulation SimulationConfig  `yaml:"simulation"`
}

// SimulationConfig — 가상 센서/액추에이터 모드.
// enabled=true 면 sensor.go가 HAL.ModbusRead 대신 합성 데이터 생성, actuator는 GPIO 호출 우회.
// 비-Pi 환경 (WSL/x86 Ubuntu/Mac)에서 wire 흐름 검증 가능.
type SimulationConfig struct {
	Enabled       bool    `yaml:"enabled"`        // false (default) = 실 하드웨어
	Pattern       string  `yaml:"pattern"`        // "sine" (default) | "random_walk" | "fixed"
	JitterPercent float64 `yaml:"jitter_percent"` // 추가 노이즈 비율, default 2.0%
	Seed          int64   `yaml:"seed"`           // 재현 가능한 시퀀스용. 0이면 시간 기반.
}

// GatewayConfig — gateway 자체 식별 + 운영 파라미터
type GatewayConfig struct {
	ID                string `yaml:"id"`                  // "GW-DEV01" 등
	Name              string `yaml:"name"`                // 표시 이름
	HeartbeatSec      int    `yaml:"heartbeat_sec"`       // 30
	LocalReadyTimeout int    `yaml:"local_ready_timeout"` // sd_notify READY까지 최대 초
}

// MQTTConfig — Phase 0은 plain 1883, Phase 7부터 TLS
type MQTTConfig struct {
	Broker            string `yaml:"broker"`             // tcp://127.0.0.1:1883
	Username          string `yaml:"username,omitempty"` // Phase 0 anonymous OK
	Password          string `yaml:"password,omitempty"`
	ClientID          string `yaml:"client_id"`           // gateway-{ID} 권장
	KeepaliveSec      int    `yaml:"keepalive_sec"`       // 30
	ConnectTimeoutSec int    `yaml:"connect_timeout_sec"` // 10
	QoS               byte   `yaml:"qos"`                 // 1
	CleanSession      bool   `yaml:"clean_session"`       // false (LWT 활용)
}

// StorageConfig — local SQLite buffer
type StorageConfig struct {
	DBPath           string `yaml:"db_path"`             // /var/lib/iot-gateway/local.db
	RetentionDays    int    `yaml:"retention_days"`      // 7
	MaxQueueRows     int    `yaml:"max_queue_rows"`      // 100000
	DiskUsageWarnPct int    `yaml:"disk_usage_warn_pct"` // 90
}

// WatchdogConfig — systemd + kernel WDT 양쪽
type WatchdogConfig struct {
	SDNotifyIntervalSec int  `yaml:"sd_notify_interval_sec"` // 10
	KernelWDTEnabled    bool `yaml:"kernel_wdt_enabled"`     // true on Pi
	KernelWDTTimeoutSec int  `yaml:"kernel_wdt_timeout_sec"` // 15 (BCM2835 max)
	KernelWDTKickSec    int  `yaml:"kernel_wdt_kick_sec"`    // 5
}

// SensorChannel — Sensor Profile 참조 + Gateway 연결 정보
type SensorChannel struct {
	ChannelID          string `yaml:"channel_id"`           // sensor-01
	DisplayName        string `yaml:"display_name"`         // 1번 NH3 센서
	ProfileFile        string `yaml:"profile_file"`         // shared/examples/nh3_rs485.json
	Interface          string `yaml:"interface"`            // /dev/ttyUSB0
	Baud               int    `yaml:"baud"`                 // 9600
	Parity             string `yaml:"parity"`               // "N"
	DataBits           int    `yaml:"data_bits"`            // 8
	StopBits           int    `yaml:"stop_bits"`            // 1
	SlaveID            int    `yaml:"slave_id"`             // 1
	PollingIntervalSec int    `yaml:"polling_interval_sec"` // 10
	Enabled            bool   `yaml:"enabled"`              // true
}

// ActuatorChannel — 릴레이/밸브/펌프 등
type ActuatorChannel struct {
	ChannelID        string `yaml:"channel_id"`          // relay-01
	DisplayName      string `yaml:"display_name"`        // 살균기
	Type             string `yaml:"type"`                // "relay"
	GPIOPin          int    `yaml:"gpio_pin"`            // 17 (BCM)
	DefaultState     string `yaml:"default_state"`       // "off"
	MaxOnDurationSec int    `yaml:"max_on_duration_sec"` // 300 (5분)
	Enabled          bool   `yaml:"enabled"`             // true
}

// Load — 파일에서 YAML 로드 + 유효성 검증
func Load(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read config: %w", err)
	}

	var cfg Config
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("parse yaml: %w", err)
	}

	if err := cfg.Validate(); err != nil {
		return nil, fmt.Errorf("validate config: %w", err)
	}

	cfg.applyDefaults()
	return &cfg, nil
}

func (c *Config) applyDefaults() {
	if c.Gateway.HeartbeatSec == 0 {
		c.Gateway.HeartbeatSec = 30
	}
	if c.Gateway.LocalReadyTimeout == 0 {
		c.Gateway.LocalReadyTimeout = 30
	}
	if c.MQTT.KeepaliveSec == 0 {
		c.MQTT.KeepaliveSec = 30
	}
	if c.MQTT.ConnectTimeoutSec == 0 {
		c.MQTT.ConnectTimeoutSec = 10
	}
	if c.MQTT.QoS == 0 {
		c.MQTT.QoS = 1
	}
	if c.Storage.RetentionDays == 0 {
		c.Storage.RetentionDays = 7
	}
	if c.Storage.MaxQueueRows == 0 {
		c.Storage.MaxQueueRows = 100000
	}
	if c.Storage.DiskUsageWarnPct == 0 {
		c.Storage.DiskUsageWarnPct = 90
	}
	if c.Watchdog.SDNotifyIntervalSec == 0 {
		c.Watchdog.SDNotifyIntervalSec = 10
	}
	if c.Watchdog.KernelWDTTimeoutSec == 0 {
		c.Watchdog.KernelWDTTimeoutSec = 15
	}
	if c.Watchdog.KernelWDTKickSec == 0 {
		c.Watchdog.KernelWDTKickSec = 5
	}
	for i := range c.Sensors {
		if c.Sensors[i].PollingIntervalSec == 0 {
			c.Sensors[i].PollingIntervalSec = 10
		}
	}
	for i := range c.Actuators {
		if c.Actuators[i].MaxOnDurationSec == 0 {
			c.Actuators[i].MaxOnDurationSec = 300
		}
		if c.Actuators[i].DefaultState == "" {
			c.Actuators[i].DefaultState = "off"
		}
	}
	if c.Simulation.Enabled {
		if c.Simulation.Pattern == "" {
			c.Simulation.Pattern = "sine"
		}
		if c.Simulation.JitterPercent == 0 {
			c.Simulation.JitterPercent = 2.0
		}
	}
}

// Validate — 명백히 잘못된 설정 거부
func (c *Config) Validate() error {
	if c.Gateway.ID == "" {
		return fmt.Errorf("gateway.id required")
	}
	if !gatewayIDPattern.MatchString(c.Gateway.ID) {
		return fmt.Errorf("gateway.id %q invalid: only [A-Za-z0-9_-] allowed (MQTT topic injection guard)", c.Gateway.ID)
	}
	if len(c.Gateway.ID) > 64 {
		return fmt.Errorf("gateway.id too long (>64 chars)")
	}
	if c.MQTT.Broker == "" {
		return fmt.Errorf("mqtt.broker required")
	}
	if c.Storage.DBPath == "" {
		return fmt.Errorf("storage.db_path required")
	}
	seen := map[string]bool{}
	for _, s := range c.Sensors {
		if s.ChannelID == "" {
			return fmt.Errorf("sensor channel_id required")
		}
		if seen[s.ChannelID] {
			return fmt.Errorf("duplicate sensor channel_id: %s", s.ChannelID)
		}
		seen[s.ChannelID] = true
		if s.ProfileFile == "" {
			return fmt.Errorf("sensor %s: profile_file required", s.ChannelID)
		}
		if s.Interface == "" {
			return fmt.Errorf("sensor %s: interface required", s.ChannelID)
		}
		if s.SlaveID < 1 || s.SlaveID > 247 {
			return fmt.Errorf("sensor %s: slave_id 1-247", s.ChannelID)
		}
	}
	for _, a := range c.Actuators {
		if a.ChannelID == "" {
			return fmt.Errorf("actuator channel_id required")
		}
		if seen[a.ChannelID] {
			return fmt.Errorf("duplicate channel_id: %s", a.ChannelID)
		}
		seen[a.ChannelID] = true
		if a.Type != "relay" {
			return fmt.Errorf("actuator %s: type 'relay' only (Phase 0)", a.ChannelID)
		}
		if a.GPIOPin < 0 || a.GPIOPin > 53 {
			return fmt.Errorf("actuator %s: gpio_pin 0-53 (BCM)", a.ChannelID)
		}
	}
	return nil
}
