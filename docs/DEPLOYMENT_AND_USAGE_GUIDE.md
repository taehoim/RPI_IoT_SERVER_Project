# IoT Gateway Platform — 설치 + 사용 가이드

> 작성일: 2026-05-04
> 대상: 처음 deploy하는 운영자 / 개발자
> 범위: Phase 0 (Gateway agent) + Phase 1 (서버 인프라) + Phase 2 (서버 application)
> 분량: 30-60분 따라하기 (네트워크/하드웨어 준비 시간 별도)

---

## 0. 이 문서가 답하는 질문

### Q1. 지금 deploy하면 사용자가 web portal로 다 볼 수 있나요?

**❌ 아니요. 사용자 대상 web portal (React + Vite SPA)은 Phase 3에서 만듭니다.**

지금 가능한 것:
- ✅ **Swagger UI** (`https://your-server/api/docs`) — FastAPI가 자동 생성하는 API 탐색 + 호출 도구. **개발자/관리자가 모든 기능 사용 가능**
- ✅ **ReDoc** (`/api/redoc`) — 읽기 전용 API 문서
- ✅ `curl` / Postman / Insomnia로 모든 endpoint 호출
- ✅ Telemetry 데이터는 PostgreSQL에 저장됨 — `psql` 또는 `pgAdmin`으로 직접 조회 가능
- ✅ Gateway 제어 (릴레이 ON/OFF) MQTT 명령 발행 OK
- ✅ Health check, monitoring (journalctl)

지금 안 되는 것:
- ❌ 일반 사용자용 dashboard (시계열 그래프, 카드 뷰)
- ❌ Sensor 추가 Wizard UI
- ❌ Alarm rule 설정 UI
- ❌ 모바일 친화적 화면
- ❌ Gateway 지도/위치 표시

이 모두는 **Phase 3 — Web Portal 구축** 단계 산출물입니다 (별도 sprint).

### Q2. 그러면 어떻게 사용하라는 건가요?

이 문서의 **§6 사용 가이드** 가 Swagger UI 와 curl 로 정상 운영 흐름을 따라 합니다. 영업/현장 인력이 아닌 **시스템 관리자** 1명이 사용자, 회사, 게이트웨이, 센서를 등록·관리하는 시나리오입니다.

---

## 1. 시스템 구성 한눈에 (현재까지 구현)

```
┌─────────────────────────────────────────────────────────────┐
│  USER (관리자 1명)                                            │
│      ├─ Swagger UI ✅              ← 지금 사용 가능             │
│      ├─ curl/Postman ✅            ← 지금 사용 가능             │
│      └─ React Web Portal ❌        ← Phase 3                    │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTPS + Bearer JWT
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  SERVER (Ubuntu 24.04)                                        │
│  ──────────────── Phase 1 인프라 ──────────────                │
│   Nginx :443      ✅                                          │
│   Keycloak :8080  ✅                                          │
│   PostgreSQL :5432 ✅                                         │
│   VerneMQ :1883   ✅                                          │
│  ──────────────── Phase 2 application ─────────                │
│   iot-backend :8000   ✅ (FastAPI + Swagger /api/docs)        │
│   iot-worker          ✅ (MQTT subscriber → DB)               │
│   iot-scheduler       ✅ (offline 감지, partition 관리)       │
└────────────────────────┬────────────────────────────────────┘
                         │ MQTT (gw/{id}/...)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  GATEWAY (Pi 4 또는 CM4 + eMMC) — Phase 0                     │
│   Pi OS Lite 64                                               │
│   iot-gateway.service ✅ (Go agent + cgo HAL)                 │
│      ├─ MQTT publish telemetry/state/heartbeat               │
│      ├─ subscribe command/request                            │
│      └─ Modbus RS-485 + GPIO relay 제어                      │
└────────────────────────┬────────────────────────────────────┘
                         │ RS-485 + GPIO
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  FIELD I/O                                                    │
│   📡 6-in-1 환경/가스 센서 (NH3+CO2+PM10+PM2.5+T+H)            │
│   🌬️ 환기팬 릴레이 (BCM 17)                                    │
│   💧 살균 분무기 릴레이 (BCM 27)                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 사전 요구사항

### 2.1 서버 (Ubuntu 24.04 LTS · 사내 물리 머신 권장)

| 항목 | 최소 | 권장 |
|---|---|---|
| CPU | 2 core | 4 core |
| RAM | 4 GB | 8 GB |
| Disk | 50 GB SSD | 200 GB SSD |
| Network | 100 Mbps | 1 Gbps + 고정 IP |
| OS | Ubuntu 24.04 LTS Server | 동일 |
| 도메인 | 없으면 self-signed cert (LAN 운영) | 도메인 + Let's Encrypt |

### 2.2 Gateway (Phase 0 — 1대로 시작)

| 옵션 | BOM | 권장 |
|---|---|---|
| **A. CM4 + eMMC** (권장) | CM4 4GB+16GB Lite + Waveshare CM4-IO-BASE-B + 5V 어댑터 + USB-C 데이터 케이블 | 약 18-20만원 |
| **B. Pi 4 + microSD** (저예산) | Pi 4 4GB + Class 10 microSD 32GB + 5V 3A 어댑터 | 약 12만원 |

추가 (양쪽 공통):
- USB-RS485 어댑터 (FT232 또는 CH340) ~1.5만원
- 5V 1ch 또는 4ch 릴레이 모듈 ~5천원
- 6-in-1 가스 센서 (옵션, simulator 가능) 7-15만원
- 점퍼 와이어, 12V 전원 (릴레이용)

### 2.3 네트워크 요구사항

```
[관리 PC (브라우저)]
    │ HTTPS :443
    ▼
