"""initial schema — 12 핵심 테이블 + telemetry 월별 partition

Revision ID: 0001
Revises:
Create Date: 2026-05-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ----- Identity -----
    op.create_table(
        "companies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("company_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "sites",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("address", sa.Text),
        sa.Column("latitude", sa.Float),
        sa.Column("longitude", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("keycloak_user_id", sa.Text, unique=True, nullable=False),
        sa.Column("email", sa.Text, unique=True, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "user_company_roles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False
        ),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "company_id", "role"),
    )

    op.create_table(
        "user_gateway_permissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("gateway_id", UUID(as_uuid=True), nullable=False),
        sa.Column("permission", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "gateway_id", "permission"),
    )

    # ----- Gateway / Profile -----
    op.create_table(
        "gateway_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("hardware_schema", JSONB, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "gateways",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("serial_number", sa.Text, unique=True, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column(
            "company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False
        ),
        sa.Column("site_id", UUID(as_uuid=True), sa.ForeignKey("sites.id")),
        sa.Column("gateway_profile_id", UUID(as_uuid=True), sa.ForeignKey("gateway_profiles.id")),
        sa.Column("status", sa.String(32), nullable=False, server_default="offline"),
        sa.Column("firmware_version", sa.String(64)),
        sa.Column("app_version", sa.String(64)),
        sa.Column("config_version", sa.Integer, server_default="0"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_gateways_company", "gateways", ["company_id"])
    op.create_index("ix_gateways_site", "gateways", ["site_id"])

    # ----- Sensor -----
    op.create_table(
        "sensor_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("vendor", sa.Text),
        sa.Column("model", sa.Text),
        sa.Column("protocol", sa.String(32), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("profile_schema", JSONB, nullable=False),
        sa.Column("enabled", sa.Boolean, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "sensor_channels",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("gateway_id", UUID(as_uuid=True), sa.ForeignKey("gateways.id"), nullable=False),
        sa.Column(
            "sensor_profile_id",
            UUID(as_uuid=True),
            sa.ForeignKey("sensor_profiles.id"),
            nullable=False,
        ),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("interface_name", sa.String(64), nullable=False),
        sa.Column("protocol", sa.String(32), nullable=False),
        sa.Column("address", sa.String(64)),
        sa.Column("slave_id", sa.Integer),
        sa.Column("polling_interval_sec", sa.Integer, server_default="10"),
        sa.Column("enabled", sa.Boolean, server_default=sa.true()),
        sa.Column("config", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_sensor_channels_gateway", "sensor_channels", ["gateway_id"])

    # ----- Actuator -----
    op.create_table(
        "actuator_channels",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("gateway_id", UUID(as_uuid=True), sa.ForeignKey("gateways.id"), nullable=False),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("actuator_type", sa.String(32), nullable=False),
        sa.Column("hardware_channel", sa.String(64), nullable=False),
        sa.Column("default_state", sa.String(8), nullable=False, server_default="off"),
        sa.Column("current_state", sa.String(16)),
        sa.Column("enabled", sa.Boolean, server_default=sa.true()),
        sa.Column("safety_config", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_actuator_channels_gateway", "actuator_channels", ["gateway_id"])

    # ----- Telemetry (월별 partition) -----
    op.execute(
        """
        CREATE TABLE telemetry (
            id BIGSERIAL,
            company_id UUID NOT NULL,
            site_id UUID,
            gateway_id UUID NOT NULL,
            sensor_channel_id UUID NOT NULL,
            measurement_key TEXT NOT NULL,
            ts TIMESTAMPTZ NOT NULL,
            value_double DOUBLE PRECISION,
            value_text TEXT,
            value_bool BOOLEAN,
            value_json JSONB,
            unit TEXT,
            quality TEXT,
            raw JSONB,
            PRIMARY KEY (id, ts)
        ) PARTITION BY RANGE (ts);
        """
    )
    op.execute(
        """
        CREATE INDEX ix_telemetry_gw_ch_ts
        ON telemetry (gateway_id, sensor_channel_id, ts DESC);
        """
    )

    # DEFAULT partition (마지막 안전망 — 다른 partition 없을 때 모든 row 수용)
    op.execute("CREATE TABLE telemetry_default PARTITION OF telemetry DEFAULT;")

    # 동적 partition 생성: 현재 월 + 다음 3개월 (Phase 2 안전 마진)
    # alembic upgrade 시점 기준. 추가 partition은 scheduler partition_manager가 자동.
    from datetime import datetime, timezone

    def _month_partition_sql(year: int, month: int) -> str:
        next_year, next_month = (year, month + 1) if month < 12 else (year + 1, 1)
        name = f"telemetry_{year}_{month:02d}"
        return (
            f"CREATE TABLE IF NOT EXISTS {name} PARTITION OF telemetry "
            f"FOR VALUES FROM ('{year}-{month:02d}-01') "
            f"TO ('{next_year}-{next_month:02d}-01');"
        )

    now = datetime.now(tz=timezone.utc)
    y, m = now.year, now.month
    for _ in range(4):  # 현재 + N+1, N+2, N+3
        op.execute(_month_partition_sql(y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1

    op.create_table(
        "telemetry_latest",
        sa.Column("gateway_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("sensor_channel_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("measurement_key", sa.String(64), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value_double", sa.Float),
        sa.Column("value_text", sa.Text),
        sa.Column("value_bool", sa.Boolean),
        sa.Column("value_json", JSONB),
        sa.Column("unit", sa.String(32)),
        sa.Column("quality", sa.String(32)),
    )

    # ----- Commands / Audit -----
    op.create_table(
        "commands",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("gateway_id", UUID(as_uuid=True), sa.ForeignKey("gateways.id"), nullable=False),
        sa.Column(
            "actuator_channel_id", UUID(as_uuid=True), sa.ForeignKey("actuator_channels.id")
        ),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("issued_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timeout_ms", sa.Integer, server_default="3000"),
        sa.Column("require_ack", sa.Boolean, server_default=sa.true()),
        sa.Column("reason", sa.Text),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("response", JSONB),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_commands_gw_status", "commands", ["gateway_id", "status"])
    op.create_index("ix_commands_expires", "commands", ["expires_at"])

    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(64)),
        sa.Column("target_id", sa.Text),
        sa.Column("payload", JSONB),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_user_ts", "audit_logs", ["user_id", "ts"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("commands")
    op.drop_table("telemetry_latest")
    # 동적 partition은 모두 cascade drop (parent drop 시 자동)
    op.execute("DROP TABLE IF EXISTS telemetry CASCADE")
    op.drop_table("actuator_channels")
    op.drop_table("sensor_channels")
    op.drop_table("sensor_profiles")
    op.drop_table("gateways")
    op.drop_table("gateway_profiles")
    op.drop_table("user_gateway_permissions")
    op.drop_table("user_company_roles")
    op.drop_table("users")
    op.drop_table("sites")
    op.drop_table("companies")
