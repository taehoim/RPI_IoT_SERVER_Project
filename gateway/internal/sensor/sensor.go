// Package sensor — Modbus RTU 폴링 + telemetry publish
//
// 책임:
//   - Sensor Profile JSON 로드 → measurement 매핑
//   - 채널별 polling_interval_sec 주기 polling
//   - HAL의 ModbusRead 호출 → scale/offset 적용 → telemetry payload 생성
//   - 정상 → MQTT publish, 실패 → SQLite 큐 적재 + sensor health degraded
//   - CRC 실패 3회 retry, timeout은 즉시 health 갱신
package sensor

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"sync"
	"time"

	"github.com/google/uuid"

	"github.com/iot-gateway/agent/internal/config"
	"github.com/iot-gateway/agent/internal/hal"
	"github.com/iot-gateway/agent/internal/localdb"
	mqttpkg "github.com/iot-gateway/agent/internal/mqtt"
	"github.com/iot-gateway/agent/internal/sim"
)

// Profile — Sensor Profile JSON Schema
type Profile struct {
	Name              string                 `json:"name"`
	Vendor            string                 `json:"vendor"`
	Model             string                 `json:"model"`
	Protocol          string                 `json:"protocol"`       // "modbus_rtu"
	InterfaceType     string                 `json:"interface_type"` // "rs485"
	DefaultPollingSec int                    `json:"default_polling_interval_sec"`
	Connection        map[string]interface{} `json:"connection,omitempty"`
	Measurements      []Measurement          `json:"measurements"`
}

// Measurement — 측정 항목
type Measurement struct {
	Key           string     `json:"key"` // "ammonia"
	DisplayName   string     `json:"display_name"`
	Unit          string     `json:"unit"`      // "ppm"
	DataType      string     `json:"data_type"` // "float"
	Modbus        ModbusSpec `json:"modbus"`
	Scale         float64    `json:"scale"`  // 1.0 default
	Offset        float64    `json:"offset"` // 0 default
	Min           *float64   `json:"min,omitempty"`
	Max           *float64   `json:"max,omitempty"`
	Visualization string     `json:"visualization,omitempty"`
}

// ModbusSpec — Modbus register mapping
type ModbusSpec struct {
	FunctionCode int `json:"function_code"` // 3, 4
	Register     int `json:"register"`
	Length       int `json:"length"` // 1 (uint16), 2 (uint32)
}

// LoadProfile — JSON 파일에서 Profile 로드
func LoadProfile(path string) (*Profile, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read profile: %w", err)
	}
	var p Profile
	if err := json.Unmarshal(data, &p); err != nil {
		return nil, fmt.Errorf("parse profile: %w", err)
	}
	if len(p.Measurements) == 0 {
		return nil, fmt.Errorf("profile has no measurements")
	}
	for i := range p.Measurements {
		if p.Measurements[i].Scale == 0 {
			p.Measurements[i].Scale = 1.0
		}
	}
	return &p, nil
}

// channelRunner — 단일 sensor channel 폴링 상태
type channelRunner struct {
	cfg     config.SensorChannel
	profile *Profile
	fd      int
}

// Manager — 모든 sensor channel 통합 관리
type Manager struct {
	channels  []*channelRunner
	mq        *mqttpkg.Client
	db        *localdb.DB
	gatewayID string
	sim       *sim.Generator // nil이면 실 하드웨어 모드
	mu        sync.Mutex
}

// NewManager — config + Profile 로드. simCfg가 enabled이면 RS485 open 우회 + 합성 데이터 모드.
func NewManager(channels []config.SensorChannel, mq *mqttpkg.Client, db *localdb.DB, gatewayID string, simCfg config.SimulationConfig) (*Manager, error) {
	m := &Manager{
		mq:        mq,
		db:        db,
		gatewayID: gatewayID,
	}
	if simCfg.Enabled {
		m.sim = sim.New(simCfg.Pattern, simCfg.JitterPercent, simCfg.Seed)
		log.Printf("[sensor] SIMULATION mode (pattern=%s jitter=%.1f%%)", simCfg.Pattern, simCfg.JitterPercent)
	}
	for _, ch := range channels {
		if !ch.Enabled {
			continue
		}
		profile, err := LoadProfile(ch.ProfileFile)
		if err != nil {
			return nil, fmt.Errorf("channel %s: %w", ch.ChannelID, err)
		}
		var fd int
		if m.sim != nil {
			fd = -1 // 합성 모드는 실 fd 없음. pollOnce에서 분기.
		} else {
			fd, err = hal.RS485Open(ch.Interface, ch.Baud, parityByte(ch.Parity), ch.DataBits, ch.StopBits)
			if err != nil {
				return nil, fmt.Errorf("channel %s rs485 open: %w", ch.ChannelID, err)
			}
		}
		m.channels = append(m.channels, &channelRunner{cfg: ch, profile: profile, fd: fd})
	}
	return m, nil
}

