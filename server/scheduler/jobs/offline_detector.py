"""Offline detector — last_seen_at이 threshold 이상 지난 gateway를 offline 처리."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Gateway

log = structlog.get_logger("scheduler.offline_detector")


async def run(session: AsyncSession) -> None:
    settings = get_settings()
    threshold = datetime.now(tz=timezone.utc) - timedelta(seconds=settings.offline_threshold_sec)
    res = await session.execute(
        update(Gateway)
        .where(
            Gateway.status == "online",
            (Gateway.last_seen_at.is_(None)) | (Gateway.last_seen_at < threshold),
        )
        .values(status="offline")
        .returning(Gateway.id)
    )
    affected = list(res)
    if affected:
        log.info("marked offline", count=len(affected))
    await session.commit()
