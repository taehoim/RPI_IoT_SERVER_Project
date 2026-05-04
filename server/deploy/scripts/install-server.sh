#!/usr/bin/env bash
# install-server.sh — Phase 2 server install (FastAPI + Worker + Scheduler).
# Phase 1 인프라 (PostgreSQL, VerneMQ, Keycloak, Nginx) 가 이미 구동 중이라 가정.
# 실행: sudo bash deploy/scripts/install-server.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SERVER_DIR="$REPO_ROOT/server"
INSTALL_PREFIX=/opt/iot-platform/server
ETC_DIR=/etc/iot-platform
LIB_DIR=/var/lib/iot-platform
LOG_DIR=/var/log/iot-platform

# Keycloak admin (env로 override 가능)
KC_BASE_URL="${KC_BASE_URL:-http://127.0.0.1:8080}"
KC_REALM="${KC_REALM:-iot-platform}"
KC_ADMIN_USER="${KC_ADMIN_USER:-admin}"
KC_ADMIN_PASS="${KC_ADMIN_PASS:-}"
KC_CLIENT_ID="${KC_CLIENT_ID:-iot-backend}"
KC_INSTALL_BASE="${KC_INSTALL_BASE:-/opt/keycloak}"  # kcadm.sh 위치

echo "==> IoT Gateway Server install (Phase 2)"
echo "    Repo:     $REPO_ROOT"
echo "    Prefix:   $INSTALL_PREFIX"

if [[ $EUID -ne 0 ]]; then
    echo "ERROR: must run as root (sudo)" >&2
    exit 1
fi

# ----- 1. 의존성 -----
echo "==> Installing apt dependencies"
apt-get update -qq
apt-get install -y -qq python3.12 python3.12-venv python3-pip postgresql-client mosquitto-clients curl

# uv (10× faster pip)
if ! command -v uv >/dev/null 2>&1; then
    echo "==> Installing uv"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# ----- 2. iot 사용자 -----
if ! id -u iot >/dev/null 2>&1; then
    useradd --system --shell /bin/false --home-dir /opt/iot-platform --create-home iot
fi

# ----- 3. 디렉터리 -----
install -d -o iot -g iot -m 755 "$INSTALL_PREFIX"
install -d -o root -g root -m 755 "$ETC_DIR"
install -d -o iot -g iot -m 750 "$LIB_DIR" "$LOG_DIR"

# ----- 4. 코드 동기화 -----
echo "==> Syncing code → $INSTALL_PREFIX"
rsync -a --delete --exclude '.venv' --exclude '__pycache__' --exclude '.pytest_cache' \
    "$SERVER_DIR/" "$INSTALL_PREFIX/"
chown -R iot:iot "$INSTALL_PREFIX"

# ----- 5. venv + 의존성 -----
echo "==> Creating venv + installing deps (uv)"
sudo -u iot bash -c "cd $INSTALL_PREFIX && uv venv && uv pip install -e ."

# ----- 6. Keycloak client 자동 생성 (I3) -----
# 'iot-backend' confidential client 생성 + secret 추출 → backend.env에 자동 주입
KC_CLIENT_SECRET=""
if [[ -n "$KC_ADMIN_PASS" ]] && command -v "$KC_INSTALL_BASE/bin/kcadm.sh" >/dev/null 2>&1; then
    echo "==> Provisioning Keycloak client '$KC_CLIENT_ID' in realm '$KC_REALM'"
    KCADM="$KC_INSTALL_BASE/bin/kcadm.sh"
    "$KCADM" config credentials \
        --server "$KC_BASE_URL" \
        --realm master \
        --user "$KC_ADMIN_USER" \
        --password "$KC_ADMIN_PASS" >/dev/null

    # 기존 client 있으면 skip
    EXISTING=$("$KCADM" get clients -r "$KC_REALM" -q clientId="$KC_CLIENT_ID" --fields id 2>/dev/null | grep -o '"id"' | wc -l || echo 0)
    if [[ "$EXISTING" -eq 0 ]]; then
        "$KCADM" create clients -r "$KC_REALM" \
            -s clientId="$KC_CLIENT_ID" \
            -s enabled=true \
            -s publicClient=false \
            -s standardFlowEnabled=true \
            -s directAccessGrantsEnabled=true \
            -s 'redirectUris=["https://*","http://localhost*"]' >/dev/null
        echo "    Created client $KC_CLIENT_ID"
    else
        echo "    Existing client $KC_CLIENT_ID — preserving"
    fi

    CLIENT_UUID=$("$KCADM" get clients -r "$KC_REALM" -q clientId="$KC_CLIENT_ID" --fields id --format csv --noquotes | tail -n1)
    KC_CLIENT_SECRET=$("$KCADM" get "clients/$CLIENT_UUID/client-secret" -r "$KC_REALM" --fields value --format csv --noquotes | tail -n1)
    echo "    Client secret obtained (${#KC_CLIENT_SECRET} chars)"
