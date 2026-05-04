"""Command timeout — expires_at 경과 + status pending/published를 timeout 처리."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Command

log = structlog.get_logger("scheduler.command_timeout")


async def run(session: AsyncSession) -> None:
    now = datetime.now(tz=timezone.utc)
    res = await session.execute(
        update(Command)
        .where(
            Command.status.in_(("pending", "published")),
            Command.expires_at < now,
        )
        .values(status="timeout", completed_at=now)
        .returning(Command.id)
    )
    affected = list(res)
    if affected:
        log.info("commands timed out", count=len(affected))
    await session.commit()
