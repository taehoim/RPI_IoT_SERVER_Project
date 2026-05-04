"""Command response handler 단위 테스트."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from worker.handlers import command_response


@pytest.mark.asyncio
async def test_unknown_command_id_logged():
    session = MagicMock()
    session.get = AsyncMock(return_value=None)
    session.commit = AsyncMock()
    await command_response.handle(session, uuid.uuid4(), {"command_id": "cmd-x"})
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_command_status_updated():
    cmd = MagicMock()
    cmd.gateway_id = uuid.uuid4()
    cmd.status = "published"
    session = MagicMock()
    session.get = AsyncMock(return_value=cmd)
    session.commit = AsyncMock()
    await command_response.handle(
        session,
        cmd.gateway_id,
        {
            "command_id": "cmd-1",
            "status": "executed",
            "executed_at": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        },
    )
    assert cmd.status == "executed"
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_gateway_mismatch_rejected():
    cmd = MagicMock()
    cmd.gateway_id = uuid.uuid4()
    other_gw = uuid.uuid4()
    session = MagicMock()
    session.get = AsyncMock(return_value=cmd)
    session.commit = AsyncMock()
    await command_response.handle(session, other_gw, {"command_id": "cmd-1", "status": "executed"})
    session.commit.assert_not_called()
