"""Sites CRUD (filter by company_id)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_session
from app.models import Site, User
from app.schemas import SiteIn, SiteOut

router = APIRouter(prefix="/sites", tags=["sites"])


@router.post("", response_model=SiteOut, status_code=status.HTTP_201_CREATED)
async def create_site(
    body: SiteIn,
    session: Annotated[AsyncSession, Depends(get_session)],
    _user: Annotated[User, Depends(get_current_user)],
) -> Site:
    site = Site(id=uuid.uuid4(), **body.model_dump())
    session.add(site)
    await session.commit()
    await session.refresh(site)
    return site


@router.get("", response_model=list[SiteOut])
async def list_sites(
    session: Annotated[AsyncSession, Depends(get_session)],
    _user: Annotated[User, Depends(get_current_user)],
    company_id: uuid.UUID | None = None,
) -> list[Site]:
    stmt = select(Site).order_by(Site.created_at)
    if company_id is not None:
        stmt = stmt.where(Site.company_id == company_id)
    res = await session.execute(stmt)
    return list(res.scalars())
