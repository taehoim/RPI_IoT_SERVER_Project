#!/usr/bin/env bash
# install-sim.sh — IoT Gateway Server 시뮬레이션 모드 단일 호스트 설치
#
# 목적: 실 라즈베리파이/CM4 + 실 센서/액추에이터 없이 한 대의 Ubuntu 머신에서
#       Gateway agent (sim 모드) ↔ MQTT broker ↔ Server (FastAPI + Worker + Scheduler) ↔
#       PostgreSQL 의 end-to-end wire 흐름을 검증.
#
# 가정:
#   - Ubuntu 22.04 / 24.04 (다른 배포는 패키지명 조정 필요)
#   - sudo 가능
#   - 외부 인터넷 (apt + go.dev + pypi)
#
# 미포함 (의도적):
#   - Keycloak: KC_VERIFY_SIGNATURE=false로 우회. API 호출은 unsigned JWT 사용.
#     Production은 Phase 1+ install-server.sh 별도 사용.
#   - VerneMQ: mosquitto (loopback only) 로 대체. 단일 broker 충분.
#   - TLS: Phase 7 항목, sim에서는 plain.
#
# 사용:
#   sudo bash deploy/scripts/install-sim.sh         # 설치 + 자동 시드 + systemd 시작
#   sudo bash deploy/scripts/install-sim.sh --reset # 기존 sim DB/state 초기화 후 재설치
#
# 검증:
#   docs/SIMULATION_GUIDE.md 참조 — mosquitto_sub로 telemetry 관찰 + curl로 명령 발행

set -euo pipefail

# ---------- 0. 사전 점검 -----------
if [[ $EUID -ne 0 ]]; then
    echo "ERROR: must run as root (sudo bash $0)" >&2
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESET_FLAG=0
for arg in "$@"; do
    [[ "$arg" == "--reset" ]] && RESET_FLAG=1
done

# 경로 (Phase 1 install-server.sh와 별개의 sim prefix)
SIM_PREFIX=/opt/iot-sim
SIM_ETC=/etc/iot-sim
SIM_LIB=/var/lib/iot-sim
SIM_LOG=/var/log/iot-sim
SIM_USER=iotsim

PG_DB=iot_sim
PG_USER=iot_sim
PG_PASS=$(openssl rand -hex 16)

MQTT_HOST=127.0.0.1
MQTT_PORT=1883

GATEWAY_SERIAL=GW-SIMTEST
KC_FAKE_SECRET="sim-shared-secret-$(openssl rand -hex 8)"

echo "=================================================="
echo "  IoT Gateway Server — Simulation Install"
echo "=================================================="
echo "  Repo:        $REPO_ROOT"
echo "  Sim prefix:  $SIM_PREFIX"
echo "  Sim user:    $SIM_USER"
echo "  PG DB/user:  $PG_DB / $PG_USER"
echo "  MQTT:        tcp://$MQTT_HOST:$MQTT_PORT (loopback)"
echo "  Gateway ID:  $GATEWAY_SERIAL"
echo "=================================================="

# ---------- 1. apt 의존성 -----------
echo "==> Installing apt packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
    mosquitto mosquitto-clients \
    postgresql postgresql-contrib \
    python3 python3-venv python3-pip \
    curl jq sqlite3 \
    build-essential \
    git

# Go (apt golang-1.22 또는 직접 다운로드 fallback)
if ! command -v go >/dev/null 2>&1; then
    echo "==> Installing Go (apt)"
    if ! apt-get install -y -qq golang-1.22 2>/dev/null; then
        echo "    apt golang-1.22 unavailable, downloading portable Go"
        curl -sLo /tmp/go.tar.gz https://go.dev/dl/go1.22.10.linux-amd64.tar.gz
        rm -rf /usr/local/go
        tar -xzf /tmp/go.tar.gz -C /usr/local
        ln -sf /usr/local/go/bin/go /usr/local/bin/go
    else
        ln -sf /usr/lib/go-1.22/bin/go /usr/local/bin/go
    fi
fi
go version

# ---------- 2. 사용자 + 디렉터리 -----------
echo "==> Creating sim user and directories"
if ! id -u "$SIM_USER" >/dev/null 2>&1; then
    useradd --system --shell /bin/false --home-dir "$SIM_PREFIX" --create-home "$SIM_USER"
fi

install -d -o "$SIM_USER" -g "$SIM_USER" -m 755 "$SIM_PREFIX/bin" "$SIM_PREFIX/share/profiles"
install -d -o root      -g "$SIM_USER" -m 750 "$SIM_ETC"
install -d -o "$SIM_USER" -g "$SIM_USER" -m 750 "$SIM_LIB" "$SIM_LOG"

