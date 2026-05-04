"""Telemetry handler — INSERT telemetry + UPSERT telemetry_latest.

payload (Gateway agent와 동일 schema):
{
  "message_id": "...",
  "gateway_id": "GW-001",
  "timestamp": "2026-05-04T12:00:00Z",
  "values": [
    {"sensor_channel_id": "...", "measurement_key": "ammonia",
     "value": 18.4, "unit": "ppm", "quality": "good"},
    ...
  ]
}
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Gateway, Telemetry, TelemetryLatest
from app.utils.time import parse_iso8601
from worker.handlers._lookups import sensor_channel_uuid_by_slug

log = structlog.get_logger("worker.telemetry")


async def handle(session: AsyncSession, gateway_id: uuid.UUID, body: dict) -> None:
    values = body.get("values") or []
    if not values:
        log.warning("empty telemetry values", gateway_id=str(gateway_id))
        return

    ts = parse_iso8601(body.get("timestamp"))

    # company_id / site_id 조회 (Phase 2: gateway 1회 lookup)
    gw = await session.get(Gateway, gateway_id)
    if gw is None:
        log.warning("unknown gateway", gateway_id=str(gateway_id))
        return

    inserted = 0
    for v in values:
        # sensor_channel_id는 wire 식별자(슬러그). DB UUID로 lookup.
        slug = v.get("sensor_channel_id")
        if not isinstance(slug, str) or not slug:
            log.warning("missing sensor_channel_id", value=v)
            continue
        channel_id = await sensor_channel_uuid_by_slug(session, gateway_id, slug)
        if channel_id is None:
            log.warning(
                "unknown sensor_channel_slug",
                gateway_id=str(gateway_id),
                slug=slug,
            )
            continue
        key = v.get("measurement_key", "")
        if not key:
            continue

        # 값 분기 (Phase 2: float만 처리, 추후 bool/text/json)
        value = v.get("value")
        value_double = float(value) if isinstance(value, (int, float)) else None
        unit = v.get("unit")
        quality = v.get("quality", "good")

        session.add(
            Telemetry(
                company_id=gw.company_id,
                site_id=gw.site_id,
                gateway_id=gateway_id,
                sensor_channel_id=channel_id,
                measurement_key=key,
                ts=ts,
                value_double=value_double,
                unit=unit,
                quality=quality,
                raw=v,
            )
        )

        # UPSERT telemetry_latest (overwrite if newer)
        stmt = pg_insert(TelemetryLatest).values(
            gateway_id=gateway_id,
            sensor_channel_id=channel_id,
            measurement_key=key,
            ts=ts,
            value_double=value_double,
            unit=unit,
            quality=quality,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                TelemetryLatest.gateway_id,
                TelemetryLatest.sensor_channel_id,
                TelemetryLatest.measurement_key,
            ],
            set_={
                "ts": stmt.excluded.ts,
                "value_double": stmt.excluded.value_double,
                "unit": stmt.excluded.unit,
                "quality": stmt.excluded.quality,
            },
            where=TelemetryLatest.ts < stmt.excluded.ts,
        )
        await session.execute(stmt)
        inserted += 1

    # gateway last_seen_at 업데이트
    gw.last_seen_at = ts
    if gw.status != "online":
        gw.status = "online"

    await session.commit()
    log.debug("telemetry stored", gateway_id=str(gateway_id), count=inserted)

    # Notify SSE subscribers (best-effort, non-blocking)
    try:
        from app.routers.dashboard import notify_telemetry

        await notify_telemetry(str(gateway_id))
    except Exception:  # noqa: BLE001 — SSE is non-critical
        pass
