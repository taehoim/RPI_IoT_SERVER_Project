"""Actuator Channels — Gateway에 attach (relay 등 제어 채널)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_session
from app.models import ActuatorChannel, User
from app.routers.gateways import _check_perm
from app.schemas import ActuatorChannelIn, ActuatorChannelOut

router = APIRouter(tags=["actuator-channels"])


@router.post(
    "/gateways/{gateway_id}/actuator-channels",
    response_model=ActuatorChannelOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_actuator_channel(
    gateway_id: uuid.UUID,
    body: ActuatorChannelIn,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> ActuatorChannel:
    await _check_perm(session, user, gateway_id, required="configure")
    channel = ActuatorChannel(id=uuid.uuid4(), gateway_id=gateway_id, **body.model_dump())
    session.add(channel)
    await session.commit()
    await session.refresh(channel)
    return channel


@router.get(
    "/gateways/{gateway_id}/actuator-channels", response_model=list[ActuatorChannelOut]
)
async def list_actuator_channels(
    gateway_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[ActuatorChannel]:
    await _check_perm(session, user, gateway_id, required="view")
    res = await session.execute(
        select(ActuatorChannel)
        .where(ActuatorChannel.gateway_id == gateway_id)
        .order_by(ActuatorChannel.created_at)
    )
    return list(res.scalars())


@router.delete(
    "/actuator-channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_actuator_channel(
    channel_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    channel = await session.get(ActuatorChannel, channel_id)
    if channel is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "channel not found")
    await _check_perm(session, user, channel.gateway_id, required="configure")
    await session.delete(channel)
    await session.commit()
