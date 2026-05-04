// Package actuator — 원격 제어 명령 처리
//
// 책임:
//   - MQTT subscribe gw/{id}/command/request
//   - 안전 검사 (idempotency, expires_at, channel exist, max_on_duration)
//   - HAL GPIOSet 호출 → relay/valve 제어
//   - max_on_duration_sec 타이머로 자동 OFF
//   - response publish gw/{id}/command/response
//
// IRON RULE C2: panic 시 모든 액추에이터를 NC 안전 상태로 강제
package actuator

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/iot-gateway/agent/internal/config"
	"github.com/iot-gateway/agent/internal/hal"
	mqttpkg "github.com/iot-gateway/agent/internal/mqtt"
)

// Manager — 모든 actuator channel 관리
type Manager struct {
	channels   map[string]*channelState
	mq         *mqttpkg.Client
	gatewayID  string
	simulation bool // true면 GPIO 호출 우회 + 로그만
	mu         sync.Mutex
}

type channelState struct {
	cfg          config.ActuatorChannel
	currentValue int
	maxOnTimer   *time.Timer
}

// NewManager — config 로드 + GPIO reserve. simulation=true면 GPIO 우회.
func NewManager(channels []config.ActuatorChannel, mq *mqttpkg.Client, gatewayID string, simulation bool) (*Manager, error) {
	m := &Manager{
		channels:   make(map[string]*channelState),
		mq:         mq,
		gatewayID:  gatewayID,
		simulation: simulation,
	}
	if simulation {
		log.Printf("[actuator] SIMULATION mode (GPIO 호출 우회, 로그만 발행)")
	}
	for _, ch := range channels {
		if !ch.Enabled {
			continue
		}
		initial := 0
		if ch.DefaultState == "on" {
			initial = 1
		}
		if !simulation {
			if err := hal.RequestOutput(ch.GPIOPin, initial); err != nil {
				return nil, fmt.Errorf("actuator %s gpio %d: %w", ch.ChannelID, ch.GPIOPin, err)
			}
		}
		m.channels[ch.ChannelID] = &channelState{
			cfg:          ch,
			currentValue: initial,
		}
		log.Printf("[actuator %s] reserved gpio=%d initial=%s sim=%v", ch.ChannelID, ch.GPIOPin, ch.DefaultState, simulation)
	}
	return m, nil
}

// Run — subscribe 시작 후 ctx done 까지 block
func (m *Manager) Run(ctx context.Context) {
	defer func() {
		// IRON RULE C2: shutdown 시 모든 액추에이터 OFF
		m.assertAllOff()
		if r := recover(); r != nil {
			log.Printf("[actuator] PANIC: %v — assert safe state", r)
			hal.AssertSafeState()
			panic(r)
		}
	}()

	topic := fmt.Sprintf("gw/%s/command/request", m.gatewayID)
	if err := m.mq.Subscribe(topic, m.handleCommand); err != nil {
		log.Printf("[actuator] subscribe failed: %v (will retry on reconnect via paho)", err)
	}
	log.Printf("[actuator] subscribed to %s", topic)

	<-ctx.Done()
}

// CommandRequest — 수신 메시지 형식
type CommandRequest struct {
	CommandID         string `json:"command_id"`
	GatewayID         string `json:"gateway_id"`
	TargetType        string `json:"target_type"` // "actuator"
	ActuatorChannelID string `json:"actuator_channel_id"`
	Action            string `json:"action"` // "ON" | "OFF"
	IssuedBy          string `json:"issued_by"`
	IssuedAt          string `json:"issued_at"`
	ExpiresAt         string `json:"expires_at"`
	TimeoutMs         int    `json:"timeout_ms"`
	RequireAck        bool   `json:"require_ack"`
	Reason            string `json:"reason"`
}

// CommandResponse — 발신 메시지 형식
type CommandResponse struct {
	CommandID        string `json:"command_id"`
	GatewayID        string `json:"gateway_id"`
	Status           string `json:"status"` // "executed" | "rejected" | "failed"
	Reason           string `json:"reason"`
	Result           string `json:"result"`
	ExecutedAt       string `json:"executed_at"`
	LocalSafetyCheck string `json:"local_safety_check"`
}

func (m *Manager) handleCommand(_ string, payload []byte) {
	defer func() {
		if r := recover(); r != nil {
			log.Printf("[actuator] handler panic: %v — assert safe", r)
			hal.AssertSafeState()
		}
	}()

	var req CommandRequest
	if err := json.Unmarshal(payload, &req); err != nil {
		log.Printf("[actuator] invalid command JSON: %v", err)
		return
	}

	resp := m.execute(&req)
	if req.RequireAck {
		bs, _ := json.Marshal(resp)
		topic := fmt.Sprintf("gw/%s/command/response", m.gatewayID)
		if err := m.mq.Publish(topic, bs); err != nil {
			log.Printf("[actuator] response publish failed: %v", err)
		}
	}
}

