"""Dashboard endpoint tests — uses in-memory SQLite + ASGI transport."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient


async def _setup_db_and_seed(gateway_id: uuid.UUID, with_telemetry: bool = True):
    """Create tables, insert a company + gateway + 1 sensor channel + 1 telemetry_latest row.

    Also inserts a User matching the sub claim used by `_bearer_headers()` so that
    `get_current_user` resolves successfully.

    Returns the (company_id, sensor_channel_id) for assertions.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from app import db as _db
    from app.models import (
        ActuatorChannel,
        Base,
        Company,
        Gateway,
        SensorChannel,
        SensorProfile,
        TelemetryLatest,
        User,
    )

    # Build a SQLite-compatible engine and inject it as the module-level
    # singleton. We use StaticPool with a shared in-memory DB so that the
    # engine's connections all see the same schema across calls.
    if _db._engine is not None:
        await _db._engine.dispose()
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _db._engine = engine
    _db._sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = _db._sessionmaker
    company_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    sensor_ch_id = uuid.uuid4()

    async with Session() as s:
        s.add(Company(id=company_id, name="Test Co", company_type="management"))
        s.add(
            User(
                id=uuid.uuid4(),
                keycloak_user_id="test-user",
                email="test@local",
                name="T",
            )
        )
        s.add(
            SensorProfile(
                id=profile_id,
                name="env-sim",
                vendor="X",
                model="M",
                protocol="modbus_rtu",
                profile_schema={},
                enabled=True,
            )
        )
        s.add(
            Gateway(
                id=gateway_id,
                serial_number="GW-TEST",
                name="Test GW",
                company_id=company_id,
                status="online",
                last_seen_at=datetime(2026, 5, 4, tzinfo=UTC),
            )
        )
        s.add(
            SensorChannel(
                id=sensor_ch_id,
                gateway_id=gateway_id,
                slug="env-1",
                sensor_profile_id=profile_id,
                display_name="Env 6-in-1",
                interface_name="/dev/null",
                protocol="modbus_rtu",
            )
        )
        s.add(
            ActuatorChannel(
                id=uuid.uuid4(),
                gateway_id=gateway_id,
                slug="relay-vent",
                display_name="환기팬",
                actuator_type="relay",
                hardware_channel="GPIO17",
                current_state="off",
            )
        )
        if with_telemetry:
            s.add(
                TelemetryLatest(
                    gateway_id=gateway_id,
                    sensor_channel_id=sensor_ch_id,
                    measurement_key="temperature_c",
                    ts=datetime(2026, 5, 4, tzinfo=UTC),
                    value_double=22.4,
                    unit="°C",
                )
            )
        await s.commit()

    return company_id, sensor_ch_id


def _bearer_headers() -> dict[str, str]:
    """Sim-mode unsigned JWT for KC_VERIFY_SIGNATURE=false."""
    import base64
    import json

    header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        .rstrip(b"=")
        .decode()
    )
    payload_d = {
        "iss": "http://localhost:8080/realms/iot-sim",
        "aud": "iot-backend",
        "sub": "test-user",
        "email": "test@local",
        "name": "T",
        "exp": 9999999999,
        "iat": 1,
    }
    payload = (
        base64.urlsafe_b64encode(json.dumps(payload_d).encode()).rstrip(b"=").decode()
    )
    return {"Authorization": f"Bearer {header}.{payload}."}


@pytest.mark.asyncio
async def test_dashboard_returns_aggregated_view():
    from app.main import app

    gw_id = uuid.uuid4()
    await _setup_db_and_seed(gw_id, with_telemetry=True)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/dashboard?gateway_id={gw_id}",
            headers=_bearer_headers(),
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["gateway"]["serial_number"] == "GW-TEST"
    # SQLite strips tz from DateTime(timezone=True); PostgreSQL preserves it.
    # Accept both ISO forms so the test is portable across both dialects.
    assert body["last_seen"] in (
        "2026-05-04T00:00:00+00:00",
        "2026-05-04T00:00:00",
    )
    assert len(body["sensors"]) == 1
    assert body["sensors"][0]["value"] == 22.4
    assert body["sensors"][0]["unit"] == "°C"
    assert body["sensors"][0]["status"] == "ok"
    assert len(body["actuators"]) == 1
    assert body["actuators"][0]["slug"] == "relay-vent"
    assert body["actuators"][0]["state"] == "off"


@pytest.mark.asyncio
async def test_dashboard_empty_when_no_telemetry():
    from app.main import app

    gw_id = uuid.uuid4()
    await _setup_db_and_seed(gw_id, with_telemetry=False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/dashboard?gateway_id={gw_id}",
            headers=_bearer_headers(),
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["sensors"] == []
    assert len(body["actuators"]) == 1, "actuator should still be present even with no telemetry"
    assert body["actuators"][0]["slug"] == "relay-vent"
    assert body["last_seen"] is not None, "gateway last_seen_at should be populated from seed"
    assert body["gateway"]["serial_number"] == "GW-TEST"


@pytest.mark.asyncio
async def test_dashboard_404_for_unknown_gateway():
    from app.main import app

    # Seed (company + user) but don't seed the bogus gateway we'll query.
    await _setup_db_and_seed(uuid.uuid4(), with_telemetry=False)
    bogus = uuid.uuid4()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/dashboard?gateway_id={bogus}",
            headers=_bearer_headers(),
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_classify_thresholds():
    from app.routers.dashboard import _classify

    assert _classify(22.0, "temperature_c") == "ok"
    assert _classify(30.0, "temperature_c") == "warn"
    assert _classify(40.0, "temperature_c") == "danger"
    assert _classify(None, "temperature_c") == "ok"
    assert _classify(99999.0, "unknown_key") == "ok"  # no threshold = always ok
