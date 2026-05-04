// gateway-agent — IoT Gateway main entry
//
// 부팅 흐름 (14 단계, design doc 참조):
//   01. config 로드
//   02. HAL 초기화
//   03. Watchdog 오픈 (kernel + systemd)
//   04. Local DB 초기화
//   05. MQTT 연결
//   06. systemd READY (sd_notify) → local-ready
//   07. Sensor channels 초기화
//   08. Actuator channels 초기화
//   09. Sensor polling 루프 시작
//   10. Actuator command subscribe 시작
//   11. Health/heartbeat 시작
//   12. cloud-ready 신호 (MQTT CONNACK 수신 후)
//   13. signal 대기 (SIGTERM/SIGINT)
//   14. shutdown — assert_safe_state + cleanup
//
// IRON RULE: panic 시 defer로 hal.AssertSafeState 호출 보장.

package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/coreos/go-systemd/v22/daemon"

	"github.com/iot-gateway/agent/internal/actuator"
	"github.com/iot-gateway/agent/internal/config"
	"github.com/iot-gateway/agent/internal/hal"
	"github.com/iot-gateway/agent/internal/health"
	"github.com/iot-gateway/agent/internal/localdb"
	mqttpkg "github.com/iot-gateway/agent/internal/mqtt"
	"github.com/iot-gateway/agent/internal/sensor"
)

func main() {
	configPath := flag.String("config", "/etc/iot-gateway/config.yaml", "Path to YAML config")
	versionFlag := flag.Bool("version", false, "Print version and exit")
	flag.Parse()

	log.SetFlags(log.LstdFlags | log.Lmicroseconds)
	log.SetPrefix("[gateway-agent] ")

	if *versionFlag {
		fmt.Println("iot-gateway-agent 0.1.0-pi4-phase0")
		os.Exit(0)
	}

	if err := run(*configPath); err != nil {
		log.Printf("FATAL: %v", err)
		_, _ = daemon.SdNotify(false, "STATUS=fatal: "+err.Error())
		os.Exit(1)
	}
}

