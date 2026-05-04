"""Telemetry 조회 — latest (대시보드) + 시계열 (그래프)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_session
from app.models import Telemetry, TelemetryLatest, User
from app.routers.gateways import _check_perm
from app.schemas import TelemetryLatestOut, TelemetryRow

router = APIRouter(tags=["telemetry"])


@router.get(
    "/gateways/{gateway_id}/latest", response_model=list[TelemetryLatestOut]
)
async def get_latest(
    gateway_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[TelemetryLatest]:
    await _check_perm(session, user, gateway_id, required="view")
    res = await session.execute(
        select(TelemetryLatest)
        .where(TelemetryLatest.gateway_id == gateway_id)
        .order_by(TelemetryLatest.measurement_key)
    )
    return list(res.scalars())


@router.get(
    "/gateways/{gateway_id}/telemetry", response_model=list[TelemetryRow]
)
async def get_telemetry_range(
    gateway_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    measurement_key: Annotated[str | None, Query(description="필터: 특정 측정값만")] = None,
    hours: Annotated[int, Query(ge=1, le=720, description="최근 N시간 (max 30일)")] = 24,
    limit: Annotated[int, Query(ge=1, le=10000)] = 1000,
) -> list[TelemetryRow]:
    await _check_perm(session, user, gateway_id, required="view")
    since = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
    stmt = (
        select(
            Telemetry.ts,
            Telemetry.measurement_key,
            Telemetry.value_double,
            Telemetry.unit,
            Telemetry.quality,
        )
        .where(Telemetry.gateway_id == gateway_id, Telemetry.ts >= since)
        .order_by(Telemetry.ts.desc())
        .limit(limit)
    )
    if measurement_key is not None:
        stmt = stmt.where(Telemetry.measurement_key == measurement_key)
    res = await session.execute(stmt)
    return [
        TelemetryRow(
            ts=row.ts,
            measurement_key=row.measurement_key,
            value_double=row.value_double,
            unit=row.unit,
            quality=row.quality,
        )
        for row in res
    ]
