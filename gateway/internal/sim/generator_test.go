package sim

import (
	"math"
	"testing"
	"time"
)

func TestSinePatternStaysInRange(t *testing.T) {
	g := New("sine", 0, 42)
	now := time.Now()
	for i := 0; i < 100; i++ {
		v := g.Value("ch1", "temperature", now.Add(time.Duration(i)*time.Hour))
		if v < 5 || v > 40 {
			t.Errorf("temperature out of range at i=%d: %v", i, v)
		}
	}
}

func TestRandomWalkDeterministic(t *testing.T) {
	g1 := New("random_walk", 0, 12345)
	g2 := New("random_walk", 0, 12345)
	now := time.Now()
	for i := 0; i < 20; i++ {
		v1 := g1.Value("ch1", "co2", now)
		v2 := g2.Value("ch1", "co2", now)
		if math.Abs(v1-v2) > 1e-9 {
			t.Errorf("seed=12345 should be deterministic; iter=%d v1=%v v2=%v", i, v1, v2)
		}
	}
}

func TestUnknownKeyUsesDefaultProfile(t *testing.T) {
	g := New("fixed", 0, 1)
	v := g.Value("ch1", "unknown_measurement", time.Now())
	if v != 50.0 {
		t.Errorf("unknown key should use default base 50.0, got %v", v)
	}
}

func TestJitterStaysWithinClamp(t *testing.T) {
	g := New("fixed", 5.0, 99) // 5% jitter
	for i := 0; i < 100; i++ {
		v := g.Value("ch1", "co2", time.Now())
		if v < 400 || v > 5000 {
			t.Errorf("co2 jitter exceeded clamp: %v", v)
		}
	}
}

func TestWalkRespectsMinMax(t *testing.T) {
	g := New("random_walk", 0, 7)
	now := time.Now()
	for i := 0; i < 1000; i++ {
		v := g.Value("ch1", "humidity", now)
		if v < 20 || v > 95 {
			t.Errorf("humidity walk escaped clamp at i=%d: %v", i, v)
		}
	}
}
