# Review: Phase 1 인프라 + Phase 2 Server 구현

> 작성일: 2026-05-04
> 범위: Phase 1 인프라 결정 + Phase 2 server (47 파일, 2,533 Python 라인)
> 형태: review only — 구현 0줄, 의사결정 자료
> 발견 이슈: **🔴 Critical 2 · 🟠 High 6 · 🟡 Medium 7 · 🔵 Better Alternatives 5**

---

## 🔴 CRITICAL — 배포 전 반드시 수정

### C1. systemd Type=notify + WatchdogSec=30 인데 코드가 sd_notify 호출 안 함

**파일:** `server/deploy/systemd/iot-backend.service` + `server/app/main.py`
**증상:** Backend 기동 후 30초 → systemd가 hang으로 판정 → SIGABRT → 재시작 → 무한 루프
**근거:**
```
deploy/systemd/iot-backend.service:
  Type=notify
  WatchdogSec=30
```
하지만 코드 검색 결과 `sd_notify` / `SdNotify` 호출 위치 0건. uvicorn은 기본적으로 sd_notify를 자동 호출하지 않음.

**영향:** 부팅 후 30초마다 재시작. service 영원히 active 안됨. Phase 2 server 절대 운영 불가.

**해결안 (선택):**
- (A) `Type=notify` → `Type=simple` 변경 + `WatchdogSec` 제거 (단순화, watchdog 포기)
- (B) uvicorn workers를 dropping in `lifespan` start에서 `from systemd.daemon import notify; notify('READY=1')` + 별도 task가 매 10초 `notify('WATCHDOG=1')` 호출
- (C) `python-systemd` 패키지 추가 + `app/main.py`에서 lifespan startup 직후 READY 발행

**권장:** (B). `python-systemd` (Python 측 sd_notify) 설치 + main.py lifespan에서 READY + asyncio task로 WATCHDOG 매 10초.

---

### C2. JWT signature verify 기본 OFF — 누구나 token 위조 가능

**파일:** `server/app/auth.py` + `server/app/config.py`
**증상:** `KC_VERIFY_SIGNATURE=false` 기본값 → JWT signature 검증 안 함 → 임의 sub claim으로 superuser 행세 가능
**근거:**
```python
# app/config.py:39
kc_verify_signature: bool = False  # Phase 2: skip until JWKS wiring; Phase 7: True

# app/auth.py:40
options = {"verify_signature": settings.kc_verify_signature}
return jwt.decode(token, key="", options=options, ...)
```

**영향:** 외부에 노출된 순간 모든 API endpoint를 임의 user로 호출 가능. Gateway 등록·삭제·command publish 무제한. DB 권한 매핑도 attacker가 만든 user record 기반.

**왜 위험:**
- "Phase 2는 dev only" 라고 가정했으나, dev server가 LAN에 노출되면 즉시 탈취
- Phase 2 → Phase 7로 toggle 잊고 production 배포 시 silent fail

**해결안:**
1. **즉시:** `kc_verify_signature: bool = True` 로 default 변경 + JWKS fetch 구현
2. **환경 분리:** `kc_verify_signature=False` 는 `app_env=="dev"` AND `kc_issuer` 가 localhost 일 때만 허용 (config validator)
3. **fail-safe banner:** signature off 모드로 기동 시 경고 로그 + `/health` response에 `"warning": "auth disabled"` 노출

**권장:** 1+2+3 모두. Phase 2 단계라도 verify 켜고 JWKS fetch 구현 우선.

---

## 🟠 HIGH — 운영 안정성 위협

### H1. Telemetry partition 날짜 하드코딩 — 2027년 install 시 INSERT 실패

**파일:** `server/alembic/versions/0001_initial.py:194-196`
**증상:**
```sql
CREATE TABLE telemetry_2026_05 PARTITION OF telemetry FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE telemetry_2026_06 PARTITION OF telemetry FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
```
**문제:** 2026-07-01 이후 telemetry INSERT 시 `no partition of relation "telemetry" found for row` 에러. partition_manager가 다음 달만 미리 생성하므로 2026-07 partition은 6시간 내 생성되지만, **alembic upgrade 직후 첫 telemetry는 partition 없음**.