else
    echo "==> SKIP Keycloak client provisioning"
    echo "    KC_ADMIN_PASS 미설정 또는 kcadm.sh 없음."
    echo "    수동으로 client '$KC_CLIENT_ID' 생성 후 backend.env에 KC_AUDIENCE 설정 필요."
fi

# ----- 7. env 파일 (없을 때만 sample 생성) -----
PG_PASSWORD_FILE=/etc/iot-platform/.pg_password
if [[ ! -f "$PG_PASSWORD_FILE" ]]; then
    install -m 600 -o root -g iot /dev/null "$PG_PASSWORD_FILE"
    openssl rand -hex 24 > "$PG_PASSWORD_FILE"
    echo "==> Generated PostgreSQL password ($PG_PASSWORD_FILE)"
    echo "    !!! 이 password로 'iot_user' DB role 만들어야 함:"
    echo "    sudo -u postgres psql -c \"CREATE USER iot_user WITH PASSWORD '\$(cat $PG_PASSWORD_FILE)';\""
fi
PG_PASS=$(cat "$PG_PASSWORD_FILE")

for env in backend.env worker.env scheduler.env; do
    if [[ ! -f "$ETC_DIR/$env" ]]; then
        cat > "$ETC_DIR/$env" <<EOF
APP_ENV=prod
DATABASE_URL=postgresql+asyncpg://iot_user:${PG_PASS}@127.0.0.1:5432/iot_platform
MQTT_HOST=127.0.0.1
MQTT_PORT=1883
MQTT_USERNAME=iot-backend
MQTT_PASSWORD=CHANGE_ME_VERNEMQ_PASSWORD
KC_ISSUER=$KC_BASE_URL/realms/$KC_REALM
KC_AUDIENCE=$KC_CLIENT_ID
KC_VERIFY_SIGNATURE=true
LOG_LEVEL=INFO
EOF
        # KC_CLIENT_SECRET이 있으면 추가
        if [[ -n "$KC_CLIENT_SECRET" ]]; then
            echo "KC_CLIENT_SECRET=$KC_CLIENT_SECRET" >> "$ETC_DIR/$env"
        fi
        chown root:iot "$ETC_DIR/$env"
        chmod 640 "$ETC_DIR/$env"
        echo "    Installed $ETC_DIR/$env (auto-generated PG password + KC client config)"
    else
        echo "    Existing $ETC_DIR/$env preserved"
    fi
done

# ----- 8. Alembic 마이그레이션 -----
echo "==> Running alembic upgrade head"
sudo -u iot env -i HOME="/opt/iot-platform" PATH="/usr/lib/go-1.22/bin:/usr/bin:/bin" \
    DATABASE_URL="postgresql+asyncpg://iot_user:${PG_PASS}@127.0.0.1:5432/iot_platform" \
    bash -c "cd $INSTALL_PREFIX && .venv/bin/alembic upgrade head"

# ----- 9. systemd unit -----
echo "==> Installing systemd units"
install -m 644 "$SERVER_DIR/deploy/systemd/iot-backend.service" /etc/systemd/system/
install -m 644 "$SERVER_DIR/deploy/systemd/iot-worker.service" /etc/systemd/system/
install -m 644 "$SERVER_DIR/deploy/systemd/iot-scheduler.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable iot-backend iot-worker iot-scheduler

# ----- 10. 검증 (start + curl /health) -----
echo "==> Starting services + verifying"
systemctl restart iot-backend iot-worker iot-scheduler
sleep 5

VERIFY_FAIL=0
for s in iot-backend iot-worker iot-scheduler; do
    if systemctl is-active --quiet "$s"; then
        echo "    ✅ $s: active"
    else
        echo "    ❌ $s: NOT active"
        systemctl status "$s" --no-pager -l | head -10
        VERIFY_FAIL=1
    fi
done

if curl -fsS -m 5 http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "    ✅ /health: 200"
else
    echo "    ❌ /health: failed"
    VERIFY_FAIL=1
fi

echo ""
if [[ $VERIFY_FAIL -eq 0 ]]; then
    echo "✅ Install + verify complete. All 3 services active + /health OK."
else
    echo "⚠️  Install complete, but verification has failures. Check journalctl."
fi
echo ""
echo "다음 단계:"
echo "  1. PostgreSQL DB role 생성:"
echo "     sudo -u postgres psql -c \"CREATE USER iot_user WITH PASSWORD '\$(cat $PG_PASSWORD_FILE)';\""
echo "     sudo -u postgres psql -c \"CREATE DATABASE iot_platform OWNER iot_user;\""
echo "  2. (선택) VerneMQ password file에 iot-backend 계정 생성:"
echo "     sudo vmq-passwd /etc/vernemq/vmq.passwd iot-backend"
echo "  3. sudo journalctl -fu iot-backend"
echo "  4. curl http://127.0.0.1:8000/health"
