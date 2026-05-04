"""channel slug for wire identifier (gateway YAML ↔ server UUID 매핑)

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-04

Wire 정합성 fix: gateway YAML은 슬러그(`sensor-01`, `relay-vent`)로 채널을 식별하나
server는 UUID PK만 갖고 있어 telemetry value가 100% drop되던 문제 해결.

각 채널 테이블에 `slug` (text, NOT NULL) + UNIQUE(gateway_id, slug) 추가.
형식 제한: ^[A-Za-z0-9_-]+$, 길이 ≤ 64 (MQTT topic injection 가드 + gateway 측과 동일).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ----- sensor_channels -----
    op.add_column("sensor_channels", sa.Column("slug", sa.String(64), nullable=True))
    # 기존 row가 있다면 (Phase 0 dev에서 가능) UUID 앞 8자로 backfill
    op.execute(
        "UPDATE sensor_channels SET slug = substring(id::text, 1, 8) WHERE slug IS NULL"
    )
    op.alter_column("sensor_channels", "slug", nullable=False)
    op.create_check_constraint(
        "ck_sensor_channels_slug_format",
        "sensor_channels",
        r"slug ~ '^[A-Za-z0-9_-]+$'",
    )
    op.create_unique_constraint(
        "uq_sensor_channels_gateway_slug", "sensor_channels", ["gateway_id", "slug"]
    )

    # ----- actuator_channels -----
    op.add_column("actuator_channels", sa.Column("slug", sa.String(64), nullable=True))
    op.execute(
        "UPDATE actuator_channels SET slug = substring(id::text, 1, 8) WHERE slug IS NULL"
    )
    op.alter_column("actuator_channels", "slug", nullable=False)
    op.create_check_constraint(
        "ck_actuator_channels_slug_format",
        "actuator_channels",
        r"slug ~ '^[A-Za-z0-9_-]+$'",
    )
    op.create_unique_constraint(
        "uq_actuator_channels_gateway_slug", "actuator_channels", ["gateway_id", "slug"]
    )

    # ----- gateways.serial_number 형식 보강 -----
    # MQTT topic 식별자로 사용되므로 wildcard/separator 차단 + 길이 제한.
    op.create_check_constraint(
        "ck_gateways_serial_number_format",
        "gateways",
        r"serial_number ~ '^[A-Za-z0-9_-]+$' AND length(serial_number) <= 64",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_gateways_serial_number_format", "gateways", type_="check"
    )
    op.drop_constraint(
        "uq_actuator_channels_gateway_slug", "actuator_channels", type_="unique"
    )
    op.drop_constraint(
        "ck_actuator_channels_slug_format", "actuator_channels", type_="check"
    )
    op.drop_column("actuator_channels", "slug")
    op.drop_constraint(
        "uq_sensor_channels_gateway_slug", "sensor_channels", type_="unique"
    )
    op.drop_constraint(
        "ck_sensor_channels_slug_format", "sensor_channels", type_="check"
    )
    op.drop_column("sensor_channels", "slug")
