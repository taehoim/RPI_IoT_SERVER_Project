"""Worker dispatcher 단위 테스트 — slug 토픽 → UUID 변환."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from worker.handlers import _lookups, dispatch


@pytest.fixture(autouse=True)
def _clear_cache():
    _lookups.invalidate_all()
    yield
    _lookups.invalidate_all()


@pytest.mark.asyncio
async def test_dispatch_slug_topic_resolves_to_uuid():
    gw_uuid = uuid.uuid4()
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value.scalar_one_or_none = MagicMock(return_value=gw_uuid)

    handler_called_with = {}

    async def _stub(s, gw_id, body):
        handler_called_with["gw_id"] = gw_id
        handler_called_with["body"] = body

    with patch("worker.handlers.telemetry_h.handle", side_effect=_stub):
        await dispatch(session, "gw/GW-DEV01/telemetry", b'{"values":[]}')

    assert handler_called_with["gw_id"] == gw_uuid


@pytest.mark.asyncio
async def test_dispatch_unknown_serial_drops_message():
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)

    with patch("worker.handlers.telemetry_h.handle") as h:
        await dispatch(session, "gw/UNKNOWN/telemetry", b'{"values":[]}')
        h.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_command_response_4segment_topic():
    """gw/{serial}/command/response (4 segment) 가 dispatcher regex에 매칭되어야 함."""
    gw_uuid = uuid.uuid4()
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value.scalar_one_or_none = MagicMock(return_value=gw_uuid)

    with patch("worker.handlers.command_response.handle") as h:
        await dispatch(
            session,
            "gw/GW-DEV01/command/response",
            b'{"command_id":"c1","status":"executed"}',
        )
        h.assert_called_once()
        # 두 번째 인자가 gateway UUID
        assert h.call_args[0][1] == gw_uuid


@pytest.mark.asyncio
async def test_dispatch_invalid_topic_logged_and_dropped():
    session = MagicMock()
    session.execute = AsyncMock()

    # gateway lookup 호출되지 않아야 함
    await dispatch(session, "wrong/format", b'{}')
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_invalid_json_logged():
    gw_uuid = uuid.uuid4()
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value.scalar_one_or_none = MagicMock(return_value=gw_uuid)

    with patch("worker.handlers.telemetry_h.handle") as h:
        await dispatch(session, "gw/GW-DEV01/telemetry", b'{not json')
        h.assert_not_called()
