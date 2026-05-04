"""SQLAlchemy 2.0 ORM models — 12 핵심 테이블 (design doc § 11-22).

Phase 2-4 범위:
  Identity:    users, user_company_roles, user_gateway_permissions
  Asset:       companies, sites, gateways, gateway_profiles
  Profile:     sensor_profiles, sensor_channels
  Actuator:    actuator_channels
  Telemetry:   telemetry (월별 partition), telemetry_latest
  Operations:  commands, audit_logs

미포함 (Phase 5+):
  gateway_configs, gateway_config_history (Phase 5)
  alarm_rules, bulk_jobs, actuator_profiles (Phase 4-6)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    UUID,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """공통 base."""


# ============================================================
# Identity
# ============================================================


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    company_type: Mapped[str] = mapped_column(String(32), nullable=False)  # 'management' | 'customer'
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sites: Mapped[list[Site]] = relationship(back_populates="company", cascade="all, delete-orphan")


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped[Company] = relationship(back_populates="sites")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    keycloak_user_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserCompanyRole(Base):
    __tablename__ = "user_company_roles"
    __table_args__ = (UniqueConstraint("user_id", "company_id", "role"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserGatewayPermission(Base):
    __tablename__ = "user_gateway_permissions"
    __table_args__ = (UniqueConstraint("user_id", "gateway_id", "permission"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    gateway_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    permission: Mapped[str] = mapped_column(String(32), nullable=False)
    # view | control | configure | maintain | admin
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# Gateway / Profile
# ============================================================


class GatewayProfile(Base):
    __tablename__ = "gateway_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    hardware_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Gateway(Base):
    __tablename__ = "gateways"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    serial_number: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id"))
    gateway_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gateway_profiles.id")
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="offline")
    firmware_version: Mapped[str | None] = mapped_column(String(64))
    app_version: Mapped[str | None] = mapped_column(String(64))
    config_version: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    sensor_channels: Mapped[list[SensorChannel]] = relationship(
        back_populates="gateway", cascade="all, delete-orphan"
    )
    actuator_channels: Mapped[list[ActuatorChannel]] = relationship(
        back_populates="gateway", cascade="all, delete-orphan"
    )


# ============================================================
# Sensor / Actuator
# ============================================================


class SensorProfile(Base):
    __tablename__ = "sensor_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    vendor: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    protocol: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    profile_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SensorChannel(Base):
    __tablename__ = "sensor_channels"
    # slug는 wire 식별자 (gateway YAML의 channel_id, MQTT payload의 sensor_channel_id).
    # gateway 단위로 unique. 형식 ^[A-Za-z0-9_-]+$ 는 alembic CHECK constraint로 강제.
    __table_args__ = (UniqueConstraint("gateway_id", "slug", name="uq_sensor_channels_gateway_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gateway_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gateways.id"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    sensor_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sensor_profiles.id"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    interface_name: Mapped[str] = mapped_column(String(64), nullable=False)
    protocol: Mapped[str] = mapped_column(String(32), nullable=False)
    address: Mapped[str | None] = mapped_column(String(64))
    slave_id: Mapped[int | None] = mapped_column(Integer)
    polling_interval_sec: Mapped[int] = mapped_column(Integer, default=10)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    gateway: Mapped[Gateway] = relationship(back_populates="sensor_channels")


class ActuatorChannel(Base):
    __tablename__ = "actuator_channels"
    # slug는 wire 식별자 (gateway YAML의 channel_id, MQTT command payload의 actuator_channel_id).
    __table_args__ = (UniqueConstraint("gateway_id", "slug", name="uq_actuator_channels_gateway_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gateway_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gateways.id"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    actuator_type: Mapped[str] = mapped_column(String(32), nullable=False)  # 'relay' | 'valve' | ...
    hardware_channel: Mapped[str] = mapped_column(String(64), nullable=False)
    default_state: Mapped[str] = mapped_column(String(8), nullable=False, default="off")
    current_state: Mapped[str | None] = mapped_column(String(16))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    safety_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    gateway: Mapped[Gateway] = relationship(back_populates="actuator_channels")


# ============================================================
# Telemetry (월별 partition)
# ============================================================


class Telemetry(Base):
    """월별 PARTITION BY RANGE (ts).

    초기 마이그레이션은 parent + 1개월치 partition 생성.
    추가 partition은 Scheduler가 자동 생성 (jobs/partition_manager.py).
    """

    __tablename__ = "telemetry"

    # Identity()는 SQLAlchemy에게 "DB가 값을 채운다"고 명시 → INSERT 시 컬럼 제외 + RETURNING으로 회수.
    # alembic 0001은 BIGSERIAL로 테이블을 만들어 sequence default가 이미 걸려 있어서
    # runtime에서는 BIGSERIAL과 IDENTITY가 동등하게 동작.
    # 미적용 시: id=None이 명시 INSERT되어 NotNullViolationError로 telemetry 처리 100% 실패.
    id: Mapped[int] = mapped_column(BigInteger, Identity(), autoincrement=True)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    gateway_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sensor_channel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    measurement_key: Mapped[str] = mapped_column(String(64), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value_double: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str | None] = mapped_column(Text)
    value_bool: Mapped[bool | None] = mapped_column(Boolean)
    value_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    unit: Mapped[str | None] = mapped_column(String(32))
    quality: Mapped[str | None] = mapped_column(String(32))
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    __mapper_args__ = {"primary_key": [id, ts]}
    __table_args__ = (
        {"postgresql_partition_by": "RANGE (ts)"},
    )


class TelemetryLatest(Base):
    """대시보드 최신값 조회용 (O(1))."""

    __tablename__ = "telemetry_latest"

    gateway_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    sensor_channel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    measurement_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value_double: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str | None] = mapped_column(Text)
    value_bool: Mapped[bool | None] = mapped_column(Boolean)
    value_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    unit: Mapped[str | None] = mapped_column(String(32))
    quality: Mapped[str | None] = mapped_column(String(32))


# ============================================================
# Commands / Audit
# ============================================================


class Command(Base):
    __tablename__ = "commands"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # command_id from request
    gateway_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gateways.id"), nullable=False
    )
    actuator_channel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("actuator_channels.id")
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    issued_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timeout_ms: Mapped[int] = mapped_column(Integer, default=3000)
    require_ack: Mapped[bool] = mapped_column(Boolean, default=True)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    # pending | published | executed | rejected | failed | timeout
    response: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(64))
    target_id: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