**해결안:**
- (A) initial migration에서 dynamic 날짜 — `now()` 기반 현재월 + 다음월 N개 ahead 생성
- (B) DEFAULT partition 추가: `CREATE TABLE telemetry_default PARTITION OF telemetry DEFAULT;` (PostgreSQL 11+)
- (C) pg_partman 도입 (Phase 6+ 검토)

**권장:** (B) + scheduler가 N+1, N+2 생성. DEFAULT partition은 안전망.

---

### H2. Mixed naive vs timezone-aware datetime — 비교 오류 발생

**파일:** 여러 위치 (worker/handlers/{telemetry,state,heartbeat,command_response}.py + app/routers/gateways.py)
**증상:** 같은 코드베이스에서 `datetime.utcnow()` (naive) 와 `datetime.now(tz=timezone.utc)` (aware) 혼용. PostgreSQL TIMESTAMPTZ 컬럼 비교/저장 시 silent timezone shift 가능.

**근거:**
```python
# worker/handlers/telemetry.py:33
return datetime.utcnow()                       # naive
# scheduler/jobs/offline_detector.py:19
threshold = datetime.now(tz=timezone.utc) - ...  # aware
# worker/handlers/state.py:49
gw.last_seen_at = datetime.utcnow()             # naive 저장
```

**문제:**
- `last_seen_at` 컬럼이 TIMESTAMPTZ인데 naive datetime 저장 시 PostgreSQL은 server local time 가정 → KST면 9시간 shift
- offline_detector가 aware threshold와 비교 → naive vs aware 비교는 TypeError 또는 silent UTC 가정

**해결안:**
- 프로젝트 전역 정책: `datetime.now(tz=timezone.utc)` 만 사용
- helper `app/utils/time.py::now()` 제공 + ruff rule로 `datetime.utcnow` 금지
- 모든 `_parse_ts` fallback 도 aware

---

### H3. Worker 단일 subscriber + serial dispatch — back-pressure 없음

**파일:** `server/worker/main.py`
**증상:**
```python
async for msg in client.messages:
    async with Session() as session:
        await dispatch(session, msg.topic.value, msg.payload)
```
한 메시지 처리가 느리면 (예: DB lock, slow query) 모든 후속 메시지 대기. 100대 gateway × 10초 polling = 600 msg/min. DB INSERT 1건이 100ms면 6초 내내 dispatch만, telemetry 큐 적체.

**해결안:**
- (A) `asyncio.create_task(dispatch(...))` 로 fan-out (단, DB session pool 한계 도달 위험)
- (B) `asyncio.Queue` 도입 + N개 worker coroutine (배치 INSERT 가능)
- (C) `arq`/`dramatiq` 도입 (production grade, redis 의존)

**권장:** (B). bounded queue (maxsize=1000) + 4-8개 worker coroutine + batch INSERT 기능.

---

### H4. Worker/Scheduler systemd unit에 WatchdogSec 없음 — hang 시 자동 복구 ❌

**파일:** `server/deploy/systemd/iot-worker.service` + `iot-scheduler.service`
**증상:** Worker가 deadlock (예: aiomqtt 내부 future hang) 또는 scheduler tick 영구 정지 시 systemd가 감지 못함. Restart=always는 process 죽었을 때만 작동.

**해결안:**
- Worker/Scheduler도 sd_notify 패턴 적용 + WatchdogSec=60
- 또는 main.py에 self-watchdog (각 N초마다 `last_alive` timestamp 갱신, scheduler tick이 X초 지연되면 SIGTERM self)

---

### H5. install-server.sh — `curl | sh` 공급망 + 약한 password 템플릿

**파일:** `server/deploy/scripts/install-server.sh:30-32`
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
**문제:** astral.sh가 탈취되면 root 권한 임의 코드 실행. 또한:
```bash
DATABASE_URL=postgresql+asyncpg://iot_user:CHANGE_ME@127.0.0.1:5432/iot_platform
```
사용자가 CHANGE_ME 잊고 systemctl start하면 weak password로 운영. 그리고 alembic 단계에서 `source ... && DATABASE_URL=$DATABASE_URL alembic` 패턴은 환경변수가 ps 에서 노출될 수 있음.

