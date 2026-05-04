"""Wire 식별자(serial/slug) → DB UUID lookup helpers.

각 worker process 내 in-memory TTL 캐시. 채널/게이트웨이는 자주 바뀌지 않으므로
60초 TTL로 충분 (Phase 5+ pubsub 무효화 시 TTL 단축 또는 이벤트-기반 invalidation).

캐시 부재 시 매 telemetry 메시지마다 추가 SELECT 발생 → 100 gateway × 10s polling
× 6 channel = 6000 SELECT/min → DB pool 포화 위험.
"""

from __future__ import annotations

import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ActuatorChannel, Gateway, SensorChannel

_TTL_SEC = 60.0

# (key) → (uuid_or_None, expires_at)
_gateway_cache: dict[str, tuple[uuid.UUID | None, float]] = {}
_sensor_channel_cache: dict[tuple[uuid.UUID, str], tuple[uuid.UUID | None, float]] = {}
_actuator_channel_cache: dict[tuple[uuid.UUID, str], tuple[uuid.UUID | None, float]] = {}


def _expired(entry: tuple[uuid.UUID | None, float]) -> bool:
    return entry[1] < time.monotonic()


async def gateway_uuid_by_serial(session: AsyncSession, serial: str) -> uuid.UUID | None:
    """serial_number → gateways.id. 미존재 시 None."""
    cached = _gateway_cache.get(serial)
    if cached is not None and not _expired(cached):
        return cached[0]
    res = await session.execute(select(Gateway.id).where(Gateway.serial_number == serial))
    gw_id = res.scalar_one_or_none()
    _gateway_cache[serial] = (gw_id, time.monotonic() + _TTL_SEC)
    return gw_id


async def sensor_channel_uuid_by_slug(
    session: AsyncSession, gateway_id: uuid.UUID, slug: str
) -> uuid.UUID | None:
    """(gateway_id, slug) → sensor_channels.id. 미존재 시 None."""
    key = (gateway_id, slug)
    cached = _sensor_channel_cache.get(key)
    if cached is not None and not _expired(cached):
        return cached[0]
    res = await session.execute(
        select(SensorChannel.id).where(
            SensorChannel.gateway_id == gateway_id,
            SensorChannel.slug == slug,
        )
    )
    ch_id = res.scalar_one_or_none()
    _sensor_channel_cache[key] = (ch_id, time.monotonic() + _TTL_SEC)
    return ch_id


async def actuator_channel_by_slug(
    session: AsyncSession, gateway_id: uuid.UUID, slug: str
) -> uuid.UUID | None:
    """(gateway_id, slug) → actuator_channels.id. 미존재 시 None."""
    key = (gateway_id, slug)
    cached = _actuator_channel_cache.get(key)
    if cached is not None and not _expired(cached):
        return cached[0]
    res = await session.execute(
        select(ActuatorChannel.id).where(
            ActuatorChannel.gateway_id == gateway_id,
            ActuatorChannel.slug == slug,
        )
    )
    ch_id = res.scalar_one_or_none()
    _actuator_channel_cache[key] = (ch_id, time.monotonic() + _TTL_SEC)
    return ch_id


def invalidate_gateway(serial: str) -> None:
    _gateway_cache.pop(serial, None)


def invalidate_all() -> None:
    """테스트/관리 작업용. Production에서는 TTL 만료에 의존."""
    _gateway_cache.clear()
    _sensor_channel_cache.clear()
    _actuator_channel_cache.clear()
