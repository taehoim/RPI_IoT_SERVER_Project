# Review: Server Delta (미리뷰 영역 + 회귀 검증)

> 작성일: 2026-05-04
> 범위: 미리뷰 라우터 8개 + 워커 핸들러 4개 + 스케줄러 잡 3개 + 유틸 3개 + 회귀 검증
> 형태: review only
> 발견 이슈: 🔴 1 · 🟠 3 · 🟡 5 · 🔵 2 (신규만 카운트)
> 회귀 상태: 기존 C1/C2/H1-H6 중 **6건 수정됨** / **2건 잔존**

---

## REGRESSION CHECK (vs REVIEW_PHASE1_PHASE2.md)

| 기존 ID | 항목 | 현재 상태 | 근거 |
|---|---|---|---|
| C1 | sd_notify READY/WATCHDOG 미구현 | **수정됨** | `app/utils/sd.py` 전체 신설. `main.py:45` `sd.ready()` + `:49` `asyncio.create_task(sd.watchdog_loop(10))`. worker/scheduler도 동일 패턴 구현. `pyproject.toml:24` `sdnotify>=0.3.2` 의존성 추가. |
| C2 | JWT verify 기본 OFF | **수정됨** | `config.py:39` `kc_verify_signature: bool = True`. `auth.py:57-90` JWKS RS256 verify 전체 구현(`jwks.py` 신설). dev escape는 `validate_security()` 3-조건 강제. |
| H1 | partition 날짜 하드코딩 | **수정됨** | `alembic/versions/0001_initial.py:192` `CREATE TABLE telemetry_default PARTITION OF telemetry DEFAULT;` 추가. `:196-214` 동적 날짜(`datetime.now(tz=timezone.utc)`) 기반 현재+3개월 생성. `partition_manager.py:19` `LOOKAHEAD_MONTHS=4`. |
| H2 | naive vs aware datetime 혼용 | **수정됨** | `app/utils/time.py` 신설 (`utcnow()`, `parse_iso8601()`). 핸들러 전체가 `parse_iso8601()` 사용. `telemetry.py:36`, `state.py:23`, `heartbeat.py:13`, `command_response.py:13` 모두 import. `datetime.utcnow()` 잔존 0건 확인. |
| H3 | Worker serial dispatch (back-pressure 없음) | **잔존** | `worker/main.py:40-45` 여전히 `async for msg: await dispatch(...)` 직렬 처리. `asyncio.Queue` + 복수 worker 도입 안 됨. |
| H4 | Worker/Scheduler WatchdogSec 없음 | **수정됨** | `iot-worker.service:14` `WatchdogSec=30`. `iot-scheduler.service:14` `WatchdogSec=30`. worker/scheduler 모두 `sd.watchdog_loop()` 구현 완료. |
| H5 | install-server.sh 공급망 + weak password | **부분수정** | PG password: `openssl rand -hex 24` 자동 생성(`:103`) + 권한 0600(`:102`) 수정됨. verification 단계(`:151-171`) 추가. **그러나** `curl -LsSf https://astral.sh/uv/install.sh \| sh`(`:39`) 여전히 잔존. MQTT password `CHANGE_ME_VERNEMQ_PASSWORD`(`:117`) 자동 생성 미구현. |
| H6 | get_current_user auto-upsert | **수정됨** | `auth.py:102-120` SELECT only. upsert 코드 완전 제거. 미등록 user → `HTTP 403 "user not provisioned"`. |

---

## 🔴 CRITICAL (신규)

### C-NEW-1. JWKS 캐시 — 동기 httpx.get()을 비동기 FastAPI request path에서 호출

**파일:** `server/app/utils/jwks.py:36`
```python
def _fetch(self) -> None:
    resp = httpx.get(self._url, timeout=self._timeout)  # 동기 blocking I/O
```

**파일:** `server/app/utils/jwks.py:56-63` (호출 경로)
```python
def get_key(self, kid: str) -> dict[str, Any] | None:
    with self._lock:          # threading.Lock (blocking)
        if self._is_stale() or kid not in self._keys:
            self._fetch()     # 동기 httpx.get — asyncio event loop block
```

**호출 경로:** `auth.py:65-70` `get_key(kid)` → `jwks.py:_fetch()` → `httpx.get()` (동기)

