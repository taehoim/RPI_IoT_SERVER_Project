"""Gateways CRUD + 사용자별 필터링 + state 조회."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_session
from app.models import Gateway, User, UserGatewayPermission
from app.schemas import GatewayIn, GatewayOut, GatewayPatch
from app.utils.time import utcnow

router = APIRouter(prefix="/gateways", tags=["gateways"])


async def _check_perm(
    session: AsyncSession, user: User, gateway_id: uuid.UUID, required: str = "view"
) -> Gateway:
    """user가 gateway에 대해 permission 보유 확인. 없으면 403/404."""
    gateway = await session.get(Gateway, gateway_id)
    if gateway is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "gateway not found")
    res = await session.execute(
        select(UserGatewayPermission).where(
            UserGatewayPermission.user_id == user.id,
            UserGatewayPermission.gateway_id == gateway_id,
            UserGatewayPermission.permission.in_([required, "admin"]),
        )
    )
    if res.scalar_one_or_none() is None:
        # Phase 2: admin role 우회 (Keycloak system_admin 검증은 Phase 4+)
        # TODO: token.has_role("system_admin") 우회 로직 추가
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"missing '{required}' permission")
    return gateway


@router.post("", response_model=GatewayOut, status_code=status.HTTP_201_CREATED)
async def register_gateway(
    body: GatewayIn,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> Gateway:
    gateway = Gateway(id=uuid.uuid4(), **body.model_dump())
    session.add(gateway)
    # 등록자에게 admin 권한 자동 부여
    perm = UserGatewayPermission(
        id=uuid.uuid4(), user_id=user.id, gateway_id=gateway.id, permission="admin"
    )
    session.add(perm)
    await session.commit()
    await session.refresh(gateway)
    return gateway


@router.get("", response_model=list[GatewayOut])
async def list_gateways(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[Gateway]:
    """현재 user에게 view 권한 이상 있는 gateway만 반환."""
    stmt = (
        select(Gateway)
        .join(UserGatewayPermission, UserGatewayPermission.gateway_id == Gateway.id)
        .where(UserGatewayPermission.user_id == user.id)
        .order_by(Gateway.registered_at.desc())
        .distinct()
    )
    res = await session.execute(stmt)
    return list(res.scalars())


@router.get("/{gateway_id}", response_model=GatewayOut)
async def get_gateway(
    gateway_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> Gateway:
    return await _check_perm(session, user, gateway_id, required="view")


@router.patch("/{gateway_id}", response_model=GatewayOut)
async def update_gateway(
    gateway_id: uuid.UUID,
    body: GatewayPatch,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> Gateway:
    gateway = await _check_perm(session, user, gateway_id, required="configure")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(gateway, key, value)
    await session.commit()
    await session.refresh(gateway)
    return gateway


@router.delete("/{gateway_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_gateway(
    gateway_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    gateway = await _check_perm(session, user, gateway_id, required="admin")
    await session.delete(gateway)
    await session.commit()


@router.get("/{gateway_id}/state")
async def get_gateway_state(
    gateway_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    gateway = await _check_perm(session, user, gateway_id, required="view")
    return {
        "gateway_id": str(gateway.id),
        "status": gateway.status,
        "last_seen_at": gateway.last_seen_at.isoformat() if gateway.last_seen_at else None,
        "firmware_version": gateway.firmware_version,
        "app_version": gateway.app_version,
        "config_version": gateway.config_version,
        "now": utcnow().isoformat(),
    }
