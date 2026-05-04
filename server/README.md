# IoT Gateway Server (Phase 2)

자체 호스팅 IoT Fleet Management Platform — **서버 사이드 초기 버전**.

Phase 1 인프라 (Ubuntu 24.04 + PostgreSQL 16 + VerneMQ + Keycloak + Nginx) 위에서 동작.

## 구성

```
server/
├── pyproject.toml          # uv-based deps (FastAPI · SQLAlchemy 2.0 async · alembic · aiomqtt · ...)
├── alembic.ini + alembic/  # DB schema 마이그레이션 (12 핵심 테이블)
├── app/                    # Backend FastAPI (:8000)
│   ├── main.py             # entry + lifespan
│   ├── config.py           # pydantic-settings
│   ├── db.py               # async session
│   ├── models.py           # 12 ORM 모델
│   ├── schemas.py          # Pydantic v2 DTO
│   ├── auth.py             # JWT decode (Phase 7: JWKS verify)
│   ├── mqtt_publisher.py   # command publish용 aiomqtt
│   └── routers/            # 8 라우터 (health/companies/sites/gateways/sensor_*/actuator/commands/telemetry)
├── worker/                 # MQTT subscriber → DB writer
│   ├── main.py
│   └── handlers/           # telemetry · state · heartbeat · command_response
├── scheduler/              # 주기 작업
│   ├── main.py
│   └── jobs/               # offline_detector · command_timeout · partition_manager
├── deploy/
│   ├── systemd/            # 3 unit (Type=notify · WatchdogSec=30)
│   └── scripts/install-server.sh
└── tests/                  # pytest + asyncio
```

## 설치 (server)

```bash
# Phase 1 인프라가 이미 떠있다고 가정
cd /path/to/repo
sudo bash server/deploy/scripts/install-server.sh

# .env 편집
sudo nano /etc/iot-platform/backend.env  # DATABASE_URL password
sudo systemctl restart iot-backend iot-worker iot-scheduler

# 검증
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/db
sudo journalctl -fu iot-backend
```

## 로컬 개발

```bash
cd server
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# DB
export DATABASE_URL="postgresql+asyncpg://iot_user:iot_pw@localhost:5432/iot_platform"
alembic upgrade head

# Backend
iot-backend  # uvicorn :8000

# Worker (별도 터미널)
iot-worker

# Scheduler (별도 터미널)
iot-scheduler

# 테스트
pytest -v
```

## Phase 2 범위 (현재)

| 영역 | 포함 | 제외 (Phase 4+) |
|---|---|---|
| **DB** | 12 테이블 + telemetry 월별 partition | gateway_configs · alarm_rules · bulk_jobs · actuator_profiles |
| **Auth** | JWT decode + DB 권한 매핑 (3축 단순화) | Keycloak JWKS RS256 verify (Phase 7) · OIDC code flow |
| **Routers** | health · companies · sites · gateways · sensor_* · actuator · commands · telemetry | OTA · Bulk · Alarm · Audit · Reports |
| **Worker** | telemetry · state · heartbeat · command_response | event 처리 · alarm rule eval · ota status |
| **Scheduler** | offline_detector · command_timeout · partition_manager | backup automation · retention drop · report generator |
| **Tests** | unit (handlers, health) + 통합 가이드 | E2E with real PostgreSQL · Keycloak · VerneMQ |

## Gateway agent와의 호환

| Topic 패턴 | 방향 | Worker handler |
|---|---|---|
| `gw/{id}/telemetry` | gw → server | `worker/handlers/telemetry.py` |
| `gw/{id}/state` | gw → server | `worker/handlers/state.py` |
| `gw/{id}/heartbeat` | gw → server | `worker/handlers/heartbeat.py` |
| `gw/{id}/command/response` | gw → server | `worker/handlers/command_response.py` |
| `gw/{id}/command/request` | server → gw | `app/mqtt_publisher.py` |
| `gw/{id}/event` · `ota/*` · `config/reported` | gw → server | log only (Phase 5+) |

JSON payload schema는 Gateway agent가 publish하는 그대로 (design doc + `04_data_flow_command.excalidraw`).

## API 빠른 reference

```
GET    /health                        no auth
GET    /health/db                     no auth

POST   /api/companies                 RBAC: any auth
GET    /api/companies
GET    /api/companies/{id}

POST   /api/sites
GET    /api/sites?company_id=...

POST   /api/gateways                  → 등록자에게 admin 권한 자동 부여
GET    /api/gateways                  → user 권한 있는 gateway만
GET    /api/gateways/{id}             permission: view
PATCH  /api/gateways/{id}             permission: configure
DELETE /api/gateways/{id}             permission: admin
GET    /api/gateways/{id}/state

POST   /api/sensor-profiles           Sensor Profile JSON Schema 검증
GET    /api/sensor-profiles
GET    /api/sensor-profiles/{id}

POST   /api/gateways/{id}/sensor-channels
GET    /api/gateways/{id}/sensor-channels
DELETE /api/sensor-channels/{id}

POST   /api/gateways/{id}/actuator-channels
GET    /api/gateways/{id}/actuator-channels
DELETE /api/actuator-channels/{id}

POST   /api/gateways/{id}/commands    permission: control · MQTT publish
GET    /api/commands/{cmd_id}

GET    /api/gateways/{id}/latest      대시보드용 (telemetry_latest)
GET    /api/gateways/{id}/telemetry?hours=24&limit=1000   시계열
```

## 다음 phase 진입 조건 (Phase 2 → Phase 3)

- [ ] Backend + Worker + Scheduler 3 service active 24시간
- [ ] Gateway agent 1대 (Pi 4 또는 CM4)에서 telemetry publish → DB 적재 확인
- [ ] Web에서 POST /api/gateways/{id}/commands → 실 릴레이 ON/OFF 확인
- [ ] 첫 customer (유기 보호소 운영자) 인터뷰 완료 (office-hours assignment)

이후 Phase 3 (Sensor Wizard + Dynamic Dashboard, React + Vite frontend).