**문제:**
FastAPI는 asyncio event loop 위에서 동작한다. `get_current_user` → `get_key()` → `httpx.get()`을 실행하는 순간 **event loop 전체가 최대 `kc_jwks_fetch_timeout_sec=5초` 동안 block**된다.
- TTL 1시간 주기 갱신 시 정상 트래픽 중 5초 hang → 모든 동시 요청 대기
- VerneMQ 서비스에서 수백 메시지가 queue에 쌓임
- 더 심각하게는 테스트에서 `KC_VERIFY_SIGNATURE=false`로만 실행하므로 이 코드가 CI에서 전혀 실행되지 않아 **production 첫 배포 때 silent event loop block**이 발생

추가로 `threading.Lock`을 asyncio context에서 사용하면 await 없는 lock acquire가 동기 실행되므로 다른 coroutine이 lock release를 기다리며 starve한다.

**해결안:**
```python
# jwks.py — 비동기 전환
import asyncio
import httpx

class JWKSCache:
    def __init__(self, ...):
        self._lock = asyncio.Lock()   # threading.Lock → asyncio.Lock

    async def _fetch(self) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.get(self._url, timeout=self._timeout)
            ...

    async def get_key(self, kid: str) -> dict[str, Any] | None:
        async with self._lock:
            if self._is_stale() or kid not in self._keys:
                await self._fetch()
            return self._keys.get(kid)

# auth.py — await 추가
public_key = await cache.get_key(kid)
```

**영향:** KC_VERIFY_SIGNATURE=True(production default)로 운영하는 모든 환경에서 JWKS TTL 만료 시 최대 5초 event loop hang. 부하가 있으면 전체 API 응답 없음.

---

## 🟠 HIGH (신규)

### H-NEW-1. companies.py / sites.py — 역할 기반 권한 검사 완전 부재

**파일:** `server/app/routers/companies.py:20-51`, `server/app/routers/sites.py:20-43`

```python
# companies.py:20-30
@router.post("", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
async def create_company(
    body: CompanyIn,
    session: ...,
    _user: Annotated[User, Depends(get_current_user)],  # 인증만, 인가 없음
) -> Company:
    company = Company(id=uuid.uuid4(), **body.model_dump())
    session.add(company)  # 모든 인증된 user가 company 생성 가능
```

```python
# companies.py:33-39
@router.get("", response_model=list[CompanyOut])
async def list_companies(...) -> list[Company]:
    res = await session.execute(select(Company).order_by(Company.created_at))
    return list(res.scalars())  # 모든 company 전체 반환 — 테넌트 격리 없음
```

**문제 세 가지:**

1. **수직 권한 부재**: `create_company`, `list_companies`, `get_company` 모두 인증된 user라면 누구나 호출 가능. `system_admin` 역할 확인 없음. 일반 고객 user가 다른 회사를 신규 생성할 수 있음.

2. **수평 격리(테넌트 분리) 부재**: `list_companies`가 `SELECT * FROM companies` 수준으로 전체 반환. 고객 A의 담당자가 고객 B의 회사 정보를 볼 수 있음. `user_company_roles` 테이블이 있는데 join 없이 전체 조회.

3. **sites.py도 동일**: `list_sites`는 `company_id` 쿼리 파라미터가 **optional**이어서 파라미터 미전달 시 전체 site 반환.

**해결안:**
```python
# companies.py — 관리자 전용 create + 본인 company_roles 기반 list
async def create_company(..., token: TokenPayload = Depends(get_token)):
    if not token.has_role("system_admin"):
        raise HTTPException(403, "system_admin role required")
    ...

async def list_companies(...):
    # user_company_roles join으로 본인 소속 company만 반환
    stmt = (
        select(Company)
        .join(UserCompanyRole, UserCompanyRole.company_id == Company.id)
        .where(UserCompanyRole.user_id == user.id)
    )
```

---

### H-NEW-2. sensor_profiles.py — profile_schema 글로벌 뮤터블 캐시 + RuntimeError 전파

**파일:** `server/app/routers/sensor_profiles.py:24-33`

```python
_PROFILE_SCHEMA: dict | None = None  # 글로벌 뮤터블 상태

def _schema() -> dict:
    global _PROFILE_SCHEMA
    if _PROFILE_SCHEMA is None:
        if not _SCHEMA_PATH.exists():
            raise RuntimeError(f"Sensor Profile schema not found: {_SCHEMA_PATH}")
        _PROFILE_SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return _PROFILE_SCHEMA
```

**문제 두 가지:**

1. `RuntimeError`가 FastAPI request handler 내에서 unhandled 예외로 전파 → `HTTP 500 Internal Server Error` 응답. 단, FastAPI 기본 exception handler가 stack trace를 숨기므로 보안 누출은 아님. 그러나 `500`이 아닌 명시적 `503 Service Unavailable`과 적절한 메시지가 더 운영 친화적.

