#!/usr/bin/env bash
# sim-verify.sh — install-sim.sh 후 wire 흐름 자동 검증.
#
# 5단계 PASS/FAIL 체크:
#  1. 모든 systemd 서비스 active
#  2. mosquitto에서 telemetry 토픽 수신 (10초 내)
#  3. DB telemetry_latest에 row 존재
#  4. command 발행 → response 수신 → DB status='executed'
#  5. heartbeat 수신 + last_seen_at 갱신
set -uo pipefail

PASS=0
FAIL=0
PG_PASS=$(grep -E '^DATABASE_URL=' /etc/iot-sim/server.env 2>/dev/null | sed 's|.*://[^:]*:\([^@]*\)@.*|\1|' || true)
GW_SERIAL=$(grep -E '^  id:' /etc/iot-sim/gateway.yaml 2>/dev/null | head -1 | awk '{print $2}')

step() { echo ""; echo "------ $* ------"; }
ok() { echo "  ✅ $*"; PASS=$((PASS+1)); }
fail() { echo "  ❌ $*"; FAIL=$((FAIL+1)); }

# ----- 1. services -----
step "1. systemd services active"
for svc in postgresql mosquitto iot-sim-backend iot-sim-worker iot-sim-scheduler iot-sim-gateway; do
    state=$(systemctl is-active "$svc" 2>/dev/null || echo "FAIL")
    if [[ "$state" == "active" ]]; then
        ok "$svc: $state"
    else
        fail "$svc: $state"
    fi
done

# ----- 2. mosquitto telemetry stream -----
step "2. MQTT telemetry stream (max 12s wait)"
TMP=$(mktemp)
timeout 12 mosquitto_sub -h 127.0.0.1 -t "gw/+/telemetry" -C 1 > "$TMP" 2>/dev/null || true
if [[ -s "$TMP" ]]; then
    ok "telemetry received: $(head -c 80 "$TMP")..."
else
    fail "no telemetry in 12s"
fi
rm -f "$TMP"

# ----- 3. DB telemetry_latest row -----
step "3. PostgreSQL telemetry_latest"
COUNT=$(PGPASSWORD="$PG_PASS" psql -h 127.0.0.1 -U iot_sim -d iot_sim -tAc \
    "SELECT count(*) FROM telemetry_latest;" 2>/dev/null || echo "0")
if [[ "${COUNT:-0}" -gt 0 ]]; then
    ok "telemetry_latest rows: $COUNT"
else
    fail "telemetry_latest empty (worker not writing?)"
fi

# ----- 4. command round-trip -----
step "4. Command round-trip (relay-vent ON)"
TOKEN=$(/opt/iot-sim/bin/sim-fake-jwt 2>/dev/null)
GATEWAY_UUID=$(PGPASSWORD="$PG_PASS" psql -h 127.0.0.1 -U iot_sim -d iot_sim -tAc \
    "SELECT id FROM gateways WHERE serial_number = '$GW_SERIAL';" 2>/dev/null | tr -d ' ')
ACT_UUID=$(PGPASSWORD="$PG_PASS" psql -h 127.0.0.1 -U iot_sim -d iot_sim -tAc \
    "SELECT id FROM actuator_channels WHERE gateway_id = '$GATEWAY_UUID' AND slug = 'relay-vent';" 2>/dev/null | tr -d ' ')
if [[ -z "$ACT_UUID" ]]; then
    fail "actuator_channel relay-vent UUID 못 찾음"
else
    CMD_RESP=$(curl -s -X POST \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"actuator_channel_id\":\"$ACT_UUID\", \"action\":\"ON\", \"expires_in_sec\":15}" \
        "http://127.0.0.1:8000/api/gateways/$GATEWAY_UUID/commands" 2>/dev/null || echo '{}')
    CMD_ID=$(echo "$CMD_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null)
    if [[ -z "$CMD_ID" ]]; then
        fail "command 발행 실패: $CMD_RESP"
    else
        ok "command issued: $CMD_ID"
        sleep 3
        STATUS=$(PGPASSWORD="$PG_PASS" psql -h 127.0.0.1 -U iot_sim -d iot_sim -tAc \
            "SELECT status FROM commands WHERE id = '$CMD_ID';" 2>/dev/null | tr -d ' ')
        if [[ "$STATUS" == "executed" ]]; then
            ok "command executed (round-trip 성공)"
        else
            fail "command status: $STATUS (expected: executed)"
        fi
    fi
fi

# ----- 5. heartbeat -----
step "5. Gateway heartbeat → last_seen_at 갱신"
LAST_SEEN=$(PGPASSWORD="$PG_PASS" psql -h 127.0.0.1 -U iot_sim -d iot_sim -tAc \
    "SELECT EXTRACT(EPOCH FROM (now() - last_seen_at))::int FROM gateways WHERE serial_number = '$GW_SERIAL';" 2>/dev/null | tr -d ' ')
if [[ -n "$LAST_SEEN" ]] && [[ "$LAST_SEEN" -lt 60 ]]; then
    ok "last_seen_at within ${LAST_SEEN}s"
else
    fail "last_seen_at stale: ${LAST_SEEN:-N/A}s ago"
fi

# ----- 6. Web dashboard via nginx -----
step "6. nginx → web (Next standalone) 응답"
HTTP_STATUS=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/ 2>/dev/null || echo "000")
if [[ "$HTTP_STATUS" == "200" || "$HTTP_STATUS" == "307" || "$HTTP_STATUS" == "308" ]]; then
    ok "nginx serves web at / (HTTP $HTTP_STATUS)"
else
    fail "nginx /: expected 200/307/308, got $HTTP_STATUS"
fi

# ----- 7. nginx → /api/dashboard reachable (auth-required → 401) -----
step "7. nginx → /api/dashboard proxy 도달"
GW_UUID=$(PGPASSWORD="$PG_PASS" psql -h 127.0.0.1 -U iot_sim -d iot_sim -tAc \
    "SELECT id FROM gateways WHERE serial_number = '$GW_SERIAL';" 2>/dev/null | tr -d ' ')
if [[ -n "$GW_UUID" ]]; then
    API_STATUS=$(curl -s -o /dev/null -w '%{http_code}' \
        "http://127.0.0.1/api/dashboard?gateway_id=$GW_UUID" 2>/dev/null || echo "000")
    if [[ "$API_STATUS" == "401" || "$API_STATUS" == "200" ]]; then
        ok "/api/dashboard reachable through nginx (HTTP $API_STATUS)"
    else
        fail "/api/dashboard via nginx: expected 401/200, got $API_STATUS"
    fi
else
    fail "gateway UUID lookup failed"
fi

# ----- 결과 -----
echo ""
echo "=================================================="
echo "  PASS: $PASS    FAIL: $FAIL"
echo "=================================================="
if [[ $FAIL -gt 0 ]]; then
    echo ""
    echo "Debugging:"
    echo "  sudo journalctl -u iot-sim-worker --since '1 min ago' --no-pager | tail -40"
    echo "  sudo journalctl -u iot-sim-gateway --since '1 min ago' --no-pager | tail -40"
    exit 1
fi
echo ""
echo "✅ All wire-level checks PASS — sim 환경 정상 동작 중"
