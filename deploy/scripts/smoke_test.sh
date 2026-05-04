#!/usr/bin/env bash
# smoke_test.sh — Phase 0 7건 검증
# Pi 4에서 실행: bash deploy/scripts/smoke_test.sh
# 종료 코드 0 = all PASS, 비정상 = 실패 카운트
set -uo pipefail

PASS=0
FAIL=0
GATEWAY_ID="${GATEWAY_ID:-GW-DEV01}"
MQTT_HOST="${MQTT_HOST:-127.0.0.1}"

color_g='\033[0;32m'; color_r='\033[0;31m'; color_y='\033[1;33m'; color_n='\033[0m'

pass() { echo -e "${color_g}✓ PASS${color_n} $1"; PASS=$((PASS+1)); }
fail() { echo -e "${color_r}✗ FAIL${color_n} $1"; FAIL=$((FAIL+1)); }
info() { echo -e "${color_y}→${color_n} $1"; }

echo "===== IoT Gateway Phase 0 smoke test ====="
echo "  Gateway: $GATEWAY_ID"
echo "  MQTT:    $MQTT_HOST"
echo ""

# ----- #1: systemd active -----
info "1) systemctl is-active iot-gateway"
if systemctl is-active --quiet iot-gateway; then
    pass "iot-gateway is active"
else
    fail "iot-gateway not active"
    systemctl status iot-gateway --no-pager -l | head -20
fi

# ----- #2: mosquitto active -----
info "2) systemctl is-active mosquitto"
if systemctl is-active --quiet mosquitto; then
    pass "mosquitto is active"
else
    fail "mosquitto not active"
fi

# ----- #3: telemetry round trip -----
info "3) telemetry round trip (15초 대기)"
TMP_OUT=$(mktemp)
timeout 15 mosquitto_sub -h "$MQTT_HOST" -t "gw/$GATEWAY_ID/telemetry" -C 1 > "$TMP_OUT" 2>/dev/null || true
if [[ -s "$TMP_OUT" ]]; then
    if grep -q "values" "$TMP_OUT"; then
        pass "telemetry received"
    else
        fail "telemetry payload malformed: $(head -c 200 "$TMP_OUT")"
    fi
else
    fail "no telemetry within 15s (sensor 미연결 가능 — simulator 실행 필요)"
fi
rm -f "$TMP_OUT"

# ----- #4: command round trip -----
info "4) command round trip (relay-01 ON → response)"
RESP_FILE=$(mktemp)
mosquitto_sub -h "$MQTT_HOST" -t "gw/$GATEWAY_ID/command/response" -C 1 > "$RESP_FILE" 2>/dev/null &
SUB_PID=$!
sleep 0.5

mosquitto_pub -h "$MQTT_HOST" -t "gw/$GATEWAY_ID/command/request" -m "$(cat <<EOF
{
  "command_id": "smoke-cmd-$(date +%s)",
  "gateway_id": "$GATEWAY_ID",
  "target_type": "actuator",
  "actuator_channel_id": "relay-01",
  "action": "ON",
  "issued_by": "smoke_test",
  "issued_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "expires_at": "$(date -u -d '+5 seconds' +%Y-%m-%dT%H:%M:%SZ)",
  "timeout_ms": 3000,
  "require_ack": true,
  "reason": "smoke_test"
}
EOF
)"

wait $SUB_PID 2>/dev/null || true
if [[ -s "$RESP_FILE" ]] && grep -q '"status":"executed"' "$RESP_FILE"; then
    pass "command executed"
else
    fail "command response missing or status != executed: $(head -c 200 "$RESP_FILE")"
fi
rm -f "$RESP_FILE"

# 안전: 다시 OFF
mosquitto_pub -h "$MQTT_HOST" -t "gw/$GATEWAY_ID/command/request" -m "$(cat <<EOF
{
  "command_id": "smoke-off-$(date +%s)",
  "gateway_id": "$GATEWAY_ID",
  "actuator_channel_id": "relay-01",
  "action": "OFF",
  "expires_at": "$(date -u -d '+5 seconds' +%Y-%m-%dT%H:%M:%SZ)",
  "require_ack": false
}
EOF
)" || true

