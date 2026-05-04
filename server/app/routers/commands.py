"""Commands — Gateway 원격 제어 publish (User → Web → Backend → MQTT → Gateway)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import mqtt_publisher
from app.auth import get_current_user
from app.config import get_settings
from app.db import get_session
from app.models import ActuatorChannel, Command, Gateway, User
from app.routers.gateways import _check_perm
from app.schemas import CommandIn, CommandOut

router = APIRouter(tags=["commands"])


@router.post(
    "/gateways/{gateway_id}/commands",
    response_model=CommandOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def issue_command(
    gateway_id: uuid.UUID,
    body: CommandIn,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> Command:
    await _check_perm(session, user, gateway_id, required="control")

    # gateway lookup — wire 토픽은 serial_number로 발행해야 gateway agent가 받음.
    gw = await session.get(Gateway, gateway_id)
    if gw is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "gateway not found")

    # actuator channel은 같은 gateway 소속이어야 함. payload는 슬러그로 보냄.
    actuator = await session.get(ActuatorChannel, body.actuator_channel_id)
    if actuator is None or actuator.gateway_id != gateway_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "actuator_channel not found in gateway")

    settings = get_settings()
    now = datetime.now(tz=timezone.utc)
    expires_at = now + timedelta(seconds=body.expires_in_sec or settings.command_default_expires_sec)
    cmd_id = f"cmd-{now.strftime('%Y%m%d-%H%M%S-%f')}-{uuid.uuid4().hex[:8]}"

    cmd = Command(
        id=cmd_id,
        gateway_id=gateway_id,
        actuator_channel_id=body.actuator_channel_id,
        action=body.action,
        issued_by=user.id,
        issued_at=now,
        expires_at=expires_at,
        timeout_ms=body.timeout_ms,
        require_ack=body.require_ack,
        reason=body.reason,
        status="pending",
    )
    session.add(cmd)
    await session.commit()
    await session.refresh(cmd)

    # MQTT payload는 wire 식별자(슬러그)로 발행. Gateway agent가 YAML config의
    # `gateway.id` (= serial_number)와 actuator `channel_id` (= slug)로 매칭.
    payload = {
        "command_id": cmd.id,
        "gateway_id": gw.serial_number,
        "target_type": "actuator",
        "actuator_channel_id": actuator.slug,
        "action": body.action,
        "issued_by": str(user.id),
        "issued_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "timeout_ms": body.timeout_ms,
        "require_ack": body.require_ack,
        "reason": body.reason or "",
    }
    try:
        await mqtt_publisher.publish(
            f"gw/{gw.serial_number}/command/request", payload, qos=1
        )
        cmd.status = "published"
        await session.commit()
    except Exception as exc:  # noqa: BLE001 — DB record는 유지, retry는 scheduler가
        # publish 실패해도 status=pending로 둠 → scheduler가 timeout 처리
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"mqtt publish failed: {exc}",
        ) from exc

    return cmd


@router.get("/commands/{command_id}", response_model=CommandOut)
async def get_command(
    command_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> Command:
    cmd = await session.get(Command, command_id)
    if cmd is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "command not found")
    await _check_perm(session, user, cmd.gateway_id, required="view")
    return cmd