# ---------- 3. mosquitto (loopback only) -----------
echo "==> Configuring mosquitto (loopback only — sim mode anonymous OK)"
# 주의: Ubuntu 24.04 mosquitto 2.0.18 기본 /etc/mosquitto/mosquitto.conf 가 이미
#   persistence true + persistence_location /var/lib/mosquitto/ + log_dest file ...
# 을 선언하므로 conf.d에서 중복 선언하면 "Duplicate persistence_location value" 에러.
# 따라서 listener / allow_anonymous / log_dest 만 추가 (log_dest는 추가 가능).
# WSL은 rsyslog 미설치 기본이라 syslog 대신 stderr (journald가 캡처).
cat > /etc/mosquitto/conf.d/iot-sim.conf <<EOF
# IoT sim — loopback only listener. anonymous는 127.0.0.1 한정이므로 LAN 노출 없음.
listener 1883 127.0.0.1
allow_anonymous true
log_dest stderr
EOF
systemctl reset-failed mosquitto 2>/dev/null || true
systemctl enable mosquitto
systemctl restart mosquitto
sleep 1
if ! systemctl is-active --quiet mosquitto; then
    echo "ERROR: mosquitto failed to start. Diagnostics:" >&2
    sudo -u mosquitto /usr/sbin/mosquitto -c /etc/mosquitto/mosquitto.conf 2>&1 | head -10 >&2
    exit 1
fi

# ---------- 4. PostgreSQL — DB + user + reset 옵션 -----------
echo "==> Configuring PostgreSQL"
systemctl enable --now postgresql

PG_DROP_AND_CREATE=0
if [[ $RESET_FLAG -eq 1 ]]; then
    PG_DROP_AND_CREATE=1
fi

# user 존재? + password 갱신
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$PG_USER'" | grep -q 1; then
    if [[ $RESET_FLAG -eq 1 ]]; then
        sudo -u postgres psql -c "ALTER USER $PG_USER WITH PASSWORD '$PG_PASS';" >/dev/null
    else
        # 기존 비밀번호 유지 — 새 비밀번호 생성 안 함 위해 .env 재사용
        if [[ -f "$SIM_ETC/server.env" ]]; then
            PG_PASS=$(grep -E '^DATABASE_URL=' "$SIM_ETC/server.env" | sed 's|.*://[^:]*:\([^@]*\)@.*|\1|')
            echo "    reusing existing password from $SIM_ETC/server.env"
        else
            sudo -u postgres psql -c "ALTER USER $PG_USER WITH PASSWORD '$PG_PASS';" >/dev/null
        fi
    fi
else
    sudo -u postgres psql -c "CREATE USER $PG_USER WITH PASSWORD '$PG_PASS';" >/dev/null
fi

if [[ $PG_DROP_AND_CREATE -eq 1 ]] && sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$PG_DB'" | grep -q 1; then
    echo "    --reset: dropping existing $PG_DB"
    sudo -u postgres psql -c "DROP DATABASE $PG_DB;" >/dev/null
fi
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$PG_DB'" | grep -q 1; then
    sudo -u postgres psql -c "CREATE DATABASE $PG_DB OWNER $PG_USER;" >/dev/null
fi

# ---------- 5. Server Python venv + alembic -----------
echo "==> Installing server Python deps"
SERVER_VENV="$SIM_PREFIX/server-venv"
if [[ ! -d "$SERVER_VENV" ]]; then
    python3 -m venv "$SERVER_VENV"
fi
"$SERVER_VENV/bin/pip" install --quiet --upgrade pip
# server pyproject.toml 기반
"$SERVER_VENV/bin/pip" install --quiet -e "$REPO_ROOT/server"

# 대체 경로: sdnotify 등 일부 deps는 pyproject에 없으면 명시
"$SERVER_VENV/bin/pip" install --quiet sdnotify python-jose[cryptography]
chown -R "$SIM_USER:$SIM_USER" "$SERVER_VENV"

