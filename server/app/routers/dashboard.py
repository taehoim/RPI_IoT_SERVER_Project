"""Dashboard aggregator endpoint.

Returns a single snapshot for the card grid:
  { gateway, sensors[], actuators[], last_seen }

Real-time updates: clients poll via TanStack Query refetchInterval=5s. SSE/MQTT
push is deferred to Phase 2 — needs cross-process pub/sub (e.g., Postgres
LISTEN/NOTIFY or MQTT topic events/dashboard/{gateway_id}) plus a stream-
auth ticket flow because EventSource can't send Authorization headers.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_session
from app.models import ActuatorChannel, Gateway, SensorChannel, TelemetryLatest, User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# 임계치 (Phase 2에서 sensor_profile 기반으로 교체)
_THRESHOLDS: dict[str, tuple[float, float]] = {
    "co2_ppm": (1000.0, 1500.0),
    "temperature_c": (28.0, 35.0),
    "humidity_pct": (80.0, 90.0),
}


def _classify(value: float | None, key: str) -> str:
    if value is None:
        return "ok"
    warn, danger = _THRESHOLDS.get(key, (float("inf"), float("inf")))
    if value >= danger:
        return "danger"
    if value >= warn:
        return "warn"
    return "ok"


def _latest_value(row: TelemetryLatest) -> float | None:
    """Pick the active value variant. Dashboard only uses numeric (double)."""
    return row.value_double


@router.get("")
async def get_dashboard(
    gateway_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    gw = await session.get(Gateway, gateway_id)
    if not gw:
        raise HTTPException(404, "gateway not found")

    # Channel display names
    ch_rows = await session.execute(
        select(SensorChannel).where(SensorChannel.gateway_id == gateway_id)
    )
    ch_names = {c.id: c.display_name for c in ch_rows.scalars()}

    # Latest telemetry per (channel, measurement) — single table, no aggregation.
    latest_rows = await session.execute(
        select(TelemetryLatest).where(TelemetryLatest.gateway_id == gateway_id)
    )
    sensors = []
    for row in latest_rows.scalars():
        v = _latest_value(row)
        sensors.append(
            {
                "channel_id": str(row.sensor_channel_id),
                "channel_name": ch_names.get(row.sensor_channel_id, row.measurement_key),
                "measurement_key": row.measurement_key,
                "value": v,
                "unit": row.unit or "",
                "ts": row.ts.isoformat(),
                "status": _classify(v, row.measurement_key),
            }
        )

    act_rows = await session.execute(
        select(ActuatorChannel).where(ActuatorChannel.gateway_id == gateway_id)
    )
    actuators = [
        {
            "id": str(a.id),
            "slug": a.slug,
            "display_name": a.display_name,
            "state": a.current_state or "unknown",
            "enabled": a.enabled,
        }
        for a in act_rows.scalars()
    ]

    return {
        "gateway": {
            "id": str(gw.id),
            "serial_number": gw.serial_number,
            "name": gw.name,
            "status": gw.status,
            "site_id": str(gw.site_id) if gw.site_id else None,
        },
        "sensors": sensors,
        "actuators": actuators,
        "last_seen": gw.last_seen_at.isoformat() if gw.last_seen_at else None,
    }
