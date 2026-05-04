#!/usr/bin/env bash
# uninstall-sim.sh — install-sim.sh가 만든 모든 리소스 삭제
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "ERROR: run as root" >&2
    exit 1
fi

echo "==> Stopping + disabling services"
for svc in iot-sim-gateway iot-sim-scheduler iot-sim-worker iot-sim-backend; do
    systemctl stop "$svc" 2>/dev/null || true
    systemctl disable "$svc" 2>/dev/null || true
    rm -f "/etc/systemd/system/$svc.service"
done
systemctl daemon-reload

echo "==> Removing mosquitto sim listener"
rm -f /etc/mosquitto/conf.d/iot-sim.conf
systemctl restart mosquitto 2>/dev/null || true

echo "==> Dropping PostgreSQL DB + user"
sudo -u postgres psql -c "DROP DATABASE IF EXISTS iot_sim;" >/dev/null 2>&1 || true
sudo -u postgres psql -c "DROP USER IF EXISTS iot_sim;" >/dev/null 2>&1 || true

echo "==> Removing files"
rm -rf /opt/iot-sim /etc/iot-sim /var/lib/iot-sim /var/log/iot-sim /tmp/iotsim-gopath

echo "==> Removing user"
userdel -r iotsim 2>/dev/null || true

echo "✅ Uninstall complete. (PostgreSQL/mosquitto packages는 그대로 남음 — 필요 시 apt remove)"