# ----- #5: expired command rejected -----
info "5) expired command rejected"
RESP_FILE=$(mktemp)
mosquitto_sub -h "$MQTT_HOST" -t "gw/$GATEWAY_ID/command/response" -C 1 > "$RESP_FILE" 2>/dev/null &
SUB_PID=$!
sleep 0.5

mosquitto_pub -h "$MQTT_HOST" -t "gw/$GATEWAY_ID/command/request" -m "$(cat <<EOF
{
  "command_id": "smoke-exp-$(date +%s)",
  "gateway_id": "$GATEWAY_ID",
  "actuator_channel_id": "relay-01",
  "action": "ON",
  "expires_at": "2020-01-01T00:00:00Z",
  "require_ack": true
}
EOF
)"

wait $SUB_PID 2>/dev/null || true
if grep -q '"status":"rejected"' "$RESP_FILE" && grep -q "expired" "$RESP_FILE"; then
    pass "expired command rejected"
else
    fail "expired command not properly rejected: $(head -c 200 "$RESP_FILE")"
fi
rm -f "$RESP_FILE"

# ----- #6: SIGSTOP recovery (systemd watchdog) -----
info "6) SIGSTOP → systemd WatchdogSec=30 recovery"
PID=$(systemctl show -p MainPID --value iot-gateway)
if [[ "$PID" -gt 0 ]]; then
    kill -SIGSTOP "$PID" 2>/dev/null || true
    info "  sent SIGSTOP to PID $PID, waiting up to 45s for systemd restart..."
    SLEEP=0
    while [[ $SLEEP -lt 45 ]]; do
        NEW_PID=$(systemctl show -p MainPID --value iot-gateway)
        if [[ "$NEW_PID" != "$PID" ]] && [[ "$NEW_PID" -gt 0 ]]; then
            pass "systemd restarted ($PID → $NEW_PID)"
            break
        fi
        sleep 2
        SLEEP=$((SLEEP+2))
    done
    if [[ "$NEW_PID" == "$PID" ]] || [[ "$NEW_PID" == "0" ]]; then
        # SIGCONT로 보내서 stuck 해제 후 다시 죽이기
        kill -SIGCONT "$PID" 2>/dev/null || true
        fail "systemd did not restart within 45s (WatchdogSec=30)"
    fi
else
    fail "could not get MainPID"
fi

# ----- #7: SQLite buffer + mosquitto restart -----
info "7) mosquitto restart → telemetry buffered → backlog flush"
PRE_COUNT=$(sqlite3 /var/lib/iot-gateway/local.db "SELECT COUNT(*) FROM queued_messages" 2>/dev/null || echo "?")
info "  pre-test queue size: $PRE_COUNT"
sudo systemctl stop mosquitto
sleep 15  # gateway가 publish 시도 → SQLite 큐 적재
MID_COUNT=$(sqlite3 /var/lib/iot-gateway/local.db "SELECT COUNT(*) FROM queued_messages" 2>/dev/null || echo "?")
info "  during-down queue size: $MID_COUNT (should be > pre)"
sudo systemctl start mosquitto
sleep 20
POST_COUNT=$(sqlite3 /var/lib/iot-gateway/local.db "SELECT COUNT(*) FROM queued_messages" 2>/dev/null || echo "?")
info "  post-recovery queue size: $POST_COUNT"
if [[ "$MID_COUNT" -gt "$PRE_COUNT" ]] 2>/dev/null && [[ "$POST_COUNT" -le "$MID_COUNT" ]] 2>/dev/null; then
    pass "queue grew during outage and shrank after recovery"
else
    fail "queue behavior anomaly (pre=$PRE_COUNT mid=$MID_COUNT post=$POST_COUNT)"
fi

# ----- 결과 요약 -----
echo ""
echo "===== Result: $PASS passed, $FAIL failed ====="
if [[ $FAIL -eq 0 ]]; then
    echo -e "${color_g}ALL PASS — Phase 0 smoke test green${color_n}"
    exit 0
else
    echo -e "${color_r}$FAIL test(s) failed${color_n}"
    exit "$FAIL"
fi