func (m *Manager) execute(req *CommandRequest) *CommandResponse {
	now := time.Now().UTC()
	resp := &CommandResponse{
		CommandID:        req.CommandID,
		GatewayID:        m.gatewayID,
		ExecutedAt:       now.Format(time.RFC3339Nano),
		LocalSafetyCheck: "passed",
	}

	if req.CommandID == "" {
		resp.Status = "rejected"
		resp.Reason = "missing command_id"
		return resp
	}

	// gateway_id 일치 확인 — broker ACL 미설정/오발행 시 다른 gateway 명령 실행 차단
	if req.GatewayID != "" && req.GatewayID != m.gatewayID {
		resp.Status = "rejected"
		resp.Reason = "wrong gateway: " + req.GatewayID
		resp.LocalSafetyCheck = "rejected_wrong_gateway"
		return resp
	}

	// expires_at 검사. Python isoformat()은 6자리 microsecond를 포함하므로
	// RFC3339Nano를 먼저 시도하고 RFC3339로 fallback. 파싱 실패 시 expired로 reject
	// (silently skip하면 만료된 명령도 실행됨).
	if req.ExpiresAt != "" {
		t, err := time.Parse(time.RFC3339Nano, req.ExpiresAt)
		if err != nil {
			t, err = time.Parse(time.RFC3339, req.ExpiresAt)
		}
		if err != nil {
			resp.Status = "rejected"
			resp.Reason = "invalid expires_at: " + req.ExpiresAt
			resp.LocalSafetyCheck = "rejected_invalid_expires"
			return resp
		}
		if now.After(t) {
			resp.Status = "rejected"
			resp.Reason = "expired"
			resp.LocalSafetyCheck = "rejected_expired"
			return resp
		}
	}

	m.mu.Lock()
	state, ok := m.channels[req.ActuatorChannelID]
	m.mu.Unlock()
	if !ok {
		resp.Status = "rejected"
		resp.Reason = "unknown channel: " + req.ActuatorChannelID
		return resp
	}

	value, err := actionToValue(req.Action)
	if err != nil {
		resp.Status = "rejected"
		resp.Reason = err.Error()
		return resp
	}

	if !m.simulation {
		if err := hal.GPIOSet(state.cfg.GPIOPin, value); err != nil {
			resp.Status = "failed"
			resp.Reason = "hal: " + err.Error()
			return resp
		}
	} else {
		log.Printf("[actuator %s] SIM: would GPIOSet(pin=%d, value=%d)", state.cfg.ChannelID, state.cfg.GPIOPin, value)
	}

	m.mu.Lock()
	state.currentValue = value
	// 기존 max_on timer 취소
	if state.maxOnTimer != nil {
		state.maxOnTimer.Stop()
		state.maxOnTimer = nil
	}
	// ON 명령이면 max_on_duration_sec 타이머 설정
	if value == 1 && state.cfg.MaxOnDurationSec > 0 {
		dur := time.Duration(state.cfg.MaxOnDurationSec) * time.Second
		state.maxOnTimer = time.AfterFunc(dur, func() {
			if !m.simulation {
				if err := hal.GPIOSet(state.cfg.GPIOPin, 0); err != nil {
					log.Printf("[actuator %s] max_on auto-OFF failed: %v", state.cfg.ChannelID, err)
					return
				}
			} else {
				log.Printf("[actuator %s] SIM: would GPIOSet(pin=%d, value=0) [max_on auto-OFF]", state.cfg.ChannelID, state.cfg.GPIOPin)
			}
			m.mu.Lock()
			state.currentValue = 0
			m.mu.Unlock()
			log.Printf("[actuator %s] max_on_duration %v expired, forced OFF", state.cfg.ChannelID, dur)
			m.publishEvent(map[string]any{
				"event":               "max_on_auto_off",
				"actuator_channel_id": state.cfg.ChannelID,
				"timestamp":           time.Now().UTC().Format(time.RFC3339Nano),
			})
		})
	}
	m.mu.Unlock()

	resp.Status = "executed"
	resp.Result = fmt.Sprintf("%s-%s", req.ActuatorChannelID, req.Action)
	return resp
}

func (m *Manager) publishEvent(payload map[string]any) {
	bs, _ := json.Marshal(payload)
	topic := fmt.Sprintf("gw/%s/event", m.gatewayID)
	_ = m.mq.Publish(topic, bs) // best-effort, 실패해도 무시
}

func (m *Manager) assertAllOff() {
	m.mu.Lock()
	defer m.mu.Unlock()
	for _, st := range m.channels {
		if st.maxOnTimer != nil {
			st.maxOnTimer.Stop()
		}
		if !m.simulation {
			_ = hal.GPIOSet(st.cfg.GPIOPin, 0)
		}
		st.currentValue = 0
	}
}

func actionToValue(action string) (int, error) {
	switch action {
	case "ON", "on", "1", "true":
		return 1, nil
	case "OFF", "off", "0", "false":
		return 0, nil
	}
	return 0, fmt.Errorf("invalid action: %s", action)
}
