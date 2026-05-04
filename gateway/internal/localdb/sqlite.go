// Package localdb — SQLite 기반 telemetry/event 큐
//
// modernc.org/sqlite (pure Go) 사용 — cgo 없음.
// 큐 적재 → MQTT 복귀 시 backlog flush.
//
// 정책:
//   - retention_days 초과한 행 자동 삭제 (background)
//   - max_queue_rows 초과 시 oldest drop (insert 시점)
//   - 우선순위: event > command_response > telemetry
package localdb

import (
	"database/sql"
	"fmt"
	"log"
	"time"

	_ "modernc.org/sqlite"
)

// QueuedMessage — 큐 항목
type QueuedMessage struct {
	ID        int64
	Topic     string
	Payload   []byte
	Priority  int // 1=event(highest), 2=command_response, 3=telemetry
	CreatedAt time.Time
}

// DB — Local SQLite 핸들
type DB struct {
	conn          *sql.DB
	retentionDays int
	maxQueueRows  int
}

// Open — 파일 오픈 + schema 적용
func Open(path string, retentionDays, maxQueueRows int) (*DB, error) {
	conn, err := sql.Open("sqlite", path+"?_journal_mode=WAL&_synchronous=NORMAL&_busy_timeout=5000")
	if err != nil {
		return nil, fmt.Errorf("sqlite open: %w", err)
	}
	if err := conn.Ping(); err != nil {
		return nil, fmt.Errorf("sqlite ping: %w", err)
	}

	if _, err := conn.Exec(schemaSQL); err != nil {
		conn.Close()
		return nil, fmt.Errorf("schema: %w", err)
	}

	d := &DB{
		conn:          conn,
		retentionDays: retentionDays,
		maxQueueRows:  maxQueueRows,
	}
	return d, nil
}

const schemaSQL = `
CREATE TABLE IF NOT EXISTS queued_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    topic       TEXT NOT NULL,
    payload     BLOB NOT NULL,
    priority    INTEGER NOT NULL DEFAULT 3,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_priority_created ON queued_messages(priority, created_at);

CREATE TABLE IF NOT EXISTS sensor_health (
    channel_id   TEXT PRIMARY KEY,
    last_ok_at   TIMESTAMP,
    last_fail_at TIMESTAMP,
    consecutive_fails INTEGER DEFAULT 0,
    state        TEXT DEFAULT 'unknown'  -- ok | degraded | failed | unknown
);

CREATE TABLE IF NOT EXISTS command_log (
    command_id    TEXT PRIMARY KEY,
    channel_id    TEXT,
    action        TEXT,
    requested_at  TIMESTAMP,
    completed_at  TIMESTAMP,
    status        TEXT,
    reason        TEXT
);
`

// Close — DB 닫기
func (d *DB) Close() error {
	return d.conn.Close()
}

// Enqueue — 메시지 적재. max_queue_rows 초과 시 가장 오래된 telemetry부터 drop.
func (d *DB) Enqueue(msg QueuedMessage) error {
	if msg.Priority == 0 {
		msg.Priority = 3
	}
	if msg.CreatedAt.IsZero() {
		msg.CreatedAt = time.Now().UTC()
	}

	// 용량 체크 + drop oldest telemetry
	var count int
	if err := d.conn.QueryRow("SELECT COUNT(*) FROM queued_messages").Scan(&count); err != nil {
		return fmt.Errorf("count: %w", err)
	}
	if count >= d.maxQueueRows {
		// 가장 오래된 telemetry(priority=3)부터 삭제
		if _, err := d.conn.Exec(
			"DELETE FROM queued_messages WHERE id IN (SELECT id FROM queued_messages WHERE priority=3 ORDER BY created_at ASC LIMIT 1000)",
		); err != nil {
			log.Printf("[localdb] drop oldest telemetry failed: %v", err)
		}
	}

	_, err := d.conn.Exec(
		"INSERT INTO queued_messages(topic, payload, priority, created_at) VALUES(?, ?, ?, ?)",
		msg.Topic, msg.Payload, msg.Priority, msg.CreatedAt,
	)
	return err
}

// PeekBatch — 우선순위 + timestamp 순으로 N개 조회 (삭제 안 함)
func (d *DB) PeekBatch(n int) ([]QueuedMessage, error) {
	rows, err := d.conn.Query(
		"SELECT id, topic, payload, priority, created_at FROM queued_messages ORDER BY priority ASC, created_at ASC LIMIT ?",
		n,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	out := []QueuedMessage{}
	for rows.Next() {
		var m QueuedMessage
		if err := rows.Scan(&m.ID, &m.Topic, &m.Payload, &m.Priority, &m.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, m)
	}
	return out, rows.Err()
}

// Delete — 발송 완료된 메시지 제거
func (d *DB) Delete(id int64) error {
	_, err := d.conn.Exec("DELETE FROM queued_messages WHERE id = ?", id)
	return err
}

// PurgeOld — retention_days 초과한 행 정리 (background에서 주기 호출)
func (d *DB) PurgeOld() (int, error) {
	cutoff := time.Now().UTC().Add(-time.Duration(d.retentionDays) * 24 * time.Hour)
	res, err := d.conn.Exec("DELETE FROM queued_messages WHERE created_at < ?", cutoff)
	if err != nil {
		return 0, err
	}
	n, _ := res.RowsAffected()
	return int(n), nil
}

// QueueLen — 현재 큐 크기
func (d *DB) QueueLen() (int, error) {
	var n int
	err := d.conn.QueryRow("SELECT COUNT(*) FROM queued_messages").Scan(&n)
	return n, err
}

// SetSensorHealth — 센서 health 상태 저장
func (d *DB) SetSensorHealth(channelID string, ok bool) error {
	now := time.Now().UTC()
	if ok {
		_, err := d.conn.Exec(
			`INSERT INTO sensor_health(channel_id, last_ok_at, consecutive_fails, state)
			 VALUES(?, ?, 0, 'ok')
			 ON CONFLICT(channel_id) DO UPDATE SET
			   last_ok_at = excluded.last_ok_at,
			   consecutive_fails = 0,
			   state = 'ok'`,
			channelID, now,
		)
		return err
	}
	_, err := d.conn.Exec(
		`INSERT INTO sensor_health(channel_id, last_fail_at, consecutive_fails, state)
		 VALUES(?, ?, 1, 'degraded')
		 ON CONFLICT(channel_id) DO UPDATE SET
		   last_fail_at = excluded.last_fail_at,
		   consecutive_fails = sensor_health.consecutive_fails + 1,
		   state = CASE WHEN sensor_health.consecutive_fails + 1 >= 5 THEN 'failed' ELSE 'degraded' END`,
		channelID, now,
	)
	return err
}

// LogCommand — command 처리 결과 기록
func (d *DB) LogCommand(commandID, channelID, action, status, reason string, requestedAt, completedAt time.Time) error {
	_, err := d.conn.Exec(
		`INSERT OR REPLACE INTO command_log(command_id, channel_id, action, requested_at, completed_at, status, reason)
		 VALUES(?, ?, ?, ?, ?, ?, ?)`,
		commandID, channelID, action, requestedAt, completedAt, status, reason,
	)
	return err
}

// CommandSeen — command_id 중복 실행 방지 (idempotency)
func (d *DB) CommandSeen(commandID string) (bool, error) {
	var n int
	err := d.conn.QueryRow("SELECT COUNT(*) FROM command_log WHERE command_id = ?", commandID).Scan(&n)
	return n > 0, err
}