[서버 (고정 IP)]
    │ MQTT :1883 (Phase 2 plain) / :8883 (Phase 7 TLS)
    ▼
[Gateway (DHCP OK, 같은 LAN)]
    │ RS-485 / GPIO
    ▼
[현장 센서/액추에이터]
```

방화벽 (서버):
- 22 SSH (관리 PC만 허용 권장)
- 80, 443 HTTP/HTTPS
- 1883 MQTT (LAN 내부만)
- 5432 PostgreSQL (localhost만)
- 8080 Keycloak (localhost만, Nginx 통해 노출)

---

## 3. 1단계: 서버 인프라 설치 (Phase 1)

### 3.1 OS 준비

```bash
# Ubuntu 24.04 LTS Server 설치 후
sudo apt-get update && sudo apt-get upgrade -y
sudo timedatectl set-timezone Asia/Seoul
hostnamectl set-hostname iot-platform-prod
```

### 3.2 PostgreSQL 16

```bash
sudo apt-get install -y postgresql-16 postgresql-contrib-16
sudo systemctl enable --now postgresql

# DB 사용자 + DB 2개 (iot_platform + keycloak) 생성
sudo -u postgres psql <<EOF
CREATE USER iot_user WITH PASSWORD '$(openssl rand -hex 24)';
\password iot_user   -- 또는 위 password 기록해 두세요
CREATE DATABASE iot_platform OWNER iot_user;
CREATE USER keycloak WITH PASSWORD '$(openssl rand -hex 24)';
CREATE DATABASE keycloak OWNER keycloak;
EOF

# 패스워드는 install-server.sh가 자동 생성 + /etc/iot-platform/.pg_password 에 저장
# 위 수동 단계는 sudo postgres 권한이 필요하기 때문에 분리됨.
```

### 3.3 VerneMQ

```bash
# VerneMQ 공식 .deb 다운로드 (vernemq.com 의 latest stable)
wget https://vernemq.com/release/vernemq-2.0.1.jammy.x86_64.deb
sudo dpkg -i vernemq-2.0.1.jammy.x86_64.deb
sudo systemctl enable --now vernemq

# Phase 1: anonymous 허용 (Phase 7에서 X.509 + ACL로 강화)
sudo vmq-admin listener show
# allow_anonymous = on (vernemq.conf)
sudo systemctl restart vernemq

# password file 생성 + 사용자 추가 (Phase 1 권장)
sudo vmq-passwd /etc/vernemq/vmq.passwd iot-backend   # backend용
sudo vmq-passwd /etc/vernemq/vmq.passwd gateway       # gateway용
sudo vmq-passwd /etc/vernemq/vmq.passwd admin         # 관리자용

# vernemq.conf 수정 → password file 활성화
sudo sed -i 's/^allow_anonymous = on/allow_anonymous = off/' /etc/vernemq/vernemq.conf
echo "vmq_passwd.password_file = /etc/vernemq/vmq.passwd" | sudo tee -a /etc/vernemq/vernemq.conf
sudo systemctl restart vernemq
```

### 3.4 Keycloak

```bash
# Java 17 + Keycloak 공식 release
sudo apt-get install -y openjdk-17-jdk
KC_VERSION=26.0.5
wget https://github.com/keycloak/keycloak/releases/download/$KC_VERSION/keycloak-$KC_VERSION.tar.gz
sudo tar xzf keycloak-$KC_VERSION.tar.gz -C /opt/
sudo ln -sf /opt/keycloak-$KC_VERSION /opt/keycloak

# DB 설정 (PostgreSQL backend)
sudo -u postgres psql -c "ALTER DATABASE keycloak OWNER TO keycloak;"

# 첫 admin 사용자 생성 (한 번만)
export KC_DB=postgres KC_DB_URL=jdbc:postgresql://localhost/keycloak \
       KC_DB_USERNAME=keycloak KC_DB_PASSWORD=<위에서 생성한 비번>
sudo /opt/keycloak/bin/kc.sh build
sudo KC_BOOTSTRAP_ADMIN_USERNAME=admin KC_BOOTSTRAP_ADMIN_PASSWORD=admin \
     /opt/keycloak/bin/kc.sh start-dev &
# 첫 실행 후 admin/admin 으로 로그인 → 비밀번호 변경

# systemd unit 등록 (production)
sudo tee /etc/systemd/system/keycloak.service >/dev/null <<EOF
[Unit]
Description=Keycloak
After=network.target postgresql.service

[Service]
User=keycloak
Group=keycloak
Environment=KC_DB=postgres
Environment=KC_DB_URL=jdbc:postgresql://localhost/keycloak
Environment=KC_DB_USERNAME=keycloak
Environment=KC_DB_PASSWORD=<DB password>
Environment=KC_HOSTNAME=iot-platform.example.com
Environment=KC_HTTP_ENABLED=true
Environment=KC_PROXY_HEADERS=xforwarded
ExecStart=/opt/keycloak/bin/kc.sh start --optimized
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo useradd -r -s /bin/false keycloak
sudo chown -R keycloak:keycloak /opt/keycloak-$KC_VERSION
sudo systemctl enable --now keycloak

