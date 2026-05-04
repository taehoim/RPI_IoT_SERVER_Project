// Package health — heartbeat + system metric publish
//
// 주기 publish gw/{id}/heartbeat (timestamp + uptime + cpu/mem/disk)
// + 첫 connect 시 gw/{id}/state with online payload (LWT 덮음)
package health

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"runtime"
	"strings"
	"syscall"
	"time"

	mqttpkg "github.com/iot-gateway/agent/internal/mqtt"
)

// Agent — health 모듈
type Agent struct {
	mq        *mqttpkg.Client
	gatewayID string
	interval  time.Duration
	startTime time.Time
}

// New — health agent
func New(mq *mqttpkg.Client, gatewayID string, interval time.Duration) *Agent {
	if interval == 0 {
		interval = 30 * time.Second
	}
	return &Agent{
		mq:        mq,
		gatewayID: gatewayID,
		interval:  interval,
		startTime: time.Now(),
	}
}

// Run — heartbeat 루프
func (a *Agent) Run(ctx context.Context) {
	// MQTT 첫 connect 시 online state publish (LWT 덮음)
	a.mq.OnConnect = func() {
		_ = a.mq.PublishOnline(map[string]any{
			"app_version": "0.1.0-pi4-phase0",
			"uptime_sec":  int(time.Since(a.startTime).Seconds()),
		})
	}

	tick := time.NewTicker(a.interval)
	defer tick.Stop()

	a.publish() // 첫 publish 즉시
	for {
		select {
		case <-ctx.Done():
			// graceful: offline 알림
			offline, _ := json.Marshal(map[string]any{
				"gateway_id": a.gatewayID,
				"status":     "shutdown",
				"timestamp":  time.Now().UTC().Format(time.RFC3339),
			})
			_ = a.mq.PublishRetained(fmt.Sprintf("gw/%s/state", a.gatewayID), offline)
			return
		case <-tick.C:
			a.publish()
		}
	}
}

func (a *Agent) publish() {
	hostname, _ := os.Hostname()
	uptimeSec := int(time.Since(a.startTime).Seconds())

	var ms runtime.MemStats
	runtime.ReadMemStats(&ms)

	diskPct := -1.0
	var stat syscall.Statfs_t
	if err := syscall.Statfs("/", &stat); err == nil {
		total := stat.Blocks * uint64(stat.Bsize)
		avail := stat.Bavail * uint64(stat.Bsize)
		if total > 0 {
			diskPct = float64(total-avail) / float64(total) * 100.0
		}
	}

	cpuTemp := readCPUTemp()

	hb := map[string]any{
		"gateway_id":             a.gatewayID,
		"timestamp":              time.Now().UTC().Format(time.RFC3339Nano),
		"hostname":               hostname,
		"uptime_sec":             uptimeSec,
		"go_alloc_mb":            float64(ms.Alloc) / 1024 / 1024,
		"go_sys_mb":              float64(ms.Sys) / 1024 / 1024,
		"goroutines":             runtime.NumGoroutine(),
		"disk_root_used_percent": diskPct,
		"cpu_temp_celsius":       cpuTemp,
	}
	bs, _ := json.Marshal(hb)
	topic := fmt.Sprintf("gw/%s/heartbeat", a.gatewayID)
	if err := a.mq.Publish(topic, bs); err != nil {
		log.Printf("[health] heartbeat publish failed (will retry next tick): %v", err)
	}
}

// readCPUTemp — Pi 4 thermal zone 0
func readCPUTemp() float64 {
	data, err := os.ReadFile("/sys/class/thermal/thermal_zone0/temp")
	if err != nil {
		return -1
	}
	s := strings.TrimSpace(string(data))
	var n int
	if _, err := fmt.Sscanf(s, "%d", &n); err != nil {
		return -1
	}
	return float64(n) / 1000.0
}
