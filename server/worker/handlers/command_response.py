"""Command response handler — gw/{id}/command/response.

payload:
{
  "command_id": "cmd-...",
  "gateway_id": "GW-001",
  "status": "executed" | "rejected" | "failed",
  "reason": "...",
  "result": "...",
  "executed_at": "2026-05-04T12:00:00Z",
  "local_safety_check": "passed" | "rejected_expired" | ...
}
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Command
from app.utils.time import parse_iso8601

log = structlog.get_logger("worker.command_response")


async def handle(session: AsyncSession, gateway_id: uuid.UUID, body: dict) -> None:
    cmd_id = body.get("command_id")
    if not cmd_id:
        log.warning("missing command_id", body=body)
        return

    cmd = await session.get(Command, cmd_id)
    if cmd is None:
        log.warning("unknown command_id", command_id=cmd_id)
        return
    if cmd.gateway_id != gateway_id:
        log.warning(
            "gateway mismatch", command_id=cmd_id, expected=str(cmd.gateway_id), got=str(gateway_id)
        )
        return

    cmd.status = body.get("status", "executed")
    cmd.response = body
    cmd.completed_at = parse_iso8601(body.get("executed_at"))

    await session.commit()
    log.info(
        "command response",
        command_id=cmd_id,
        status=cmd.status,
        gateway_id=str(gateway_id),
    )
