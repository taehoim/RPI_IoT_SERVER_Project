"""State handler — gw/{id}/state (online/offline retained).

payload:
{
  "gateway_id": "GW-001",
  "timestamp": "2026-05-04T12:00:00Z",
  "status": "online" | "offline" | "shutdown",
  "app_version": "0.1.0",
  "firmware_version": "2026.05.04",
  "config_version": 12,
  ...
}
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Gateway
from app.utils.time import parse_iso8601, utcnow

log = structlog.get_logger("worker.state")


async def handle(session: AsyncSession, gateway_id: uuid.UUID, body: dict) -> None:
    gw = await session.get(Gateway, gateway_id)
    if gw is None:
        log.warning("unknown gateway", gateway_id=str(gateway_id))
        return

    new_status = body.get("status", "online")
    gw.status = new_status if new_status in ("online", "offline", "shutdown") else "offline"

    if "app_version" in body:
        gw.app_version = body["app_version"]
    if "firmware_version" in body:
        gw.firmware_version = body["firmware_version"]
    if "config_version" in body and isinstance(body["config_version"], int):
        gw.config_version = body["config_version"]

    # LWT payload는 timestamp가 없거나 stale (gateway client 시작 시점에 고정).
    # reason="lwt"면 broker 감지 시각 ≈ 서버 현재시각으로 대체.
    if new_status == "online":
        gw.last_seen_at = parse_iso8601(body.get("timestamp"))
    elif new_status == "offline" and body.get("reason") == "lwt":
        gw.last_seen_at = utcnow()

    await session.commit()
    log.info("state updated", gateway_id=str(gateway_id), status=gw.status)
