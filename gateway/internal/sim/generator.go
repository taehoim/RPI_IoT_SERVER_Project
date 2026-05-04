// Package sim — 가상 센서 값 생성기.
//
// measurement_key별로 사람이 읽기에 자연스러운 시계열 합성 데이터 생성.
// 패턴: sine (주기적), random_walk (관성), fixed (상수 + jitter).
//
// Phase 0 시뮬레이션 모드에서 sensor.go가 HAL.ModbusRead 대신 호출.
// 비-Pi 환경 (WSL/x86 Ubuntu)에서 server worker → DB → API 흐름 검증용.
package sim

import (
	"math"
	"math/rand"
	"sync"
	"time"
)

// profile — measurement_key별 자연스러운 값 범위 + 주기.
// 양돈/축산 환경 기준 reference 값 (REVIEW 컨텍스트의 livestock 6-in-1 sensor와 일관).
type profile struct {
	base      float64       // 평균
	amplitude float64       // sine 진폭
	period    time.Duration // 주기 (sine)
	walkStep  float64       // random_walk 1-step 변동
	min, max  float64
}

var profiles = map[string]profile{
	// 환경 모니터링
	"temperature": {base: 22.0, amplitude: 4.0, period: 24 * time.Hour, walkStep: 0.2, min: 5, max: 40},
	"humidity":    {base: 60.0, amplitude: 15.0, period: 24 * time.Hour, walkStep: 1.0, min: 20, max: 95},
	"pm10":        {base: 25.0, amplitude: 15.0, period: 6 * time.Hour, walkStep: 2.0, min: 0, max: 200},
	"pm25":        {base: 12.0, amplitude: 8.0, period: 6 * time.Hour, walkStep: 1.5, min: 0, max: 150},
	"nh3":         {base: 4.0, amplitude: 2.5, period: 8 * time.Hour, walkStep: 0.3, min: 0, max: 25},
	"co2":         {base: 800.0, amplitude: 300.0, period: 4 * time.Hour, walkStep: 30.0, min: 400, max: 5000},
	// 추가 keys: gateway는 이외 key도 받지만 default profile fallback
}

var defaultProfile = profile{base: 50.0, amplitude: 10.0, period: 1 * time.Hour, walkStep: 1.0, min: 0, max: 100}

// Generator — 시뮬레이션 인스턴스. thread-safe.
type Generator struct {
	pattern       string
	jitterPercent float64
	rng           *rand.Rand
	mu            sync.Mutex
	walkState     map[string]float64 // (channel_id+key) → 마지막 값 (random_walk)
}

// New — Generator 생성. pattern: "sine" | "random_walk" | "fixed". seed=0이면 time-based.
func New(pattern string, jitterPercent float64, seed int64) *Generator {
	if seed == 0 {
		seed = time.Now().UnixNano()
	}
	if pattern == "" {
		pattern = "sine"
	}
	return &Generator{
		pattern:       pattern,
		jitterPercent: jitterPercent,
		rng:           rand.New(rand.NewSource(seed)),
		walkState:     make(map[string]float64),
	}
}

// Value — 단일 측정값 생성. channelID는 walk state 키, measurementKey는 profile 선택자.
//
// 반환값은 sensor.go가 raw → scale/offset 처리하기 전 단계의 "최종 측정값"으로 가정.
// 따라서 sensor.go 시뮬레이션 분기는 scale/offset을 곱하지 않고 그대로 사용.
func (g *Generator) Value(channelID, measurementKey string, t time.Time) float64 {
	prof, ok := profiles[measurementKey]
	if !ok {
		prof = defaultProfile
	}

	var v float64
	switch g.pattern {
	case "fixed":
		v = prof.base
	case "random_walk":
		v = g.walk(channelID+":"+measurementKey, prof)
	default: // "sine"
		v = g.sine(prof, t)
	}

	// jitter
	if g.jitterPercent > 0 {
		g.mu.Lock()
		noise := (g.rng.Float64()*2 - 1) * g.jitterPercent / 100.0 * prof.base
		g.mu.Unlock()
		v += noise
	}

	// 최종 클램프 — 센서가 물리적으로 절대 못 내는 값은 차단
	if v < prof.min {
		v = prof.min
	}
	if v > prof.max {
		v = prof.max
	}
	return v
}

func (g *Generator) sine(p profile, t time.Time) float64 {
	periodSec := p.period.Seconds()
	if periodSec <= 0 {
		return p.base
	}
	phase := 2.0 * math.Pi * float64(t.UnixNano()) / (periodSec * 1e9)
	return p.base + p.amplitude*math.Sin(phase)
}

func (g *Generator) walk(key string, p profile) float64 {
	g.mu.Lock()
	defer g.mu.Unlock()
	cur, seen := g.walkState[key]
	if !seen {
		cur = p.base
	}
	step := (g.rng.Float64()*2 - 1) * p.walkStep
	cur += step
	if cur < p.min {
		cur = p.min
	}
	if cur > p.max {
		cur = p.max
	}
	g.walkState[key] = cur
	return cur
}