2. `_PROFILE_SCHEMA`가 모듈 수준 글로벌 변수로 초기화 후 영구 캐시됨. schema 파일이 배포 중 변경되면 재시작 없이 반영 불가 (이건 의도적일 수 있으나 명시 주석 없음). `pytest`에서 모듈을 재로드하지 않으면 다른 테스트가 캐시된 값을 공유.

**해결안:**
```python
def _schema() -> dict:
    global _PROFILE_SCHEMA
    if _PROFILE_SCHEMA is None:
        if not _SCHEMA_PATH.exists():
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                f"sensor profile schema not installed at {_SCHEMA_PATH}",
            )
        _PROFILE_SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return _PROFILE_SCHEMA
```

---

### H-NEW-3. command_response.py — status 필드 미검증 → 임의 값 DB 저장

**파일:** `server/worker/handlers/command_response.py:44`

```python
cmd.status = body.get("status", "executed")  # gateway가 전달한 값 그대로 저장
```

**문제:** MQTT는 인증 없이(혹은 탈취된 계정으로) 메시지를 발행할 수 있다. 악의적 payload가 `"status": "pending"` 또는 `"status": "whatever_i_want"` 를 보내면 DB에 그대로 저장된다.

- `"pending"` 재저장 → 이미 executed인 command가 다시 timeout 대상이 됨 (command_timeout job과 충돌)
- `Command.status`에 DB 레벨 CHECK constraint가 없으므로(M4 미수정) DB에도 저장됨
- `models.py:301` 주석에 허용 값이 명시되어 있으나 코드에서 검증 없음

**해결안:**
```python
VALID_RESPONSE_STATUSES = frozenset({"executed", "rejected", "failed"})

raw_status = body.get("status", "executed")
if raw_status not in VALID_RESPONSE_STATUSES:
    log.warning("invalid command response status", status=raw_status, command_id=cmd_id)
    raw_status = "failed"
cmd.status = raw_status
```

---

## 🟡 MEDIUM (신규)

### M-NEW-1. telemetry.py router — 페이지네이션 없는 list 형 API + limit 우회 가능

**파일:** `server/app/routers/telemetry.py:47-48, 61`

```python
limit: Annotated[int, Query(ge=1, le=10000)] = 1000,
...
.limit(limit)
```

`limit=10000`이 허용된다. gateway 수십 대 × 수십 측정값 × 30일 조회 시 10,000건 row를 한 번에 직렬화하여 반환. 각 row에 JSON 필드가 있으므로 응답 크기가 100MB 이상이 될 수 있다. `/gateways/{gateway_id}/latest`는 `limit` 파라미터 자체가 없어 gateway당 채널이 많으면 unbounded 반환.

**해결안:**
- `limit` 상한을 `le=1000` 또는 `le=5000` 수준으로 내리거나
- cursor 기반 페이지네이션 (`last_ts` 파라미터 + `LIMIT`) 도입
- `latest` endpoint도 `limit` 파라미터 추가

---

### M-NEW-2. companies/sites — missing pagination (list endpoint)

**파일:** `server/app/routers/companies.py:33-39`, `server/app/routers/sites.py:33-43`

```python
res = await session.execute(select(Company).order_by(Company.created_at))
return list(res.scalars())  # 전체 반환, limit 없음
```

company와 site가 수백 건 이상 되면 전체를 메모리에 올려 직렬화한다. `limit`/`offset` 쿼리 파라미터 없음.

---

### M-NEW-3. worker/main.py — dispatch 예외 삼킴 시 메시지 손실 무음

**파일:** `server/worker/main.py:44-45`

```python
except Exception as exc:  # noqa: BLE001 — handler 자체에서 swallow하면 손실
    log.error("dispatch failed", topic=msg.topic.value, error=str(exc))
```

오류 로그는 남기지만 MQTT QoS=1이어도 **재처리(retry)가 전혀 없다**. 브로커는 `PUBACK`을 받았으므로 메시지를 재전송하지 않는다. DB 일시 장애 또는 커넥션 풀 고갈 시 telemetry 메시지가 영구 손실된다.

최소 보호 방안:
- Dead letter queue (별도 테이블 또는 파일) 기록
- 또는 `asyncio.Queue` 도입(H3 해결)으로 backlog 유지 후 재시도

---

### M-NEW-4. conftest.py — KC_VERIFY_SIGNATURE=false 하드코딩, 인증 경로 테스트 전무

**파일:** `server/tests/conftest.py:13`

```python
os.environ.setdefault("KC_VERIFY_SIGNATURE", "false")
```

