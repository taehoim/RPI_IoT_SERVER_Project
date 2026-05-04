"""Sensor Profile CRUD + JSON Schema 검증."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Annotated

import jsonschema
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_session
from app.models import SensorProfile, User
from app.schemas import SensorProfileIn, SensorProfileOut

router = APIRouter(prefix="/sensor-profiles", tags=["sensor-profiles"])

# shared/sensor_profile_schema.json 로드 (서버 + gateway 공유 SoT)
_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "shared" / "sensor_profile_schema.json"
_PROFILE_SCHEMA: dict | None = None


def _schema() -> dict:
    global _PROFILE_SCHEMA
    if _PROFILE_SCHEMA is None:
        if not _SCHEMA_PATH.exists():
            raise RuntimeError(f"Sensor Profile schema not found: {_SCHEMA_PATH}")
        _PROFILE_SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return _PROFILE_SCHEMA


@router.post("", response_model=SensorProfileOut, status_code=status.HTTP_201_CREATED)
async def create_sensor_profile(
    body: SensorProfileIn,
    session: Annotated[AsyncSession, Depends(get_session)],
    _user: Annotated[User, Depends(get_current_user)],
) -> SensorProfile:
    # Sensor Profile JSON Schema 검증 (gateway와 동일 SoT)
    try:
        jsonschema.validate(body.profile_schema, _schema())
    except jsonschema.ValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"profile_schema validation failed: {exc.message}",
        ) from exc

    profile = SensorProfile(id=uuid.uuid4(), **body.model_dump())
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile


@router.get("", response_model=list[SensorProfileOut])
async def list_sensor_profiles(
    session: Annotated[AsyncSession, Depends(get_session)],
    _user: Annotated[User, Depends(get_current_user)],
) -> list[SensorProfile]:
    res = await session.execute(
        select(SensorProfile).where(SensorProfile.enabled.is_(True)).order_by(SensorProfile.name)
    )
    return list(res.scalars())


@router.get("/{profile_id}", response_model=SensorProfileOut)
async def get_sensor_profile(
    profile_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    _user: Annotated[User, Depends(get_current_user)],
) -> SensorProfile:
    profile = await session.get(SensorProfile, profile_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "sensor profile not found")
    return profile
