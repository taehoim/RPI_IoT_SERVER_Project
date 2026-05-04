// Package mqtt — paho.mqtt.golang wrapper
//
// 책임:
//   - autoreconnect (paho 내장)
//   - LWT (Last Will & Testament): gw/{id}/state with offline payload
//   - QoS 1 (atleast-once)
//   - clean_session=false (subscribe 미수신 메시지 자동 복구)
//   - Publish/Subscribe helper + offline 시 caller가 큐 적재 결정
//
// Topic 패턴 (gw/{id}/...):
//
//	publish:    telemetry, state, heartbeat, event, command/response, config/reported
//	subscribe:  command/request, config/desired
package mqtt

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sync/atomic"
	"time"

	paho "github.com/eclipse/paho.mqtt.golang"
)

// Options — 연결 설정
type Options struct {
	Broker         string
	Username       string
	Password       string
	ClientID       string
	KeepaliveSec   int
	ConnectTimeout time.Duration
	QoS            byte
	CleanSession   bool
	GatewayID      string
}

// Client — MQTT 클라이언트
type Client struct {
	c           paho.Client
	gatewayID   string
	qos         byte
	connected   atomic.Bool
	OnConnect   func()
	OnReconnect func()
}

// New — 클라이언트 생성 (Connect는 별도)
func New(opts Options) (*Client, error) {
	if opts.Broker == "" || opts.GatewayID == "" {
		return nil, fmt.Errorf("broker and gateway_id required")
	}
	if opts.QoS == 0 {
		opts.QoS = 1
	}
	if opts.KeepaliveSec == 0 {
		opts.KeepaliveSec = 30
	}
	if opts.ConnectTimeout == 0 {
		opts.ConnectTimeout = 10 * time.Second
	}

	cl := &Client{
		gatewayID: opts.GatewayID,
		qos:       opts.QoS,
	}

	pahoOpts := paho.NewClientOptions().
		AddBroker(opts.Broker).
		SetClientID(opts.ClientID).
		SetKeepAlive(time.Duration(opts.KeepaliveSec) * time.Second).
		SetConnectTimeout(opts.ConnectTimeout).
		SetAutoReconnect(true).
		SetMaxReconnectInterval(60 * time.Second).
		SetCleanSession(opts.CleanSession).
		SetOrderMatters(false)

	if opts.Username != "" {
		pahoOpts.SetUsername(opts.Username).SetPassword(opts.Password)
	}

	// LWT: 비정상 종료 시 broker가 자동 발행.
	// timestamp는 의도적으로 제외 — payload는 New() 호출 시점에 고정되므로
	// 7일 후 abort 시 7일 전 시각이 발행되는 misleading record를 만든다.
	// Server (state.py)는 reason="lwt"이면 server-side 현재시각을 stamp한다.
	lwtTopic := fmt.Sprintf("gw/%s/state", opts.GatewayID)
	lwtPayload, _ := json.Marshal(map[string]any{
		"gateway_id": opts.GatewayID,
		"status":     "offline",
		"reason":     "lwt",
	})
	pahoOpts.SetWill(lwtTopic, string(lwtPayload), opts.QoS, true)

	pahoOpts.OnConnect = func(c paho.Client) {
		cl.connected.Store(true)
		log.Printf("[mqtt] connected to %s", opts.Broker)
		if cl.OnConnect != nil {
			cl.OnConnect()
		}
	}
	pahoOpts.OnConnectionLost = func(c paho.Client, err error) {
		cl.connected.Store(false)
		log.Printf("[mqtt] connection lost: %v", err)
	}
	pahoOpts.OnReconnecting = func(c paho.Client, _ *paho.ClientOptions) {
		log.Printf("[mqtt] reconnecting...")
		if cl.OnReconnect != nil {
			cl.OnReconnect()
		}
	}

	cl.c = paho.NewClient(pahoOpts)
	return cl, nil
}

// Connect — 연결 시도. 실패해도 autoreconnect로 백그라운드 재시도.
func (cl *Client) Connect(ctx context.Context) error {
	tok := cl.c.Connect()
	select {
	case <-tok.Done():
		return tok.Error()
	case <-ctx.Done():
		return ctx.Err()
	}
}

// Disconnect — graceful disconnect with online→offline state publish
func (cl *Client) Disconnect() {
	if cl.connected.Load() {
		offline, _ := json.Marshal(map[string]any{
			"gateway_id": cl.gatewayID,
			"status":     "offline",
			"timestamp":  time.Now().UTC().Format(time.RFC3339),
			"reason":     "graceful",
		})
		cl.PublishRetained(fmt.Sprintf("gw/%s/state", cl.gatewayID), offline)
		time.Sleep(200 * time.Millisecond) // best-effort
	}
	cl.c.Disconnect(500)
}

// IsConnected — 현재 연결 상태
func (cl *Client) IsConnected() bool {
	return cl.connected.Load() && cl.c.IsConnected()
}

// Publish — payload publish (QoS = options.QoS, retain=false)
// caller는 offline 시 직접 큐 적재 결정 (이 함수는 paho에 위임만).
func (cl *Client) Publish(topic string, payload []byte) error {
	if !cl.IsConnected() {
		return fmt.Errorf("mqtt not connected")
	}
	tok := cl.c.Publish(topic, cl.qos, false, payload)
	if !tok.WaitTimeout(5 * time.Second) {
		return fmt.Errorf("publish timeout")
	}
	return tok.Error()
}

// PublishRetained — retain=true (state, config/reported용)
func (cl *Client) PublishRetained(topic string, payload []byte) error {
	if !cl.IsConnected() {
		return fmt.Errorf("mqtt not connected")
	}
	tok := cl.c.Publish(topic, cl.qos, true, payload)
	if !tok.WaitTimeout(5 * time.Second) {
		return fmt.Errorf("publish timeout")
	}
	return tok.Error()
}

// Subscribe — handler 등록 (QoS 1)
func (cl *Client) Subscribe(topic string, handler func(topic string, payload []byte)) error {
	tok := cl.c.Subscribe(topic, cl.qos, func(c paho.Client, m paho.Message) {
		handler(m.Topic(), m.Payload())
	})
	if !tok.WaitTimeout(5 * time.Second) {
		return fmt.Errorf("subscribe timeout: %s", topic)
	}
	return tok.Error()
}

// PublishOnline — 연결 직후 호출하여 LWT를 덮음 (retained "online")
func (cl *Client) PublishOnline(extra map[string]any) error {
	payload := map[string]any{
		"gateway_id": cl.gatewayID,
		"status":     "online",
		"timestamp":  time.Now().UTC().Format(time.RFC3339),
	}
	for k, v := range extra {
		payload[k] = v
	}
	bs, _ := json.Marshal(payload)
	return cl.PublishRetained(fmt.Sprintf("gw/%s/state", cl.gatewayID), bs)
}