모든 테스트가 signature 검증 비활성화 상태로 실행된다. C-NEW-1에서 지적한 JWKS 동기 블로킹 경로가 테스트에서 실행되지 않는다. production path(`kc_verify_signature=True`)를 커버하는 테스트가 없어 C-NEW-1 같은 버그가 CI에서 완전히 드러나지 않는다.

최소 추가 사항:
- JWKS mock + `KC_VERIFY_SIGNATURE=true` 상태로 `get_current_user` 호출 성공/실패 테스트
- `jwks.reset_cache_for_tests()` fixture 활용

---

### M-NEW-5. scheduler/_tick — 장기 실행 job이 interval을 초과해도 다음 tick이 즉시 발화

**파일:** `server/scheduler/main.py:22-33`

```python
async def _tick(name: str, interval_sec: int, fn) -> None:
    while True:
        try:
            async with Session() as session:
                await fn(session)
        except ...
        await asyncio.sleep(interval_sec)  # job 완료 후 고정 sleep
```

`offline_detector`가 예를 들어 35초 걸리면 다음 tick은 35+30=65초 후. 이건 허용 범위다.

반대로 `command_timeout`(interval=10초) 실행 중 DB 연결 지연으로 15초 걸리면 job 완료 직후 10초 sleep → 25초 주기로 실행. 이건 의도된 동작이나 기록이 없다. 더 중요한 문제는 **`offline_detector`(interval=30초)가 DB full-table UPDATE(수십 대 gateway)를 30초마다 실행하는데 index가 `last_seen_at` 단독으로 없다**는 점이다.

`gateways` 테이블에는 `ix_gateways_company`, `ix_gateways_site` index는 있지만 `offline_detector.py`의 WHERE 조건(`status='online' AND last_seen_at < threshold`)을 커버하는 복합 index가 없다.

**해결안:** `alembic`에 `ix_gateways_status_last_seen` 추가:
```sql
CREATE INDEX ix_gateways_status_last_seen ON gateways (status, last_seen_at)
WHERE status = 'online';
```

---

## 🔵 BETTER ALTERNATIVES

### B-NEW-1. jwks.py — 캐시 갱신 실패 시 stale key 계속 사용 (grace period)

**파일:** `server/app/utils/jwks.py:59-62`

```python
try:
    self._fetch()
except Exception:  # noqa: BLE001 — caller가 401로 처리
    return None
```

JWKS fetch 실패 시 `None` 반환 → 모든 요청 401. Keycloak이 일시적으로 5초 응답 없어도 전체 API가 인증 불가 상태가 된다. 업계 표준은 fetch 실패 시 **이전 캐시 유지**(stale-on-error):

```python
# 수정안
if self._is_stale() or kid not in self._keys:
    try:
        await self._fetch()
    except Exception:
        log.warning("JWKS refresh failed, using stale cache", url=self._url)
        # 기존 키로 계속 서비스 (TTL 만료여도 stale 허용)
        pass
return self._keys.get(kid)
```

---

### B-NEW-2. commands.py — MQTT publish 실패 시 status=pending으로 두되 503 반환 — 클라이언트가 혼란

**파일:** `server/app/routers/commands.py:77-88`

```python
except Exception as exc:
    # publish 실패해도 status=pending로 둠 → scheduler가 timeout 처리
    raise HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        f"mqtt publish failed: {exc}",   # exc 문자열 노출
    ) from exc
```

두 가지 개선 포인트:

1. `exc` 전체를 HTTP response body에 노출하면 내부 MQTT broker 주소, 포트, 오류 메시지가 클라이언트에 보인다. `"command accepted but not yet delivered — retry or check status endpoint"` 수준의 generic 메시지로 교체.

2. 실제로 DB record(status=pending)는 생성됐으므로 `503`이 아니라 `202 Accepted`를 반환하면서 응답 body에 `"delivery": "pending"` 표시가 더 REST semantics에 맞다.

---

## H5 잔존 항목 상세

### H5 (잔존 부분) — curl | sh + MQTT password 자동 생성 미완

**파일:** `server/deploy/scripts/install-server.sh:38-40`

```bash
if ! command -v uv >/dev/null 2>&1; then
    echo "==> Installing uv"
    curl -LsSf https://astral.sh/uv/install.sh | sh
```

PG password 자동 생성은 수정되었으나 위 공급망 문제는 그대로다.

**파일:** `server/deploy/scripts/install-server.sh:117`

```bash
MQTT_PASSWORD=CHANGE_ME_VERNEMQ_PASSWORD
```

