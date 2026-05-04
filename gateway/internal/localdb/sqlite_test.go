package localdb

import (
	"path/filepath"
	"testing"
	"time"
)

func openTestDB(t *testing.T, maxRows int) *DB {
	t.Helper()
	dir := t.TempDir()
	db, err := Open(filepath.Join(dir, "test.db"), 7, maxRows)
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	t.Cleanup(func() { db.Close() })
	return db
}

func TestEnqueueAndPeek(t *testing.T) {
	db := openTestDB(t, 100)
	for i := 0; i < 5; i++ {
		err := db.Enqueue(QueuedMessage{
			Topic:    "gw/x/telemetry",
			Payload:  []byte("test"),
			Priority: 3,
		})
		if err != nil {
			t.Fatal(err)
		}
	}
	n, _ := db.QueueLen()
	if n != 5 {
		t.Fatalf("queue len = %d, want 5", n)
	}
	batch, err := db.PeekBatch(3)
	if err != nil || len(batch) != 3 {
		t.Fatalf("peek: %v len=%d", err, len(batch))
	}
}

func TestPriorityOrdering(t *testing.T) {
	db := openTestDB(t, 100)
	now := time.Now().UTC()
	// 일부러 telemetry 먼저 → event 나중
	db.Enqueue(QueuedMessage{Topic: "t1", Payload: []byte("tel"), Priority: 3, CreatedAt: now})
	db.Enqueue(QueuedMessage{Topic: "e1", Payload: []byte("evt"), Priority: 1, CreatedAt: now.Add(time.Second)})
	db.Enqueue(QueuedMessage{Topic: "r1", Payload: []byte("rsp"), Priority: 2, CreatedAt: now.Add(2 * time.Second)})

	batch, err := db.PeekBatch(10)
	if err != nil {
		t.Fatal(err)
	}
	if string(batch[0].Payload) != "evt" {
		t.Errorf("first should be event, got %s", batch[0].Payload)
	}
	if string(batch[1].Payload) != "rsp" {
		t.Errorf("second should be response, got %s", batch[1].Payload)
	}
}

func TestDropOldestTelemetryWhenFull(t *testing.T) {
	db := openTestDB(t, 1000)
	// 한도 가득 채우기
	for i := 0; i < 1000; i++ {
		db.Enqueue(QueuedMessage{Topic: "tel", Payload: []byte("p"), Priority: 3})
	}
	n, _ := db.QueueLen()
	if n != 1000 {
		t.Fatalf("queue len = %d, want 1000", n)
	}
	// 1001번째 → drop oldest 1000개 (코드는 최소 1개 drop)
	if err := db.Enqueue(QueuedMessage{Topic: "new", Payload: []byte("new"), Priority: 3}); err != nil {
		t.Fatal(err)
	}
	n, _ = db.QueueLen()
	if n > 1000 {
		t.Errorf("queue exceeded max: %d", n)
	}
}

func TestPurgeOld(t *testing.T) {
	db := openTestDB(t, 100)
	now := time.Now().UTC()
	// 8일 전 메시지 (retention 7일)
	db.Enqueue(QueuedMessage{Topic: "old", Payload: []byte("o"), CreatedAt: now.AddDate(0, 0, -8)})
	db.Enqueue(QueuedMessage{Topic: "new", Payload: []byte("n"), CreatedAt: now})
	purged, err := db.PurgeOld()
	if err != nil {
		t.Fatal(err)
	}
	if purged != 1 {
		t.Errorf("purged = %d, want 1", purged)
	}
	n, _ := db.QueueLen()
	if n != 1 {
		t.Errorf("remaining = %d, want 1", n)
	}
}

func TestSensorHealthDegradation(t *testing.T) {
	db := openTestDB(t, 100)
	for i := 0; i < 4; i++ {
		db.SetSensorHealth("s1", false)
	}
	// 4 fails → degraded
	var state string
	db.conn.QueryRow("SELECT state FROM sensor_health WHERE channel_id='s1'").Scan(&state)
	if state != "degraded" {
		t.Errorf("state after 4 fails = %s, want degraded", state)
	}
	db.SetSensorHealth("s1", false)
	db.conn.QueryRow("SELECT state FROM sensor_health WHERE channel_id='s1'").Scan(&state)
	if state != "failed" {
		t.Errorf("state after 5 fails = %s, want failed", state)
	}
	db.SetSensorHealth("s1", true)
	db.conn.QueryRow("SELECT state FROM sensor_health WHERE channel_id='s1'").Scan(&state)
	if state != "ok" {
		t.Errorf("state after recovery = %s, want ok", state)
	}
}

func TestCommandIdempotency(t *testing.T) {
	db := openTestDB(t, 100)
	now := time.Now().UTC()
	if seen, _ := db.CommandSeen("cmd-1"); seen {
		t.Error("command should not be seen yet")
	}
	db.LogCommand("cmd-1", "ch1", "ON", "executed", "ok", now, now)
	if seen, _ := db.CommandSeen("cmd-1"); !seen {
		t.Error("command should be seen after logging")
	}
}