**해결안:**
- uv 설치: GitHub release tarball + SHA256 검증 또는 apt에 등록되면 apt로
- `CHANGE_ME` → install 시 `openssl rand -hex 16` 으로 자동 생성 + .env 권한 0600
- alembic 호출: `env DATABASE_URL=...` 으로 명시적 단일 명령 (source 안 함)
- 끝에 verification step 추가: `curl -fsSL http://127.0.0.1:8000/health || exit 1` + 3 service `systemctl is-active`

---

### H6. get_current_user — read endpoint마다 upsert side-effect

**파일:** `server/app/auth.py:62-83`
**증상:** 모든 API call이 user upsert 시도. JWT가 valid format이면 (signature off일 때) 임의 sub로 user record 무한 생성 가능 → DB pollution.

**해결안:**
- get_current_user는 SELECT만 → 없으면 401 ("user not provisioned, contact admin")
- 별도 admin-only `POST /api/users` endpoint로 명시 user 생성
- 또는 Keycloak event hook으로 사용자 생성 시 자동 user row insert

---

## 🟡 MEDIUM — 개선 권장

### M1. MQTT publisher 모듈 글로벌 상태 (`_client`) — uvicorn workers > 1 환경 깨짐

**파일:** `server/app/mqtt_publisher.py`
현재 `workers=1` 강제하지만, 환경변수로 변경되거나 gunicorn 도입 시 여러 worker가 같은 client_id로 connect → broker가 같은 ID 재접속 시 이전 연결 끊음 → 무한 reconnect 폭주.

**해결:** worker process마다 unique client_id (hostname + pid) 또는 backend는 단일 worker 강제 명시 (`SystemdLimitProcess=1` 비슷한 가드).

### M2. `aiomqtt.Client.__aenter__/__aexit__` 직접 호출 — anti-pattern

**파일:** `server/app/mqtt_publisher.py:36, 42`
context manager protocol을 수동 호출하면 예외 안전성 약함. async with 내에서 사용하거나 `AsyncExitStack` 사용 권장.

### M3. Telemetry handler — float 외 타입 silent drop

**파일:** `server/worker/handlers/telemetry.py:50-51`
```python
value_double = float(value) if isinstance(value, (int, float)) else None
```
relay_state ("on"/"off"), gps ({"lat":..., "lon":...}) 같은 비-float 타입은 value_double=None로 저장 → 사용자에게는 "값 없음"으로 보임. value_text/value_json 분기 추가 필요.

### M4. 모델 누락 제약조건

**파일:** `server/app/models.py`
- `Company.company_type` — CHECK constraint 없음 (literal 'management'|'customer')
- `Gateway.status` — CHECK ('online'|'offline'|'shutdown'|'unknown')
- `Command.status` — CHECK ('pending'|'published'|'executed'|'rejected'|'failed'|'timeout')
- `UserGatewayPermission.permission` — CHECK ('view'|'control'|'configure'|'maintain'|'admin')
- `SensorChannel` — UNIQUE(gateway_id, interface_name, slave_id) 누락 → 같은 슬레이브에 두 채널 등록 가능

DB 레벨 안전망 추가하면 application bug로 잘못된 값 저장 방지.

### M5. `_check_perm` — admin role 우회 로직 미구현

**파일:** `server/app/routers/gateways.py:23-39`
```python
# TODO: token.has_role("system_admin") 우회 로직 추가
```
주석만 있고 미구현. 관리자가 권한 명시 부여 안 한 Gateway는 조회 불가 → 운영 시 첫 system_admin이 본인 권한 grant 못함 (chicken-and-egg).

**해결:** Token에서 `system_admin` role 추출 → 권한 체크 우회. JWT decode 시점에 추가.

### M6. partition_manager — N+1만 생성, N+2 누락

