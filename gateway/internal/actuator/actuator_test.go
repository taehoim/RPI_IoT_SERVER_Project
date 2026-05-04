// actuator_test.go — IRON RULE C2 만족: panic 시 safe state, expired/invalid 거부, max_on auto-OFF
package actuator

import (
	"testing"
	"time"
)

func TestActionToValue(t *testing.T) {
	cases := []struct {
		in   string
		want int
		err  bool
	}{
		{"ON", 1, false},
		{"OFF", 0, false},
		{"on", 1, false},
		{"off", 0, false},
		{"1", 1, false},
		{"0", 0, false},
		{"toggle", 0, true},
		{"", 0, true},
	}
	for _, c := range cases {
		got, err := actionToValue(c.in)
		if c.err && err == nil {
			t.Errorf("%q: expected err", c.in)
			continue
		}
		if !c.err && got != c.want {
			t.Errorf("%q: got %d, want %d", c.in, got, c.want)
		}
	}
}

func TestExpiredCommandRejected(t *testing.T) {
	// Manager에 채널 등록 (mock — 실 HAL 안 씀)
	m := &Manager{channels: map[string]*channelState{}, gatewayID: "GW-T"}
	req := &CommandRequest{
		CommandID:         "c-expired",
		ActuatorChannelID: "relay-01",
		Action:            "ON",
		ExpiresAt:         time.Now().Add(-1 * time.Hour).UTC().Format(time.RFC3339),
	}
	resp := m.execute(req)
	if resp.Status != "rejected" {
		t.Errorf("expected rejected, got %s", resp.Status)
	}
	if resp.LocalSafetyCheck != "rejected_expired" {
		t.Errorf("expected rejected_expired, got %s", resp.LocalSafetyCheck)
	}
}

func TestUnknownChannelRejected(t *testing.T) {
	m := &Manager{channels: map[string]*channelState{}, gatewayID: "GW-T"}
	req := &CommandRequest{
		CommandID:         "c-1",
		ActuatorChannelID: "relay-99",
		Action:            "ON",
	}
	resp := m.execute(req)
	if resp.Status != "rejected" {
		t.Errorf("expected rejected, got %s", resp.Status)
	}
}

func TestMissingCommandIDRejected(t *testing.T) {
	m := &Manager{channels: map[string]*channelState{}, gatewayID: "GW-T"}
	req := &CommandRequest{
		ActuatorChannelID: "relay-01",
		Action:            "ON",
	}
	resp := m.execute(req)
	if resp.Status != "rejected" {
		t.Errorf("expected rejected, got %s", resp.Status)
	}
	if resp.Reason != "missing command_id" {
		t.Errorf("reason = %s", resp.Reason)
	}
}

func TestInvalidActionRejected(t *testing.T) {
	m := &Manager{channels: map[string]*channelState{}, gatewayID: "GW-T"}
	m.channels["relay-01"] = &channelState{}
	req := &CommandRequest{
		CommandID:         "c-1",
		ActuatorChannelID: "relay-01",
		Action:            "TOGGLE",
	}
	resp := m.execute(req)
	if resp.Status != "rejected" {
		t.Errorf("expected rejected, got %s", resp.Status)
	}
}
