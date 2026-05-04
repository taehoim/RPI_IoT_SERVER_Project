#!/usr/bin/env bash
# install-pi4.sh — Phase 0 BCM2711 family install (build + deploy + systemd enable)
# 호환:
#   - Raspberry Pi 4 Model B (microSD)
#   - Compute Module 4 (eMMC) on Waveshare/공식 carrier board
#   - 같은 BCM2711 SoC라 OS 위 절차 동일. boot media 선택과 무관.
# 실행: sudo bash deploy/scripts/install-pi4.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
INSTALL_PREFIX=/opt/iot-gateway
ETC_DIR=/etc/iot-gateway
LIB_DIR=/var/lib/iot-gateway
LOG_DIR=/var/log/iot-gateway

echo "==> IoT Gateway Phase 0 install (Pi 4)"
echo "    Repo: $REPO_ROOT"
echo "    Prefix: $INSTALL_PREFIX"

# ----- 0. 권한 체크 -----
if [[ $EUID -ne 0 ]]; then
    echo "ERROR: must run as root (sudo)" >&2
    exit 1
fi

# ----- 1. 의존성 설치 -----
echo "==> Installing apt dependencies"
apt-get update -qq
apt-get install -y -qq \
    build-essential \
    libgpiod-dev \
    libsystemd-dev \
    golang-1.22 \
    git \
    mosquitto \
    mosquitto-clients \
    sqlite3 \
    python3 \
    python3-pip

# Pi OS Lite의 golang-1.22는 /usr/lib/go-1.22/bin/go 에 있음
export PATH="/usr/lib/go-1.22/bin:$PATH"

# ----- 2. iot 사용자 + group -----
echo "==> Creating iot user and groups"
if ! id -u iot >/dev/null 2>&1; then
    useradd --system --shell /bin/false --home-dir "$INSTALL_PREFIX" --create-home iot
fi
# watchdog 그룹은 일부 배포에 미존재 → 생성. /dev/watchdog 권한을 위해 필수.
# (없으면 iot 사용자가 /dev/watchdog 못 열고 main.go가 WARN만 출력하면서 진행 →
#  kernel WDT 실제로 비동작 → systemd hang 시 hardware reset 영구 비가동.)
groupadd -f watchdog
usermod -aG dialout,gpio,watchdog iot

# ----- 3. 디렉터리 -----
echo "==> Creating directories"
install -d -o iot -g iot -m 755 "$INSTALL_PREFIX/bin" "$INSTALL_PREFIX/share/profiles" "$INSTALL_PREFIX/docs"
install -d -o root -g root -m 755 "$ETC_DIR"
install -d -o iot -g iot -m 750 "$LIB_DIR" "$LOG_DIR"

# ----- 4. C HAL 빌드 + install -----
echo "==> Building libgw_hal.so"
cd "$REPO_ROOT/hal"
make clean
make all PLATFORM=pi4
make install PREFIX=/usr/local
ldconfig

# 단위 테스트는 선택 (Pi에서 build 시간 절약)
if [[ "${RUN_C_TESTS:-1}" == "1" ]]; then
    echo "==> Running C unit tests"
    make test
fi

# ----- 5. Go agent 빌드 -----
echo "==> Building gateway-agent (Go)"
cd "$REPO_ROOT/gateway"
go mod download
CGO_ENABLED=1 go build -ldflags "-s -w" -o "$INSTALL_PREFIX/bin/gateway-agent" ./cmd/gateway-agent
chown iot:iot "$INSTALL_PREFIX/bin/gateway-agent"

# ----- 6. Sensor profile + sample config 배포 -----
echo "==> Deploying profiles + config"
install -m 644 "$REPO_ROOT/shared/examples/"*.json "$INSTALL_PREFIX/share/profiles/"
chown iot:iot "$INSTALL_PREFIX/share/profiles/"*.json

if [[ ! -f "$ETC_DIR/config.yaml" ]]; then
    install -m 640 "$REPO_ROOT/deploy/sample-config.yaml" "$ETC_DIR/config.yaml"
    chown root:iot "$ETC_DIR/config.yaml"
    echo "    Installed default config: $ETC_DIR/config.yaml (edit before start)"
else
    echo "    Existing config preserved: $ETC_DIR/config.yaml"
fi

# Profile 경로를 /opt/iot-gateway 로 보정
sed -i "s|profile_file: shared/examples/|profile_file: /opt/iot-gateway/share/profiles/|g" "$ETC_DIR/config.yaml" || true

# ----- 7. mosquitto Phase 0 설정 (loopback only — anonymous OK on 127.0.0.1) -----
echo "==> Configuring mosquitto (Phase 0 loopback)"
# 127.0.0.1 바인딩 — gateway agent와 같은 호스트에서만 접근.
# anonymous는 loopback에 한정되므로 LAN 공격자가 relay 임의 조작 불가능.
# Phase 1+ server-gateway 통합 시 별도 listener 추가 (TLS + password file).
cat > /etc/mosquitto/conf.d/iot-gateway-phase0.conf <<EOF
listener 1883 127.0.0.1
allow_anonymous true
persistence true
persistence_location /var/lib/mosquitto/
log_dest syslog
EOF
systemctl enable --now mosquitto || true
systemctl restart mosquitto || true

# ----- 8. udev rule (USB-RS485 안정 권한 + /dev/watchdog group) -----
echo "==> udev rule for USB-RS485 + watchdog"
cat > /etc/udev/rules.d/99-iot-gateway-usb-rs485.rules <<'EOF'
# FTDI / CH340 USB-RS485 adapters
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", GROUP="dialout", MODE="0660"
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", GROUP="dialout", MODE="0660"
EOF
# /dev/watchdog: 일부 커널은 root만 접근 가능 → group=watchdog + mode=0660로 iot 접근 허용
cat > /etc/udev/rules.d/99-iot-gateway-watchdog.rules <<'EOF'
KERNEL=="watchdog", GROUP="watchdog", MODE="0660"
KERNEL=="watchdog[0-9]*", GROUP="watchdog", MODE="0660"
EOF
udevadm control --reload || true
udevadm trigger || true

# ----- 9. systemd unit -----
echo "==> Installing systemd unit"
install -m 644 "$REPO_ROOT/deploy/systemd/iot-gateway.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable iot-gateway

# ----- 10. ufw -----
echo "==> Configuring ufw (22 only; mosquitto loopback-only)"
ufw allow 22/tcp >/dev/null 2>&1 || true
# 1883은 loopback 바인딩이므로 포트 개방 불필요.

echo ""
echo "✅ Install complete."
echo ""
echo "다음 단계:"
echo "  1. sudo nano $ETC_DIR/config.yaml      # gateway.id, sensors[] 수정"
echo "  2. sudo systemctl start iot-gateway"
echo "  3. sudo journalctl -fu iot-gateway     # 로그 확인"
echo "  4. bash $REPO_ROOT/deploy/scripts/smoke_test.sh   # 7건 자동 검증"