**파일:** `server/scheduler/jobs/partition_manager.py`
6시간 주기로 다음 달 1개만 생성. scheduler가 6시간 이상 down → 다음 달 partition 없는 채로 telemetry 도착 → INSERT fail. **N+1, N+2, N+3 ahead 생성**으로 안전 마진 확보.

### M7. command_timeout job — race condition

**파일:** `server/scheduler/jobs/command_timeout.py`
status가 pending/published인 command를 timeout으로 변경. **그러나 거의 동시에 gateway가 response 발행하면**:
- Worker: status='executed' UPDATE
- Scheduler: status='timeout' UPDATE
순서 따라 잘못된 status 영구 저장. SELECT FOR UPDATE 또는 condition column (`WHERE status IN (...) AND completed_at IS NULL`) 필요.

---

## 🔵 BETTER ALTERNATIVES — 다음 phase에 검토

### B1. Sensor Profile JSON Schema → 코드 자동 생성 (server/gateway 양쪽)

현재: server는 `jsonschema.validate()`만, gateway는 Profile JSON 수동 파싱.
권장: `datamodel-code-generator` (Python pydantic 모델 생성) + `quicktype` (Go struct 생성). CI로 schema → 코드 자동 생성. `shared/sensor_profile_schema.json` 변경 시 PR에 두 코드 생성 결과 동시 반영.

### B2. APScheduler 또는 Temporal 도입 (Phase 5+)

현재 in-process asyncio tick은 단일 인스턴스 가정. 서버 이중화 시 모든 인스턴스가 같은 job 실행 → 중복. APScheduler + redis lock 또는 Temporal로 분산 안전성 확보.

### B3. Worker = aiomqtt + asyncio.Queue + N workers

위 H3 해결안 (B). 추가로 batch INSERT (예: 100건 모아 한 번에) 적용 시 telemetry write throughput 5-10×.

### B4. SQLAlchemy 2.0 `Annotated` mapped_column 활용

현재 모델은 SQLAlchemy 1.x 스타일에 가까움. 2.0의 `Annotated[uuid.UUID, mapped_column(...)]` 패턴으로 30% 코드 감소 + 타입 추론 개선 가능.

### B5. Backend = Litestar 검토 (Phase 5+)

FastAPI 대비 Litestar는 더 빠른 routing + 더 강한 dependency injection + 내장 OpenAPI 문서. Phase 5 양산 단계에서 마이그레이션 검토 가치.

---

## Phase 1 인프라 ↔ Phase 2 Server 정합성 점검

### I1. mosquitto vs VerneMQ 불일치 가능성

Gateway agent (Phase 0)는 로컬 `mosquitto :1883`에 연결 가정.
Phase 1 server는 `vernemq :1883` 가정.
**Gateway가 server VerneMQ에 직접 연결하는 시나리오:** Phase 0 dev mode (Pi 4 자체 mosquitto)와 Phase 1+ (server VerneMQ로 직접) 사이에 명시적 마이그레이션 단계 필요.

**해결:** Gateway config의 mqtt.broker URL만 변경하면 동작하도록 코드는 이미 구성됨. 단, **Phase 1 server install 절차서에 "Gateway config의 mqtt.broker를 server IP로 변경" 명시** 필요.

### I2. VerneMQ password file vs Backend MQTT user

Phase 1 결정: VerneMQ password file 인증 (gateway/admin 계정).
Phase 2 Backend는 `mqtt_username=None` default로 anonymous connect 시도 → VerneMQ가 anonymous 거부 시 publish 실패.

**해결:** install-server.sh에서 `iot-backend` 전용 MQTT user 생성 + backend.env의 MQTT_USERNAME/PASSWORD 자동 설정. 또는 mosquitto.conf/vernemq.conf에 backend 계정 명시.

### I3. Keycloak realm — Phase 2 Backend가 사용할 client 미생성

Phase 1 Keycloak 설정: realm + 7 role + test user 1명. **클라이언트(client_id)는 안 만듦.**
Phase 2 Backend는 `kc_audience: str = "iot-platform"` 가정. realm에 audience 매칭 client (예: "iot-backend") 필요.