func run(configPath string) error {
	// 01. config 로드
	cfg, err := config.Load(configPath)
	if err != nil {
		return fmt.Errorf("config: %w", err)
	}
	log.Printf("loaded config: gateway=%s, sensors=%d, actuators=%d, simulation=%v",
		cfg.Gateway.ID, len(cfg.Sensors), len(cfg.Actuators), cfg.Simulation.Enabled)

	// 02. HAL 초기화. simulation 빌드 (-tags simulation)이면 noop, 일반 빌드는 cgo init.
	if err := hal.Init(); err != nil {
		return fmt.Errorf("hal init: %w", err)
	}
	if cfg.Simulation.Enabled {
		log.Printf("=== SIMULATION MODE === (HAL noop, sensor synthetic data, actuator log-only)")
	}
	// IRON RULE: panic/return 시 safe state 강제.
	// defer는 LIFO이므로 등록 순서가 중요:
	//   1) cleanup (먼저 등록 → 나중에 실행)
	//   2) safe-state assert (중간)
	//   3) recover (마지막에 등록 → 가장 먼저 실행하여 panic 잡기)
	// recover가 먼저 실행되어야 후속 defer들이 정상 진행됨.
	defer func() {
		if err := hal.Cleanup(); err != nil {
			log.Printf("hal cleanup: %v", err)
		}
	}()
	defer hal.AssertSafeState()
	defer func() {
		if r := recover(); r != nil {
			log.Printf("PANIC recovered: %v — asserting safe state", r)
			hal.AssertSafeState()
			panic(r) // re-panic so systemd sees abort (후속 defer들은 정상 실행)
		}
	}()

	v, err := hal.Version()
	if err == nil {
		log.Printf("HAL: %s", v)
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// 03. Watchdog (optional)
	var wdtFd int = -1
	if cfg.Watchdog.KernelWDTEnabled {
		wdtFd, err = hal.WatchdogOpen(cfg.Watchdog.KernelWDTTimeoutSec)
		if err != nil {
			log.Printf("WARN: kernel watchdog disabled: %v", err)
		} else {
			defer hal.WatchdogClose(wdtFd)
			go kernelWDTLoop(ctx, wdtFd, cfg.Watchdog.KernelWDTKickSec)
		}
	}

	// 04. Local DB
	db, err := localdb.Open(cfg.Storage.DBPath, cfg.Storage.RetentionDays, cfg.Storage.MaxQueueRows)
	if err != nil {
		return fmt.Errorf("localdb: %w", err)
	}
	defer db.Close()

	// 05. MQTT
	mqClient, err := mqttpkg.New(mqttpkg.Options{
		Broker:         cfg.MQTT.Broker,
		Username:       cfg.MQTT.Username,
		Password:       cfg.MQTT.Password,
		ClientID:       cfg.MQTT.ClientID,
		KeepaliveSec:   cfg.MQTT.KeepaliveSec,
		ConnectTimeout: time.Duration(cfg.MQTT.ConnectTimeoutSec) * time.Second,
		QoS:            cfg.MQTT.QoS,
		CleanSession:   cfg.MQTT.CleanSession,
		GatewayID:      cfg.Gateway.ID,
	})
	if err != nil {
		return fmt.Errorf("mqtt new: %w", err)
	}

	// MQTT 연결 시도 (실패해도 local-ready는 통과 — backlog로 동작)
	mqErr := mqClient.Connect(ctx)
	if mqErr != nil {
		log.Printf("WARN: MQTT initial connect failed (will retry in background): %v", mqErr)
	}
	defer mqClient.Disconnect()

	// 06. systemd READY → local-ready
	if sent, err := daemon.SdNotify(false, daemon.SdNotifyReady); err != nil {
		log.Printf("sd_notify READY error: %v", err)
	} else if sent {
		log.Printf("sd_notify READY sent (local-ready)")
	}

	// 07-08. Sensor + Actuator channels 초기화 (simulation 플래그 전달)
	sensorMgr, err := sensor.NewManager(cfg.Sensors, mqClient, db, cfg.Gateway.ID, cfg.Simulation)
	if err != nil {
		return fmt.Errorf("sensor manager: %w", err)
	}
	actuatorMgr, err := actuator.NewManager(cfg.Actuators, mqClient, cfg.Gateway.ID, cfg.Simulation.Enabled)
	if err != nil {
		return fmt.Errorf("actuator manager: %w", err)
	}

	// 09. Sensor polling
	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		sensorMgr.Run(ctx)
	}()

	// 10. Actuator subscribe
	wg.Add(1)
	go func() {
		defer wg.Done()
		actuatorMgr.Run(ctx)
	}()

	// 11. Health / heartbeat
	healthAgent := health.New(mqClient, cfg.Gateway.ID, time.Duration(cfg.Gateway.HeartbeatSec)*time.Second)
	wg.Add(1)
	go func() {
		defer wg.Done()
		healthAgent.Run(ctx)
	}()

	// systemd watchdog kick (sd_notify WATCHDOG=1)
	wg.Add(1)
	go func() {
		defer wg.Done()
		sdWatchdogLoop(ctx, time.Duration(cfg.Watchdog.SDNotifyIntervalSec)*time.Second)
	}()

	// 13. signal 대기
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGTERM, syscall.SIGINT)
	sig := <-sigCh
	log.Printf("received signal %v, initiating shutdown", sig)
	_, _ = daemon.SdNotify(false, daemon.SdNotifyStopping)

	cancel()
	wg.Wait()
	log.Printf("shutdown complete")
	return nil
}

func kernelWDTLoop(ctx context.Context, fd int, kickSec int) {
	if kickSec < 1 {
		kickSec = 5
	}
	tick := time.NewTicker(time.Duration(kickSec) * time.Second)
	defer tick.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-tick.C:
			if err := hal.WatchdogKick(fd); err != nil {
				log.Printf("kernel WDT kick error: %v", err)
			}
		}
	}
}

func sdWatchdogLoop(ctx context.Context, interval time.Duration) {
	if interval < time.Second {
		interval = 10 * time.Second
	}
	tick := time.NewTicker(interval)
	defer tick.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-tick.C:
			_, _ = daemon.SdNotify(false, daemon.SdNotifyWatchdog)
		}
	}
}