# server.env (backend/worker/scheduler 공통)
cat > "$SIM_ETC/server.env" <<EOF
DATABASE_URL=postgresql+asyncpg://$PG_USER:$PG_PASS@127.0.0.1:5432/$PG_DB
# ALEMBIC_DATABASE_URL은 별도 변수로 사용 안 함 (env.py가 DATABASE_URL 직접 read).
# 본 sim 설정은 driver-prefixed URL 통일.
MQTT_HOST=$MQTT_HOST
MQTT_PORT=$MQTT_PORT
MQTT_USERNAME=
MQTT_PASSWORD=
MQTT_CLIENT_ID=iot-backend-sim
MQTT_KEEPALIVE=30
APP_ENV=sim
LOG_LEVEL=INFO
KC_VERIFY_SIGNATURE=false
KC_ISSUER=http://localhost:8080/realms/iot-sim
KC_AUDIENCE=iot-backend
KC_HS256_SECRET=$KC_FAKE_SECRET
COMMAND_DEFAULT_EXPIRES_SEC=10
EOF
chown root:"$SIM_USER" "$SIM_ETC/server.env"
chmod 640 "$SIM_ETC/server.env"

# alembic upgrade — env.py가 async (asyncpg) 전용이므로 driver-prefixed URL 필수.
# postgresql:// (sync, psycopg2) 넘기면 ModuleNotFoundError: No module named 'psycopg2'.
echo "==> Running alembic migrations (0001 + 0002)"
cd "$REPO_ROOT/server"
DATABASE_URL="postgresql+asyncpg://$PG_USER:$PG_PASS@127.0.0.1:5432/$PG_DB" \
    "$SERVER_VENV/bin/alembic" upgrade head

# ---------- 6. Seed data: company/site/user/gateway/channels -----------
echo "==> Seeding sim data (1 gateway, 6 sensor channels, 2 actuator channels)"
SEED_PASSWORD="$PG_PASS" SEED_DB="$PG_DB" SEED_USER="$PG_USER" \
    SEED_GATEWAY="$GATEWAY_SERIAL" \
    "$SERVER_VENV/bin/python3" "$REPO_ROOT/deploy/scripts/sim-seed.py"

# ---------- 7. Gateway agent (sim 빌드) -----------
echo "==> Building gateway-agent (-tags simulation, no cgo)"
cd "$REPO_ROOT/gateway"
sudo -u "$SIM_USER" -H GOPATH=/tmp/iotsim-gopath go mod download
CGO_ENABLED=0 sudo -u "$SIM_USER" -H GOPATH=/tmp/iotsim-gopath \
    go build -tags simulation -ldflags "-s -w" \
    -o "$SIM_PREFIX/bin/gateway-agent-sim" \
    ./cmd/gateway-agent
chown "$SIM_USER:$SIM_USER" "$SIM_PREFIX/bin/gateway-agent-sim"

# Sensor profile (livestock 6-in-1 변형 — sim 모드는 modbus 정보 무시하지만 schema 형식은 필요)
install -m 644 "$REPO_ROOT/shared/examples/livestock_6in1_rs485.json" \
    "$SIM_PREFIX/share/profiles/sim-env-6in1.json"

# Gateway sim config
cat > "$SIM_ETC/gateway.yaml" <<EOF
gateway:
  id: $GATEWAY_SERIAL
  name: Sim Gateway 01
  heartbeat_sec: 10
mqtt:
  broker: tcp://$MQTT_HOST:$MQTT_PORT
  client_id: gw-$GATEWAY_SERIAL
  qos: 1
  clean_session: false
  connect_timeout_sec: 5
storage:
  db_path: $SIM_LIB/local.db
  retention_days: 7
  max_queue_rows: 50000
watchdog:
  sd_notify_interval_sec: 10
  kernel_wdt_enabled: false   # sim에서는 /dev/watchdog 비활성
simulation:
  enabled: true
  pattern: sine
  jitter_percent: 3.0
  seed: 0   # 0 = 시간 기반 (매 시작마다 다른 값)
sensors:
  - channel_id: env-1
    display_name: 환경 6-in-1 센서
    profile_file: $SIM_PREFIX/share/profiles/sim-env-6in1.json
    interface: /dev/null
    baud: 9600
    parity: "N"
    data_bits: 8
    stop_bits: 1
    slave_id: 1
    polling_interval_sec: 5
    enabled: true
actuators:
  - channel_id: relay-vent
    display_name: 환기팬
    type: relay
    gpio_pin: 17
    default_state: "off"
    max_on_duration_sec: 600
    enabled: true
  - channel_id: relay-spray
    display_name: 살균기
    type: relay
    gpio_pin: 27
    default_state: "off"
    max_on_duration_sec: 60
    enabled: true
EOF
chown root:"$SIM_USER" "$SIM_ETC/gateway.yaml"
chmod 640 "$SIM_ETC/gateway.yaml"

