"""Sensor Channels — Gateway에 attach/detach."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_session
from app.models import SensorChannel, User
from app.routers.gateways import _check_perm
from app.schemas import SensorChannelIn, SensorChannelOut

router = APIRouter(tags=["sensor-channels"])


@router.post(
    "/gateways/{gateway_id}/sensor-channels",
    response_model=SensorChannelOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_sensor_channel(
    gateway_id: uuid.UUID,
    body: SensorChannelIn,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> SensorChannel:
    await _check_perm(session, user, gateway_id, required="configure")
    channel = SensorChannel(id=uuid.uuid4(), gateway_id=gateway_id, **body.model_dump())
    session.add(channel)
    await session.commit()
    await session.refresh(channel)
    return channel


@router.get("/gateways/{gateway_id}/sensor-channels", response_model=list[SensorChannelOut])
async def list_sensor_channels(
    gateway_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[SensorChannel]:
    await _check_perm(session, user, gateway_id, required="view")
    res = await session.execute(
        select(SensorChannel)
        .where(SensorChannel.gateway_id == gateway_id)
        .order_by(SensorChannel.created_at)
    )
    return list(res.scalars())


@router.delete(
    "/sensor-channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_sensor_channel(
    channel_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    channel = await session.get(SensorChannel, channel_id)
    if channel is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "channel not found")
    await _check_perm(session, user, channel.gateway_id, required="configure")
    await session.delete(channel)
    await session.commit()
