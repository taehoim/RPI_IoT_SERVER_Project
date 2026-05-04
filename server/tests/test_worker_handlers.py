"""Worker handler 단위 테스트 — telemetry parsing + slug → UUID lookup."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from worker.handlers import _lookups, telemetry as telemetry_h


@pytest.fixture(autouse=True)
def _clear_lookup_cache():
    _lookups.invalidate_all()
    yield
    _lookups.invalidate_all()


@pytest.mark.asyncio
async def test_telemetry_handler_skips_unknown_gateway(caplog):
    session = MagicMock()
    session.get = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock()

    body = {
        "message_id": "m1",
        "timestamp": "2026-05-04T12:00:00Z",
        "values": [
            {"sensor_channel_id": "sensor-01", "measurement_key": "temp", "value": 24.5}
        ],
    }
    await telemetry_h.handle(session, uuid.uuid4(), body)
    # gateway가 None이면 commit 호출되지 않음
    session.commit.assert_not_called()
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_telemetry_handler_empty_values_no_op():
    session = MagicMock()
    session.commit = AsyncMock()
    await telemetry_h.handle(session, uuid.uuid4(), {"values": []})
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_telemetry_handler_unknown_slug_skipped():
    """미등록 sensor_channel slug는 silently skip하되 다른 값은 정상 처리."""
    gw_id = uuid.uuid4()
    known_channel_uuid = uuid.uuid4()
    session = MagicMock()
    session.get = AsyncMock(
        return_value=MagicMock(company_id=uuid.uuid4(), site_id=None, status="online")
    )
    session.add = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()

    async def _lookup(_session, gateway_id, slug):
        return known_channel_uuid if slug == "sensor-known" else None

    body = {
        "timestamp": "2026-05-04T12:00:00Z",
        "values": [
            {"sensor_channel_id": "sensor-unknown", "measurement_key": "x", "value": 1.0},
            {"sensor_channel_id": "sensor-known", "measurement_key": "y", "value": 2.0},
        ],
    }
    with patch.object(telemetry_h, "sensor_channel_uuid_by_slug", side_effect=_lookup):
        await telemetry_h.handle(session, gw_id, body)
    assert session.add.call_count == 1
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_telemetry_handler_missing_sensor_channel_id_skipped():
    """payload에 sensor_channel_id 누락 시 해당 value만 skip."""
    gw_id = uuid.uuid4()
    session = MagicMock()
    session.get = AsyncMock(
        return_value=MagicMock(company_id=uuid.uuid4(), site_id=None, status="online")
    )
    session.add = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()

    body = {
        "timestamp": "2026-05-04T12:00:00Z",
        "values": [{"measurement_key": "x", "value": 1.0}],  # sensor_channel_id 없음
    }
    await telemetry_h.handle(session, gw_id, body)
    session.add.assert_not_called()
    session.commit.assert_called_once()  # gateway last_seen_at 갱신은 진행
