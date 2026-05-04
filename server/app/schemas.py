"""Pydantic v2 schemas — request/response DTO.

모델당 In/Out 분리 (입력은 server 생성 필드 제외).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Wire 식별자 슬러그: ^[A-Za-z0-9_-]+$, 1-64자.
# Gateway YAML, MQTT topic segment, payload field 모두 이 형식으로 통일.
# DB CHECK constraint와 동일 (alembic 0002).
SlugStr = Annotated[
    str,
    StringConstraints(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"),
]

# ============================================================
# Companies / Sites
# ============================================================


class CompanyIn(BaseModel):
    name: str
    company_type: Literal["management", "customer"] = "customer"
    status: str = "active"


class CompanyOut(CompanyIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime


class SiteIn(BaseModel):
    company_id: uuid.UUID
    name: str
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class SiteOut(SiteIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime


# ============================================================
# Gateways
# ============================================================


class GatewayIn(BaseModel):
    # serial_number는 wire 식별자 (MQTT topic, payload). gateway YAML의 gateway.id와 1:1 매핑.
    serial_number: SlugStr
    name: str
    company_id: uuid.UUID
    site_id: uuid.UUID | None = None
    gateway_profile_id: uuid.UUID | None = None


class GatewayPatch(BaseModel):
    name: str | None = None
    site_id: uuid.UUID | None = None
    gateway_profile_id: uuid.UUID | None = None
    status: str | None = None
    firmware_version: str | None = None
    app_version: str | None = None


class GatewayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    serial_number: str
    name: str
    company_id: uuid.UUID
    site_id: uuid.UUID | None
    gateway_profile_id: uuid.UUID | None
    status: str
    firmware_version: str | None
    app_version: str | None
    config_version: int
    last_seen_at: datetime | None
    registered_at: datetime


# ============================================================
# Sensor Profile / Channel
# ============================================================


class SensorProfileIn(BaseModel):
    name: str
    vendor: str | None = None
    model: str | None = None
    protocol: str
    description: str | None = None
    profile_schema: dict[str, Any] = Field(
        ..., description="Sensor Profile JSON (shared/sensor_profile_schema.json 준수)"
    )
    enabled: bool = True


class SensorProfileOut(SensorProfileIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime


class SensorChannelIn(BaseModel):
    # slug는 wire 식별자 — gateway YAML의 channel_id, MQTT payload의 sensor_channel_id.
    # gateway 단위 unique. 예: "sensor-01", "nh3-1F".
    slug: SlugStr
    sensor_profile_id: uuid.UUID
    display_name: str
    interface_name: str
    protocol: str
    address: str | None = None
    slave_id: int | None = None
    polling_interval_sec: int = 10
    enabled: bool = True
    config: dict[str, Any] | None = None


class SensorChannelOut(SensorChannelIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    gateway_id: uuid.UUID
    created_at: datetime


# ============================================================
# Actuator Channel
# ============================================================


class ActuatorChannelIn(BaseModel):
    # slug는 wire 식별자 — gateway YAML의 channel_id, MQTT command payload의 actuator_channel_id.
    # 예: "relay-vent", "valve-spray".
    slug: SlugStr
    display_name: str
    actuator_type: Literal["relay", "valve", "pump", "ssr"] = "relay"
    hardware_channel: str
    default_state: str = "off"
    enabled: bool = True
    safety_config: dict[str, Any] | None = None


class ActuatorChannelOut(ActuatorChannelIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    gateway_id: uuid.UUID
    current_state: str | None
    created_at: datetime


# ============================================================
# Command
# ============================================================


class CommandIn(BaseModel):
    actuator_channel_id: uuid.UUID
    action: Literal["ON", "OFF"]
    expires_in_sec: int = 5
    timeout_ms: int = 3000
    require_ack: bool = True
    reason: str | None = None


class CommandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    gateway_id: uuid.UUID
    actuator_channel_id: uuid.UUID | None
    action: str
    issued_at: datetime
    expires_at: datetime
    status: str
    response: dict[str, Any] | None
    completed_at: datetime | None


# ============================================================
# Telemetry
# ============================================================


class TelemetryLatestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    gateway_id: uuid.UUID
    sensor_channel_id: uuid.UUID
    measurement_key: str
    ts: datetime
    value_double: float | None
    value_text: str | None
    value_bool: bool | None
    unit: str | None
    quality: str | None


class TelemetryRow(BaseModel):
    ts: datetime
    measurement_key: str
    value_double: float | None
    unit: str | None
    quality: str | None
