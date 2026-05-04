"""Heartbeat handler — gw/{id}/heartbeat.

last_seen_at만 갱신. 30초 주기 가정 → offline 임계 90초 (× 3).
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Gateway
from app.utils.time import parse_iso8601

log = structlog.get_logger("worker.heartbeat")


async def handle(session: AsyncSession, gateway_id: uuid.UUID, body: dict) -> None:
    gw = await session.get(Gateway, gateway_id)
    if gw is None:
        log.warning("unknown gateway", gateway_id=str(gateway_id))
        return

    gw.last_seen_at = parse_iso8601(body.get("timestamp"))
    if gw.status == "offline":
        gw.status = "online"

    await session.commit()
    log.debug("heartbeat", gateway_id=str(gateway_id))
