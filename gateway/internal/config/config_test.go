package config

import (
	"os"
	"path/filepath"
	"testing"
)

const validYAML = `
gateway:
  id: GW-TEST01
  name: Test Gateway
  heartbeat_sec: 30
mqtt:
  broker: tcp://127.0.0.1:1883
  client_id: test
  qos: 1
storage:
  db_path: /tmp/test.db
sensors:
  - channel_id: sensor-01
    display_name: NH3 sensor
    profile_file: shared/examples/nh3_rs485.json
    interface: /dev/ttyUSB0
    baud: 9600
    parity: "N"
    data_bits: 8
    stop_bits: 1
    slave_id: 1
    polling_interval_sec: 10
    enabled: true
actuators:
  - channel_id: relay-01
    display_name: Sterilizer
    type: relay
    gpio_pin: 17
    default_state: "off"
    max_on_duration_sec: 300
    enabled: true
`

func writeTemp(t *testing.T, content string) string {
	t.Helper()
	dir := t.TempDir()
	p := filepath.Join(dir, "config.yaml")
	if err := os.WriteFile(p, []byte(content), 0644); err != nil {
		t.Fatal(err)
	}
	return p
}

func TestLoadValid(t *testing.T) {
	cfg, err := Load(writeTemp(t, validYAML))
	if err != nil {
		t.Fatalf("expected ok, got %v", err)
	}
	if cfg.Gateway.ID != "GW-TEST01" {
		t.Errorf("gateway.id = %q", cfg.Gateway.ID)
	}
	if len(cfg.Sensors) != 1 || len(cfg.Actuators) != 1 {
		t.Errorf("sensor/actuator counts wrong: %d/%d", len(cfg.Sensors), len(cfg.Actuators))
	}
	if cfg.Watchdog.KernelWDTTimeoutSec != 15 {
		t.Errorf("default WDT timeout not applied: %d", cfg.Watchdog.KernelWDTTimeoutSec)
	}
}

func TestRejectMissingGatewayID(t *testing.T) {
	bad := `mqtt: {broker: tcp://x:1883}` + "\n" +
		`storage: {db_path: /tmp/x.db}`
	_, err := Load(writeTemp(t, bad))
	if err == nil {
		t.Fatal("expected error for missing gateway.id")
	}
}

func TestRejectDuplicateChannelID(t *testing.T) {
	dup := `
gateway:
  id: GW1
mqtt:
  broker: tcp://x:1883
storage:
  db_path: /tmp/x.db
sensors:
  - channel_id: dup
    profile_file: x.json
    interface: /dev/ttyUSB0
    slave_id: 1
actuators:
  - channel_id: dup
    type: relay
    gpio_pin: 17
`
	_, err := Load(writeTemp(t, dup))
	if err == nil {
		t.Fatal("expected duplicate channel_id error")
	}
}

func TestRejectInvalidGPIOPin(t *testing.T) {
	bad := `
gateway:
  id: GW1
mqtt:
  broker: tcp://x:1883
storage:
  db_path: /tmp/x.db
actuators:
  - channel_id: r
    type: relay
    gpio_pin: 99
`
	_, err := Load(writeTemp(t, bad))
	if err == nil {
		t.Fatal("expected invalid gpio_pin error")
	}
}

func TestRejectBadSlaveID(t *testing.T) {
	bad := `
gateway:
  id: GW1
mqtt:
  broker: tcp://x:1883
storage:
  db_path: /tmp/x.db
sensors:
  - channel_id: s
    profile_file: p.json
    interface: /dev/ttyUSB0
    slave_id: 0
`
	_, err := Load(writeTemp(t, bad))
	if err == nil {
		t.Fatal("expected slave_id range error")
	}
}

func TestRejectGatewayIDWithMQTTWildcards(t *testing.T) {
	cases := []string{"gw+1", "gw#1", "gw/1", "gw 1", "gw!1"}
	for _, badID := range cases {
		yaml := `
gateway:
  id: "` + badID + `"
mqtt:
  broker: tcp://x:1883
storage:
  db_path: /tmp/x.db
`
		if _, err := Load(writeTemp(t, yaml)); err == nil {
			t.Errorf("expected gateway.id %q to be rejected (MQTT topic injection)", badID)
		}
	}
}