**해결:** install-server.sh에서 Keycloak admin API로 client 자동 생성 (kc.sh CLI 스크립팅) 또는 절차서에 수동 단계 추가.

### I4. Nginx /api proxy 대상 — 동일 호스트 가정

Phase 1 nginx 설정은 `/api → 127.0.0.1:8000` 가정. Phase 2 Backend도 같은 호스트 binding. **OK.**
단, 이중화 시 (LB 뒤 backend N대) 변경 필요. Phase 7 검토 항목.

### I5. /etc/iot-platform/ 환경변수 owner

Phase 1: `chown root:iot $ETC_DIR/*.env, chmod 640`.
Phase 2 install-server.sh: 같은 패턴 사용. **일관성 OK.**
단, secrets (DATABASE_URL password, MQTT password)는 systemd-creds 또는 Vault 같은 secret manager로 마이그레이션 검토 (Phase 7).

---

## 권장 수정 우선순위

| 순위 | 항목 | 예상 시간 |
|---|---|---|
| 1 | C1 sd_notify READY/WATCHDOG 구현 | 30분 (python-systemd 추가 + main.py 패치) |
| 2 | C2 JWT verify default ON + JWKS fetch | 2-3시간 (httpx로 JWKS 가져와 캐시 + python-jose verify) |
| 3 | H1 partition DEFAULT + N+2 ahead | 30분 (alembic 수정 + scheduler 보강) |
| 4 | H2 datetime aware 통일 + ruff rule | 1시간 (replace + helper) |
| 5 | I3 Keycloak client 자동 생성 | 1시간 (install-server.sh kc.sh CLI) |
| 6 | I2 backend MQTT user 자동 생성 | 30분 (vmq_passwd-add) |
| 7 | H3 Worker queue + N workers | 2시간 (asyncio.Queue + batch INSERT) |
| 8 | H6 get_current_user upsert 제거 | 30분 (admin endpoint 신설) |
| 9 | H4 Worker/Scheduler watchdog | 30분 (간단한 self-watchdog) |
| 10 | H5 install-server.sh 보강 | 1시간 (verification + uv 핀 + password gen) |
| 11 | M1-M7 (모음) | 3-4시간 |

**합계:** 약 14-17시간 → solo + AI pair로 2-3 sprint day.

---

## Conclusion (Risk-Adjusted)

**현 상태 평가:** Code is **structurally sound but operationally not yet deployable**.

- ✅ 아키텍처 결정 (FastAPI + asyncio + alembic + aiomqtt + systemd) 일관성 우수
- ✅ Gateway agent ↔ Server wire schema 호환 (telemetry/state/heartbeat/command 라운드트립)
- ✅ DB 모델 12 테이블 + partition + index 핵심 잘 잡힘
- ❌ **C1 (systemd watchdog) 미해결 시 backend 1초도 안정 운영 불가**
- ❌ **C2 (JWT verify off) 미해결 시 보안 0**
- 🟠 H1-H6 미해결 시 운영 첫 1주일 내 incident 다발 (timezone bug, partition 부재, queue 폭주, hang 미감지)

**권장 next action:** C1, C2, H1, H2 4개를 single sprint (반나절)로 fix → "minimal deployable initial version" 달성. M/B 항목은 Phase 3-7로 자연 분배.

**좋은 신호:**
- 모든 issue가 검색 + ast.parse + 코드 grep 으로 즉시 detect 가능 → static review로 잡힌 것
- 디자인 doc 엄격 추적 (gw/{id}/* topic, 7 systemd unit, 3축 권한) — 추상화 일관
- Test scaffold 존재 (149 라인) — fix 검증 가능
- Phase 별 deferral 명시 (Phase 5+ OTA, Phase 6+ RLS, Phase 7 X.509) — 합리적

**걱정 신호:**
- TODO 주석이 안전 critical 영역에 남음 (M5 system_admin 우회)
- "Phase 2 dev only" 방어선이 안전 default를 OFF로 두는 패턴 — config-driven 안전성은 인간 실수에 취약