# realm 생성 (admin 로그인 후 Master realm에서)
# realm name: iot-platform
# 7 role: system_admin, management_admin, company_admin, site_manager, operator, viewer, maintenance_engineer
# test user 1명: admin@example.com (initial-password 임시 부여)
```

### 3.5 Nginx + Let's Encrypt

```bash
sudo apt-get install -y nginx certbot python3-certbot-nginx

# nginx config
sudo tee /etc/nginx/sites-available/iot-platform >/dev/null <<'EOF'
server {
    listen 80;
    server_name iot-platform.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name iot-platform.example.com;

    # 추후 certbot이 ssl_certificate 자동 추가
    location /auth/ {
        proxy_pass http://127.0.0.1:8080/auth/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Authorization $http_authorization;
    }
    location / {
        # Phase 3: React build 결과물 위치
        # 지금은 placeholder
        return 200 '{"info": "IoT Gateway Platform", "api": "/api/", "auth": "/auth/", "docs": "/api/docs"}';
        add_header Content-Type application/json;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/iot-platform /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Let's Encrypt 인증서 (도메인 + DNS 필요)
sudo certbot --nginx -d iot-platform.example.com --non-interactive --agree-tos -m admin@example.com
```

### 3.6 Phase 1 검증

```bash
# 4 service 모두 active
for s in postgresql vernemq keycloak nginx; do
    sudo systemctl is-active $s && echo "✅ $s" || echo "❌ $s"
done

# Keycloak realm 응답
curl -fsS https://iot-platform.example.com/auth/realms/iot-platform/.well-known/openid-configuration | head -3

# MQTT broker
mosquitto_pub -h localhost -t test -m "ping" -u admin -P <password>
mosquitto_sub -h localhost -t test -u admin -P <password> -C 1

# PostgreSQL
sudo -u postgres psql -d iot_platform -c "SELECT version();"
```

---

## 4. 2단계: 서버 application 설치 (Phase 2)

### 4.1 코드 가져오기 + install-server.sh

```bash
git clone <YOUR_REPO_URL> /tmp/iot-platform
cd /tmp/iot-platform

# Keycloak admin 비번을 환경변수로 (kcadm.sh가 client 자동 생성)
sudo KC_ADMIN_USER=admin KC_ADMIN_PASS=<keycloak admin pwd> \
     KC_BASE_URL=https://iot-platform.example.com \
     bash server/deploy/scripts/install-server.sh
```

스크립트가 수행하는 것:
1. apt deps (python3.12-venv, postgresql-client, mosquitto-clients, curl)
2. uv 설치 (https://astral.sh/uv)
3. iot 시스템 사용자 생성
4. /opt/iot-platform/server, /etc/iot-platform/, /var/lib/iot-platform/, /var/log/iot-platform/ 생성
5. 코드 rsync → /opt/iot-platform/server
6. uv venv + uv pip install -e . (의존성)
7. **Keycloak client `iot-backend` 자동 생성** (kcadm.sh) → secret 추출
8. **PostgreSQL password 자동 생성** (`openssl rand -hex 24`) → /etc/iot-platform/.pg_password
9. /etc/iot-platform/{backend,worker,scheduler}.env 생성 (KC_CLIENT_SECRET 포함)
10. **alembic upgrade head** → 12 테이블 + telemetry partition 생성
11. systemd unit 3종 install + enable + restart
12. **검증**: 3 service active + curl /health 200

### 4.2 PostgreSQL DB role 생성

`install-server.sh`는 password만 자동 생성하고 user 생성은 안 함 (sudo postgres 권한 필요해 분리). 스크립트 끝 안내대로:

```bash
# install-server.sh 실행 후 password file 위치
sudo cat /etc/iot-platform/.pg_password    # 24 hex chars

# DB user 생성 + DB 권한 부여
sudo -u postgres psql <<EOF
CREATE USER iot_user WITH PASSWORD '$(sudo cat /etc/iot-platform/.pg_password)';
CREATE DATABASE iot_platform OWNER iot_user;
GRANT ALL PRIVILEGES ON DATABASE iot_platform TO iot_user;
EOF

# 다시 alembic 시도
sudo -u iot env DATABASE_URL="postgresql+asyncpg://iot_user:$(sudo cat /etc/iot-platform/.pg_password)@127.0.0.1:5432/iot_platform" \
    /opt/iot-platform/server/.venv/bin/alembic -c /opt/iot-platform/server/alembic.ini upgrade head

sudo systemctl restart iot-backend iot-worker iot-scheduler
```

### 4.3 환경변수 검증

```bash
sudo cat /etc/iot-platform/backend.env
# 다음이 포함되어야:
#   APP_ENV=prod
#   DATABASE_URL=postgresql+asyncpg://iot_user:<24hex>@127.0.0.1:5432/iot_platform
#   MQTT_HOST=127.0.0.1
#   MQTT_USERNAME=iot-backend
#   MQTT_PASSWORD=CHANGE_ME_VERNEMQ_PASSWORD   ← 수정 필요
#   KC_ISSUER=https://iot-platform.example.com/realms/iot-platform
#   KC_AUDIENCE=iot-backend
#   KC_VERIFY_SIGNATURE=true
#   KC_CLIENT_SECRET=<auto-generated by kcadm.sh>

# MQTT password 수정
sudo nano /etc/iot-platform/backend.env  # MQTT_PASSWORD 만 수정
sudo systemctl restart iot-backend
```

### 4.4 검증 (Health check)

```bash
# 3 service active
for s in iot-backend iot-worker iot-scheduler; do
    sudo systemctl is-active $s && echo "✅ $s" || echo "❌ $s"
done

# 로그 확인 (sd_notify READY 메시지가 보여야 함)
sudo journalctl -u iot-backend -n 30 --no-pager
# {"event":"sd_notify ready","level":"info","timestamp":"..."}
# uvicorn running on http://127.0.0.1:8000

# REST API 응답
curl http://127.0.0.1:8000/health
# {"status":"ok","version":"0.1.0-phase2"}

curl http://127.0.0.1:8000/health/db
# {"status":"ok","db":"ok"}

# Nginx 통해
curl https://iot-platform.example.com/api/health
# {"status":"ok","version":"0.1.0-phase2"}
```

### 4.5 Swagger UI 접근

브라우저로 **`https://iot-platform.example.com/api/docs`** 접속.

표시 내용:
- OpenAPI 3.1 자동 생성 schema
- 모든 endpoint (companies, sites, gateways, sensor-profiles, sensor-channels, actuator-channels, commands, telemetry)
- 각 endpoint 에 "Try it out" 버튼 → 브라우저 안에서 직접 호출 가능
- Authorize 버튼 (좌상단) → JWT 토큰 입력 필드

**JWT 토큰 얻는 방법:**

```bash
# Keycloak에서 token 요청 (test user 1명 미리 만들어 둬야 함)
TOKEN=$(curl -s -X POST \
    https://iot-platform.example.com/auth/realms/iot-platform/protocol/openid-connect/token \
    -d "grant_type=password" \
    -d "client_id=iot-backend" \
    -d "client_secret=$(grep KC_CLIENT_SECRET /etc/iot-platform/backend.env | cut -d= -f2)" \
    -d "username=admin@example.com" \
    -d "password=<keycloak user password>" \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

echo $TOKEN  # eyJhbGc... 길게 출력

# Swagger UI Authorize 입력란에 'Bearer <TOKEN>' 그대로 붙여넣기
```

### 4.6 첫 user provisioning (DB)

JWT는 발급되지만 백엔드 `users` 테이블에 row가 없으면 모든 API가 403 (auth.py가 auto-upsert 제거됨, C2 fix). 첫 admin user를 SQL로 직접 생성:

```bash
# Keycloak admin user의 sub claim 확인
KC_USER_SUB=$(echo $TOKEN | cut -d. -f2 | base64 -d 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)['sub'])")
echo "Keycloak sub: $KC_USER_SUB"

# users 테이블에 INSERT
sudo -u postgres psql -d iot_platform <<EOF
INSERT INTO users (id, keycloak_user_id, email, name, status)
VALUES (gen_random_uuid(), '$KC_USER_SUB', 'admin@example.com', 'Admin', 'active');
EOF
```

이제 Swagger UI에서 모든 endpoint 호출 가능.

---

## 5. 3단계: Gateway 설치 (Phase 0)

### 5.1 OS 굽기

**A. CM4 + eMMC 노선 (권장):**

```bash
# PC에서 rpiboot 설치
sudo apt-get install -y libusb-1.0-0-dev pkg-config build-essential
git clone --depth=1 https://github.com/raspberrypi/usbboot
cd usbboot && make

# Carrier board: BOOT 점퍼 GND로 → USB-C OTG → PC 연결 → 전원
sudo ./rpiboot
# eMMC가 /dev/sda 로 노출됨

# Pi Imager로 굽기 (또는 dd)
sudo rpi-imager   # GUI: Pi OS Lite 64-bit → /dev/sda

# 굽기 완료 → BOOT 점퍼 NORMAL → ethernet 연결 → 전원
```

자세한 절차: `docs/EMMC_FLASH.md` 참조.

**B. Pi 4 + microSD 노선:**

```bash
# Pi Imager로 microSD에 Pi OS Lite 64 굽기 (옵션에서 hostname/ssh/user 미리 설정)
```

자세한 절차: `docs/PI4_SETUP.md` 참조.

### 5.2 install-pi4.sh 실행

```bash
ssh iot@<gateway-ip>
git clone <YOUR_REPO_URL> ~/IoT_Gateway_Server
cd ~/IoT_Gateway_Server
sudo bash deploy/scripts/install-pi4.sh
```

### 5.3 결선 (Waveshare CM4-IO-BASE-B 또는 Pi 4 GPIO header)

```
40-pin GPIO header (BCM 번호)        주변
─────────────────────────────────────────────
Pin 1  (3.3V)                        RS-485 어댑터 VCC (옵션)
Pin 6  (GND)                         공통 GND
Pin 11 (BCM 17)                      Relay #1 IN (환기팬)
Pin 13 (BCM 27)                      Relay #2 IN (살균기)
USB Port                             USB-RS485 → /dev/ttyUSB0
```

릴레이 모듈은 **NC 단자** + 외부 12V 전원 사용 (NC = 자동 안전 상태 = relay open).

### 5.4 config.yaml 편집

```bash
sudo nano /etc/iot-gateway/config.yaml
```

핵심 수정:

```yaml
gateway:
  id: GW-LIVESTOCK-01           # 의미있는 이름 (UUID도 가능)
  name: "1번 보호소 환경 모니터"

mqtt:
  broker: tcp://<server-ip>:1883   # ★ 서버 VerneMQ로 직접 연결
  username: gateway                # ★ Phase 1 vmq-passwd로 만든 계정
  password: <vmq password>
  client_id: gateway-livestock-01

sensors:
  - channel_id: env-01
    profile_file: /opt/iot-gateway/share/profiles/livestock_6in1_rs485.json
    interface: /dev/ttyUSB0
    slave_id: 1
    polling_interval_sec: 10
    enabled: true

actuators:
  - channel_id: relay-vent
    gpio_pin: 17
    max_on_duration_sec: 600
  - channel_id: relay-spray
    gpio_pin: 27
    max_on_duration_sec: 60
```

### 5.5 시작 + 검증

```bash
sudo systemctl start iot-gateway
sudo systemctl status iot-gateway --no-pager -l
sudo journalctl -fu iot-gateway

# 서버 측 검증 (PC에서)
mosquitto_sub -h iot-platform.example.com -t 'gw/+/+' -v -u admin -P <pwd>
# 10초마다 telemetry 메시지 출력 확인
```

자세한 절차: `docs/PHASE0_RUNBOOK.md`.

---

## 6. 사용 가이드 — Swagger UI + curl 로 운영

### 6.1 Swagger UI 사용법

1. 브라우저 → `https://iot-platform.example.com/api/docs`
2. 우상단 **Authorize** 클릭
3. `value` 필드에 `Bearer eyJhbGc...` (위에서 얻은 토큰)
4. Authorize → Close
5. 어떤 endpoint든 펼쳐서 **Try it out** → Parameters 입력 → **Execute**

### 6.2 정상 운영 흐름 (관리자 1명 기준)

```
[1] Company 등록    POST /api/companies
        ↓
[2] Site 등록       POST /api/sites
        ↓
[3] Gateway 등록    POST /api/gateways           ← gateway 자동으로 admin 권한
        ↓
[4] Sensor Profile  POST /api/sensor-profiles    ← JSON Schema 검증
        ↓
[5] Sensor Channel  POST /api/gateways/{id}/sensor-channels
        ↓
[6] Actuator Ch.    POST /api/gateways/{id}/actuator-channels
        ↓
[7] 게이트웨이가 telemetry publish 시작
[8] Telemetry 조회   GET /api/gateways/{id}/latest
[9] 원격 제어        POST /api/gateways/{id}/commands
[10] 명령 결과 확인  GET /api/commands/{cmd_id}
```

### 6.3 curl 종합 예제 (전체 흐름)

```bash
# 0. 환경변수
SERVER=https://iot-platform.example.com
TOKEN=eyJhbGc...   # §4.5에서 발급
H="-H Authorization:Bearer $TOKEN -H Content-Type:application/json"

# 1. Company 등록
COMPANY_ID=$(curl -fsS $H -X POST $SERVER/api/companies \
    -d '{"name":"test-company","company_type":"customer"}' \
    | python3 -c "import json,sys;print(json.load(sys.stdin)['id'])")
echo "Company: $COMPANY_ID"

# 2. Site 등록
SITE_ID=$(curl -fsS $H -X POST $SERVER/api/sites \
    -d "{\"company_id\":\"$COMPANY_ID\",\"name\":\"보호소-1번동\",\"address\":\"경기도 ...\"}" \
    | python3 -c "import json,sys;print(json.load(sys.stdin)['id'])")
echo "Site: $SITE_ID"

# 3. Gateway 등록 (등록자 admin 권한 자동 부여)
GW_ID=$(curl -fsS $H -X POST $SERVER/api/gateways \
    -d "{\"serial_number\":\"GW-LIVESTOCK-01\",\"name\":\"1번 보호소\",\"company_id\":\"$COMPANY_ID\",\"site_id\":\"$SITE_ID\"}" \
    | python3 -c "import json,sys;print(json.load(sys.stdin)['id'])")
echo "Gateway: $GW_ID"

# !!! 중요: gateway 등록 후 client config의 gateway.id를 이 UUID로 변경하고 재시작
ssh iot@<gateway-ip> "sudo sed -i 's/id: .*/id: $GW_ID/' /etc/iot-gateway/config.yaml && sudo systemctl restart iot-gateway"

# 4. Sensor Profile 등록 (livestock 6-in-1)
PROFILE_ID=$(curl -fsS $H -X POST $SERVER/api/sensor-profiles \
    -d "$(cat <<EOF
{
  "name": "Livestock 6-in-1 RS485",
  "vendor": "Generic",
  "model": "LIVESTOCK-6IN1-RS485-01",
  "protocol": "modbus_rtu",
  "profile_schema": $(cat shared/examples/livestock_6in1_rs485.json)
}
EOF
)" | python3 -c "import json,sys;print(json.load(sys.stdin)['id'])")
echo "Profile: $PROFILE_ID"

# 5. Sensor Channel 추가
CHANNEL_ID=$(curl -fsS $H -X POST $SERVER/api/gateways/$GW_ID/sensor-channels \
    -d "{\"sensor_profile_id\":\"$PROFILE_ID\",\"display_name\":\"환경 통합 센서\",\"interface_name\":\"/dev/ttyUSB0\",\"protocol\":\"modbus_rtu\",\"slave_id\":1}" \
    | python3 -c "import json,sys;print(json.load(sys.stdin)['id'])")
echo "Channel: $CHANNEL_ID"

# 6. Actuator Channel 추가 (환기팬)
RELAY_VENT=$(curl -fsS $H -X POST $SERVER/api/gateways/$GW_ID/actuator-channels \
    -d '{"display_name":"환기팬","actuator_type":"relay","hardware_channel":"BCM17","default_state":"off","safety_config":{"max_on_duration_sec":600}}' \
    | python3 -c "import json,sys;print(json.load(sys.stdin)['id'])")
echo "Relay vent: $RELAY_VENT"

# 7. Telemetry 도착 확인 (10초 후)
sleep 15
curl -fsS $H $SERVER/api/gateways/$GW_ID/latest | python3 -m json.tool
# 출력 예:
# [
#   {"measurement_key":"ammonia","value_double":18.4,"unit":"ppm","ts":"2026-05-04T12:00:10Z"},
#   {"measurement_key":"carbon_dioxide","value_double":1230,"unit":"ppm","ts":"..."},
#   {"measurement_key":"humidity","value_double":62.3,"unit":"%","ts":"..."},
#   {"measurement_key":"pm10","value_double":45,"unit":"ug/m3","ts":"..."},
#   {"measurement_key":"pm2_5","value_double":21,"unit":"ug/m3","ts":"..."},
#   {"measurement_key":"temperature","value_double":24.7,"unit":"degC","ts":"..."}
# ]

# 8. 시계열 (최근 1시간)
curl -fsS $H "$SERVER/api/gateways/$GW_ID/telemetry?measurement_key=ammonia&hours=1&limit=100" \
    | python3 -m json.tool

# 9. 원격 제어 — 환기팬 ON (300초 후 자동 OFF)
CMD_ID=$(curl -fsS $H -X POST $SERVER/api/gateways/$GW_ID/commands \
    -d "{\"actuator_channel_id\":\"$RELAY_VENT\",\"action\":\"ON\",\"expires_in_sec\":5,\"reason\":\"manual test\"}" \
    | python3 -c "import json,sys;print(json.load(sys.stdin)['id'])")
echo "Command: $CMD_ID"

# 10. 명령 응답 확인 (gateway가 1-2초 내 처리)
sleep 3
curl -fsS $H $SERVER/api/commands/$CMD_ID | python3 -m json.tool
# {"id":"cmd-...","status":"executed","response":{"status":"executed","result":"...-ON","local_safety_check":"passed"}}

# 11. 환기팬 OFF (수동)
curl -fsS $H -X POST $SERVER/api/gateways/$GW_ID/commands \
    -d "{\"actuator_channel_id\":\"$RELAY_VENT\",\"action\":\"OFF\",\"expires_in_sec\":5}"
```

### 6.4 데이터를 보는 다른 방법

#### A. PostgreSQL 직접 조회

```bash
sudo -u postgres psql -d iot_platform <<EOF
-- 모든 gateway 상태
SELECT name, status, last_seen_at FROM gateways;

-- 특정 gateway의 최신 6 measurement
SELECT measurement_key, value_double, unit, quality, ts
FROM telemetry_latest
WHERE gateway_id = '<GW_ID>'
ORDER BY measurement_key;

-- NH3 최근 100건
SELECT ts, value_double FROM telemetry
WHERE measurement_key = 'ammonia'
  AND gateway_id = '<GW_ID>'
ORDER BY ts DESC LIMIT 100;

-- 명령 이력
SELECT id, action, status, issued_at, completed_at FROM commands
WHERE gateway_id = '<GW_ID>'
ORDER BY issued_at DESC LIMIT 10;
EOF
```

#### B. 간단 그래프 (Python matplotlib)

```bash
cat > /tmp/plot_telemetry.py <<'EOF'
import os, requests, matplotlib.pyplot as plt
from datetime import datetime

TOKEN = os.environ["TOKEN"]
GW = os.environ["GW_ID"]
SERVER = os.environ["SERVER"]

r = requests.get(
    f"{SERVER}/api/gateways/{GW}/telemetry",
    params={"measurement_key": "ammonia", "hours": 6, "limit": 1000},
    headers={"Authorization": f"Bearer {TOKEN}"},
)
data = r.json()
ts = [datetime.fromisoformat(d["ts"].replace("Z", "+00:00")) for d in reversed(data)]
v = [d["value_double"] for d in reversed(data)]
plt.plot(ts, v); plt.title("NH3 (ppm) - 6h"); plt.xticks(rotation=30)
plt.savefig("/tmp/nh3.png"); print("saved /tmp/nh3.png")
EOF
TOKEN=$TOKEN GW_ID=$GW_ID SERVER=$SERVER python3 /tmp/plot_telemetry.py
```

#### C. mosquitto로 실시간 모니터

```bash
# 모든 gateway의 모든 메시지 실시간 (관리 PC에서)
mosquitto_sub -h iot-platform.example.com -t 'gw/+/+' -v -u admin -P <pwd>

# 특정 gateway만
mosquitto_sub -h iot-platform.example.com -t "gw/$GW_ID/+" -v -u admin -P <pwd>
```

---

## 7. 운영 작업

### 7.1 로그 확인

```bash
# 실시간 (Ctrl-C로 종료)
sudo journalctl -fu iot-backend
sudo journalctl -fu iot-worker
sudo journalctl -fu iot-scheduler

# 최근 1시간 + ERROR만
sudo journalctl -u iot-backend --since "1 hour ago" -p err

# Gateway (Pi 4/CM4)
sudo journalctl -fu iot-gateway
```

### 7.2 서비스 재시작

```bash
# 단일 service
sudo systemctl restart iot-backend

# 모두
sudo systemctl restart iot-backend iot-worker iot-scheduler

# config 변경 후 (Gateway)
ssh iot@<gw-ip> sudo nano /etc/iot-gateway/config.yaml
ssh iot@<gw-ip> sudo systemctl restart iot-gateway
```

### 7.3 DB 백업

```bash
# 매일 백업 (cron 또는 systemd timer)
sudo -u postgres pg_dump iot_platform | gzip > /var/lib/iot-platform/backups/iot_platform-$(date +%Y%m%d).sql.gz

# 복원
gunzip -c iot_platform-20260504.sql.gz | sudo -u postgres psql iot_platform
```

### 7.4 새 gateway 추가 절차 (요약)

1. CM4/Pi 4 OS 굽기 (5분)
2. install-pi4.sh (5분)
3. POST /api/gateways → UUID 받기
4. config.yaml의 gateway.id를 받은 UUID로
5. systemctl restart iot-gateway
6. POST /api/sensor-channels + /api/actuator-channels
7. 끝

### 7.5 사용자 추가

```bash
# A. Keycloak admin UI에서 user 생성 + 비번 설정
#    https://iot-platform.example.com/auth/admin/

# B. 그 user의 sub (UUID) 확인 후 DB에 INSERT
sudo -u postgres psql -d iot_platform <<EOF
INSERT INTO users (id, keycloak_user_id, email, name, status)
VALUES (gen_random_uuid(), '<keycloak sub>', 'user@example.com', 'User Name', 'active');
EOF

# C. (선택) 특정 gateway에 권한 부여
sudo -u postgres psql -d iot_platform <<EOF
INSERT INTO user_gateway_permissions (id, user_id, gateway_id, permission)
SELECT gen_random_uuid(),
       (SELECT id FROM users WHERE email='user@example.com'),
       '<GW_ID>',
       'view';
EOF
```

---

## 8. Troubleshooting

### Backend 시작 후 30초마다 재시작

C1 fix 검증: `sd_notify` 호출 위치 확인.
```bash
sudo journalctl -u iot-backend | grep -i "sd_notify\|ready\|watchdog"
# "sd_notify ready" 메시지가 보여야 정상
```
없으면: `sdnotify` Python 패키지 설치 확인 (`uv pip list | grep sdnotify`), main.py의 lifespan 함수 검토.

### JWT 401 (invalid token)

- `KC_VERIFY_SIGNATURE=true` (default) 인 상태에서 발급된 token이 다른 issuer/audience면 reject
- 토큰 만료 (기본 5분) → `grant_type=refresh_token` 또는 재발급
- audience mismatch → Keycloak admin UI에서 client `iot-backend` 의 "Audience" mapper 확인

### 사용자 403 (not provisioned)

C2 fix로 auto-upsert 제거됨. §4.6의 SQL INSERT 절차 따라 사용자 사전 등록 필요.

### Gateway telemetry 안 옴 (서버에서 mosquitto_sub 무응답)

체크리스트:
1. Gateway `iot-gateway` service active?  →  `sudo systemctl status iot-gateway`
2. MQTT 연결됐나?  →  `sudo journalctl -u iot-gateway | grep mqtt`
3. 서버 mosquitto/VerneMQ에 client 보임?  →  `sudo vmq-admin session show`
4. 방화벽 1883 열림?  →  `sudo ufw status`
5. config.yaml의 broker URL 정확?
6. password 정확? (`vmq-passwd` 로 추가한 사용자/비번)

### Modbus CRC fail (sensor)

- 케이블 길이/저항 (RS-485는 종단저항 120Ω 권장)
- baudrate 불일치 (센서 datasheet 9600 vs 19200 등)
- slave_id 충돌 (같은 버스에 여러 슬레이브면 ID 분리)
- 일시적: HAL이 retry 3회 → degraded → polling 10× 감속 (정상 동작)

### Worker가 telemetry 받지만 DB에 insert 안 됨

- `sudo journalctl -u iot-worker | grep -i error`
- gateway_id가 `gateways` 테이블에 없으면 worker가 skip (Phase 2 정책 — Gateway 사전 등록 필수)
- partition 누락? → `sudo -u postgres psql -d iot_platform -c "\d+ telemetry"`

### Command 응답 timeout

- gateway 측 명령 도달 확인: `sudo journalctl -u iot-gateway | grep cmd`
- expires_at 너무 짧음? (기본 5초) → `expires_in_sec: 30` 으로 longer

---

## 9. 현재 한계 + 다음 단계 (Phase 3+)

| 기능 | 현재 (Phase 0/1/2) | Phase 3 | Phase 4 | Phase 5 | Phase 6 | Phase 7 |
|---|---|---|---|---|---|---|
| Backend REST API | ✅ | | | | | |
| Worker (telemetry) | ✅ | | | | | |
| Gateway agent | ✅ | | | | | |
| Swagger UI 도구 | ✅ | | | | | |
| 사용자 Web Portal (React) | ❌ | ✅ | | | | |
| Sensor 추가 Wizard UI | ❌ | ✅ | | | | |
| 시계열 Dashboard (ECharts) | ❌ | ✅ | | | | |
| 알람 Rule UI | ❌ | | ✅ | | | |
| 자동 환기팬 제어 (NH3 임계) | ❌ (수동만) | | ✅ | | | |
| Gateway Config 버전 관리 | ❌ | | | ✅ | | |
| OTA (Mender) | ❌ | | | ✅ | | |
| Bulk Operation | ❌ | | | | ✅ | |
| RLS (multi-tenant) | ❌ | | | | ✅ | |
| MQTT TLS + X.509 | ❌ (plain 1883) | | | | | ✅ |
| Safety MCU (STM32) | ❌ | | | | | ✅ |
| OSS Notice + SBOM | ❌ | | | | | ✅ |

### Phase 3 (다음) 진입 조건

- [ ] Phase 0/1/2 install이 사내 환경에서 1주 무중단 동작
- [ ] Gateway 1대 + 6-in-1 센서로 telemetry 24시간 round trip OK
- [ ] 명령 발행 100% (rejected/timeout 0건)
- [ ] 첫 customer (유기 보호소 운영자) 인터뷰 완료

이후 Phase 3은 React + Vite + Apache ECharts 로 web portal 구축.

---

## 10. 빠른 reference

### 자주 쓰는 명령

```bash
# 서버
sudo systemctl status iot-backend iot-worker iot-scheduler
sudo journalctl -fu iot-backend
sudo cat /etc/iot-platform/backend.env
curl http://127.0.0.1:8000/health

# Gateway
sudo systemctl status iot-gateway
sudo journalctl -fu iot-gateway
sudo cat /etc/iot-gateway/config.yaml
bash /opt/iot-gateway/scripts/smoke_test.sh

# DB
sudo -u postgres psql -d iot_platform -c "SELECT name, status FROM gateways;"
sudo -u postgres pg_dump iot_platform > /tmp/backup.sql

# MQTT
mosquitto_sub -h <server> -t 'gw/+/+' -v -u admin -P <pwd>
mosquitto_pub -h <server> -t 'test' -m 'hello' -u admin -P <pwd>

# Token 발급
curl -X POST <server>/auth/realms/iot-platform/protocol/openid-connect/token \
    -d "grant_type=password" -d "client_id=iot-backend" \
    -d "client_secret=<secret>" -d "username=<user>" -d "password=<pwd>"
```

### URL reference

| URL | 용도 |
|---|---|
| `https://<host>/` | placeholder JSON (Phase 3에서 React app) |
| `https://<host>/api/docs` | **Swagger UI** (지금 가장 자주 쓰는 화면) |
| `https://<host>/api/redoc` | ReDoc (읽기 전용 API 문서) |
| `https://<host>/api/openapi.json` | OpenAPI 3.1 schema |
| `https://<host>/api/health` | health check |
| `https://<host>/auth/admin/` | Keycloak admin console |
| `https://<host>/auth/realms/iot-platform/account` | 사용자 계정 self-service |

### 파일 위치

| 경로 | 내용 |
|---|---|
| `/opt/iot-platform/server/` | 서버 코드 + venv |
| `/etc/iot-platform/{backend,worker,scheduler}.env` | 환경변수 |
| `/etc/iot-platform/.pg_password` | PG password (root:iot 0600) |
| `/var/lib/iot-platform/backups/` | DB 백업 |
| `/var/log/iot-platform/` | 로그 (현재는 journald 우선) |
| `/etc/systemd/system/iot-{backend,worker,scheduler}.service` | systemd unit |
| `/opt/iot-gateway/` (gateway) | Gateway agent + HAL |
| `/etc/iot-gateway/config.yaml` (gateway) | Gateway config |

### 관련 문서

| 파일 | 내용 |
|---|---|
| `docs/PI4_SETUP.md` | CM4(eMMC) + Pi 4(SD) 하드웨어 셋업 |
| `docs/EMMC_FLASH.md` | rpiboot 절차 + eMMC 운영 최적화 |
| `docs/PHASE0_RUNBOOK.md` | Gateway 운영 절차서 |
| `docs/HAL_ABI.md` | C HAL ABI 명세 (Gateway 측) |
| `docs/REVIEW_PHASE1_PHASE2.md` | 코드 리뷰 결과 (해결 / 미해결 이슈) |
| `docs/diagrams/*.excalidraw` | 시스템 다이어그램 7종 |
| `server/README.md` | 서버 코드 빠른 reference |

---

## 부록 A. 30분 quickstart 체크리스트

본 가이드대로 처음 끝까지 따라 할 때 약 30-60분 소요 (네트워크 안정 가정).

```
[Server] (15분)
[ ] Ubuntu 24.04 설치 + ssh
[ ] § 3.2 PostgreSQL 16 + DB 2개
[ ] § 3.3 VerneMQ + password file
[ ] § 3.4 Keycloak + realm 생성
[ ] § 3.5 Nginx + certbot
[ ] § 3.6 Phase 1 검증 (4 service active)
[ ] § 4.1 install-server.sh 실행
[ ] § 4.2 PG user 생성 + alembic 재시도
[ ] § 4.3 backend.env 의 MQTT_PASSWORD 수정
[ ] § 4.4 health 200 확인
[ ] § 4.5 /api/docs 브라우저 열기
[ ] § 4.6 첫 user provisioning

[Gateway] (15분)
[ ] § 5.1 OS 굽기 (CM4 eMMC 또는 Pi 4 SD)
[ ] § 5.2 install-pi4.sh
[ ] § 5.3 결선 (USB-RS485, 릴레이 GPIO)
[ ] § 5.4 config.yaml 편집 (broker, gateway.id)
[ ] § 5.5 systemctl start + journalctl 확인

[End-to-end] (15분)
[ ] § 6.3 Company → Site → Gateway → Sensor → Actuator 등록
[ ] telemetry 10초 주기 도착 확인 (latest API)
[ ] command 발행 → 릴레이 toggle 확인
[ ] § 7.3 첫 백업
```

체크리스트 모두 끝나면 **deploy 가능 상태 + 1대 운영 검증 완료**.

이후 24시간 burn-in → Phase 3 (Web Portal) 진입 또는 customer 인터뷰.