func parityByte(s string) byte {
	if len(s) == 0 {
		return 'N'
	}
	return s[0]
}

// Run — 모든 채널 폴링 시작
func (m *Manager) Run(ctx context.Context) {
	var wg sync.WaitGroup
	for _, ch := range m.channels {
		wg.Add(1)
		go func(c *channelRunner) {
			defer wg.Done()
			if m.sim == nil {
				defer hal.RS485Close(c.fd)
			}
			m.runChannel(ctx, c)
		}(ch)
	}
	wg.Wait()
}

func (m *Manager) runChannel(ctx context.Context, c *channelRunner) {
	interval := time.Duration(c.cfg.PollingIntervalSec) * time.Second
	if interval == 0 {
		interval = 10 * time.Second
	}
	tick := time.NewTicker(interval)
	defer tick.Stop()

	log.Printf("[sensor %s] polling every %v on %s slave=%d", c.cfg.ChannelID, interval, c.cfg.Interface, c.cfg.SlaveID)

	for {
		select {
		case <-ctx.Done():
			return
		case <-tick.C:
			m.pollOnce(ctx, c)
		}
	}
}

func (m *Manager) pollOnce(ctx context.Context, c *channelRunner) {
	values := []map[string]any{}
	allOK := true
	now := time.Now()

	for _, meas := range c.profile.Measurements {
		var val float64

		if m.sim != nil {
			// SIMULATION: HAL 우회 + 합성값. scale/offset은 무시 (sim.Value가 이미 최종값).
			val = m.sim.Value(c.cfg.ChannelID, meas.Key, now)
		} else {
			var raw []uint16
			var lastErr error
			// retry 3회 (CRC fail / transient timeout)
			for attempt := 0; attempt < 3; attempt++ {
				r, err := hal.ModbusRead(c.fd, byte(c.cfg.SlaveID), byte(meas.Modbus.FunctionCode),
					uint16(meas.Modbus.Register), uint16(meas.Modbus.Length), 200)
				if err == nil {
					raw = r
					lastErr = nil
					break
				}
				lastErr = err
				if err == hal.ErrTimeout {
					break // timeout은 retry 의미 적음
				}
				time.Sleep(50 * time.Millisecond)
			}

			if lastErr != nil {
				allOK = false
				log.Printf("[sensor %s] %s read failed: %v", c.cfg.ChannelID, meas.Key, lastErr)
				continue
			}

			// 첫 번째 register만 사용 (Phase 0 단순화)
			// Phase 1+에서 length=2 (uint32, float32) 등 확장
			val = float64(int16(raw[0])) // signed 16-bit 가정
			val = val*meas.Scale + meas.Offset
		}

		quality := "good"
		if meas.Min != nil && val < *meas.Min {
			quality = "out_of_range"
		}
		if meas.Max != nil && val > *meas.Max {
			quality = "out_of_range"
		}

		values = append(values, map[string]any{
			"sensor_channel_id": c.cfg.ChannelID,
			"measurement_key":   meas.Key,
			"value":             val,
			"unit":              meas.Unit,
			"quality":           quality,
		})
	}

	_ = m.db.SetSensorHealth(c.cfg.ChannelID, allOK)

	if len(values) == 0 {
		return
	}

	payload := map[string]any{
		"message_id": uuid.NewString(),
		"gateway_id": m.gatewayID,
		"timestamp":  time.Now().UTC().Format(time.RFC3339Nano),
		"values":     values,
	}
	bs, _ := json.Marshal(payload)
	topic := fmt.Sprintf("gw/%s/telemetry", m.gatewayID)

	if err := m.mq.Publish(topic, bs); err != nil {
		// 오프라인 → 큐 적재
		_ = m.db.Enqueue(localdb.QueuedMessage{
			Topic:    topic,
			Payload:  bs,
			Priority: 3,
		})
	}
}