MQTT password는 여전히 `CHANGE_ME` 플레이스홀더. 운영자가 변경하지 않으면 VerneMQ가 anonymous 접속을 허용하거나(설정에 따라) backend가 연결 실패한다.

**해결안:**
```bash
# uv 설치: SHA256 핀
UV_VERSION="0.4.30"
UV_SHA256="<checksum>"
curl -LsSf "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-installer.sh" -o /tmp/uv-install.sh
echo "${UV_SHA256}  /tmp/uv-install.sh" | sha256sum -c
sh /tmp/uv-install.sh

# MQTT password 자동 생성
MQTT_PASS=$(openssl rand -hex 16)
echo "MQTT_PASSWORD=${MQTT_PASS}" >> "$ETC_DIR/$env"
echo "    VerneMQ에 iot-backend 계정 등록:"
echo "    sudo vmq-passwd /etc/vernemq/vmq.passwd iot-backend <<< '${MQTT_PASS}'"
```

---

## 권장 수정 우선순위 (회귀 + 신규 통합)

| 순위 | 항목 | 출처 | 예상 시간 |
|---|---|---|---|
| 1 | C-NEW-1: JWKS 동기 httpx → asyncio.Lock + httpx.AsyncClient | 신규 CRITICAL | 1시간 |
| 2 | H-NEW-1: companies/sites 권한 + 테넌트 격리 | 신규 HIGH | 2시간 |
| 3 | H-NEW-3: command_response status 필드 검증 | 신규 HIGH | 30분 |
| 4 | H3 (잔존): Worker asyncio.Queue + N workers | 회귀 잔존 | 2시간 |
| 5 | H-NEW-2: _schema() RuntimeError → HTTPException | 신규 HIGH | 15분 |
| 6 | H5 (잔존 부분): curl\|sh uv 핀 + MQTT password 자동 생성 | 회귀 부분잔존 | 45분 |
| 7 | M-NEW-1/2: 페이지네이션 limit 상한 조정 | 신규 MEDIUM | 30분 |
| 8 | M-NEW-3: worker dispatch 실패 DLQ/retry | 신규 MEDIUM | 1시간 |
| 9 | M-NEW-4: KC_VERIFY_SIGNATURE=true 테스트 경로 추가 | 신규 MEDIUM | 1시간 |
| 10 | M-NEW-5: gateways 복합 index 추가 alembic | 신규 MEDIUM | 20분 |
| 11 | B-NEW-1: JWKS stale-on-error grace period | 개선 | 30분 |
| 12 | B-NEW-2: commands.py 503 body sanitize + 202 semantics | 개선 | 30분 |

**합계:** 약 10-11시간 — 1 sprint day (solo + AI pair)

---

## Conclusion

회귀 검증 결과, 이전 리뷰에서 지적된 6건(C1, C2, H1, H2, H4, H6)이 성실하게 수정되었다. `sd.py`, `jwks.py`, `time.py` 세 유틸리티가 신설되어 systemd notify, JWKS RS256 검증, UTC-aware datetime이 모두 실제 코드로 구현된 점은 상당한 진전이다. 특히 partition_manager가 DEFAULT partition + N+3 look-ahead로 강화된 것과, auth.py의 auto-upsert 제거 + SELECT-only 전환은 핵심 설계 의도를 명확히 따른 수정이다.

그러나 신규 발견 중 **C-NEW-1(동기 JWKS fetch)이 가장 위험**하다. `kc_verify_signature=True`가 production default이므로 JWKS TTL(1시간)마다 전체 API가 최대 5초 block되는 문제가 첫 번째 운영 피크 타임에 드러날 것이다. 더 나쁜 것은 테스트 전체가 `KC_VERIFY_SIGNATURE=false`로 실행되므로 이 경로가 CI에서 전혀 검증되지 않는다는 점이다. C-NEW-1 수정 시 반드시 `KC_VERIFY_SIGNATURE=true` 통합 테스트를 같이 작성해야 한다.

**H-NEW-1(companies/sites 권한 부재)**도 멀티-테넌트 운영 시 즉시 문제가 된다. 다른 회사의 고객 담당자가 전체 company 목록을 볼 수 있고, `system_admin` 확인 없이 company를 생성할 수 있다. `_check_perm`은 gateway 레벨에 잘 적용되어 있지만 최상위 테넌트 레이어에는 적용되지 않아 권한 모델의 구멍이 생겼다. H3(worker serial dispatch) 또한 잔존하는데, 100대 gateway 환경에서 DB 부하 시 telemetry 적체가 불가피하므로 다음 sprint 안에 `asyncio.Queue` + batch INSERT로 전환을 권장한다.