# ---------- 8. systemd units (4개) -----------
echo "==> Installing systemd units"

cat > /etc/systemd/system/iot-sim-backend.service <<EOF
[Unit]
Description=IoT Sim Backend (FastAPI + uvicorn)
After=network.target postgresql.service mosquitto.service
Wants=network.target

[Service]
Type=notify
User=$SIM_USER
Group=$SIM_USER
WorkingDirectory=$SIM_PREFIX
EnvironmentFile=$SIM_ETC/server.env
ExecStart=$SERVER_VENV/bin/iot-backend
WatchdogSec=30
Restart=always
RestartSec=5
NoNewPrivileges=true
ProtectSystem=full
ReadWritePaths=$SIM_LIB $SIM_LOG
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/iot-sim-worker.service <<EOF
[Unit]
Description=IoT Sim Worker (MQTT subscriber → DB)
After=network.target postgresql.service mosquitto.service iot-sim-backend.service

[Service]
Type=notify
User=$SIM_USER
Group=$SIM_USER
WorkingDirectory=$SIM_PREFIX
EnvironmentFile=$SIM_ETC/server.env
ExecStart=$SERVER_VENV/bin/iot-worker
WatchdogSec=30
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/iot-sim-scheduler.service <<EOF
[Unit]
Description=IoT Sim Scheduler (periodic jobs)
After=network.target postgresql.service iot-sim-backend.service

[Service]
Type=notify
User=$SIM_USER
Group=$SIM_USER
WorkingDirectory=$SIM_PREFIX
EnvironmentFile=$SIM_ETC/server.env
ExecStart=$SERVER_VENV/bin/iot-scheduler
WatchdogSec=30
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/iot-sim-gateway.service <<EOF
[Unit]
Description=IoT Sim Gateway Agent (synthetic sensor data)
After=network.target mosquitto.service

[Service]
Type=notify
User=$SIM_USER
Group=$SIM_USER
WorkingDirectory=$SIM_PREFIX
ExecStart=$SIM_PREFIX/bin/gateway-agent-sim --config $SIM_ETC/gateway.yaml
WatchdogSec=30
Restart=always
RestartSec=5
ReadWritePaths=$SIM_LIB
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable iot-sim-backend iot-sim-worker iot-sim-scheduler iot-sim-gateway
systemctl restart iot-sim-backend
sleep 2
systemctl restart iot-sim-worker iot-sim-scheduler iot-sim-gateway
sleep 2

# ---------- 9. Fake JWT helper script -----------
echo "==> Installing JWT helper for API testing"
install -m 755 "$REPO_ROOT/deploy/scripts/sim-fake-jwt.py" "$SIM_PREFIX/bin/sim-fake-jwt"

# ---------- 10. 검증 출력 -----------
echo ""
echo "=================================================="
echo "  ✅ Installation complete"
echo "=================================================="
echo ""
echo "Services:"
for svc in postgresql mosquitto iot-sim-backend iot-sim-worker iot-sim-scheduler iot-sim-gateway; do
    state=$(systemctl is-active "$svc" 2>/dev/null || echo "FAIL")
    echo "  $svc: $state"
done
echo ""
echo "Quick verify:"
echo "  # Telemetry stream (별도 터미널, 5초마다 새 메시지)"
echo "  mosquitto_sub -h 127.0.0.1 -t 'gw/+/#' -v"
echo ""
echo "  # JWT 발급 + Telemetry API 조회 (예시)"
echo "  TOKEN=\$(sudo $SIM_PREFIX/bin/sim-fake-jwt)"
echo "  curl -s -H \"Authorization: Bearer \$TOKEN\" \\"
echo "       http://127.0.0.1:8000/api/gateways/$GATEWAY_SERIAL/telemetry/latest | jq"
echo ""
echo "  # 명령 발행 (relay-vent ON)"
echo "  curl -s -X POST -H \"Authorization: Bearer \$TOKEN\" -H 'Content-Type: application/json' \\"
echo "       -d '{\"actuator_channel_id\":\"<UUID>\", \"action\":\"ON\"}' \\"
echo "       http://127.0.0.1:8000/api/gateways/<gateway_uuid>/commands"
echo ""
echo "Logs:"
echo "  sudo journalctl -fu iot-sim-gateway   # gateway"
echo "  sudo journalctl -fu iot-sim-worker    # server worker"
echo ""
echo "Cleanup:"
echo "  sudo bash $REPO_ROOT/deploy/scripts/uninstall-sim.sh"
echo ""
echo "Full guide: docs/SIMULATION_GUIDE.md"
