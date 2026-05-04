"""Telemetry partition 관리.

매 6시간마다 + scheduler 부팅 시 1회 즉시:
  - 현재 + N+1, N+2, N+3 월 partition CREATE IF NOT EXISTS (안전 마진 4개월)
  - DEFAULT partition은 alembic이 이미 만들어둠 (이 job 실패해도 데이터 손실 없음)
  - retention 기간 지난 oldest partition DROP (Phase 6+ 정책 결정 후 활성)
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger("scheduler.partition_manager")

LOOKAHEAD_MONTHS = 4  # 현재 + 3개월 ahead


def _month_partition_sql(year: int, month: int) -> tuple[str, str]:
    next_year, next_month = (year, month + 1) if month < 12 else (year + 1, 1)
    name = f"telemetry_{year}_{month:02d}"
    sql = (
        f"CREATE TABLE IF NOT EXISTS {name} PARTITION OF telemetry "
        f"FOR VALUES FROM ('{year}-{month:02d}-01') "
        f"TO ('{next_year}-{next_month:02d}-01');"
    )
    return name, sql


async def run(session: AsyncSession) -> None:
    now = datetime.now(tz=timezone.utc)
    y, m = now.year, now.month
    ensured: list[str] = []
    for _ in range(LOOKAHEAD_MONTHS):
        name, sql = _month_partition_sql(y, m)
        await session.execute(text(sql))
        ensured.append(name)
        m += 1
        if m > 12:
            m = 1
            y += 1
    await session.commit()
    log.info("partitions ensured", count=len(ensured), partitions=ensured)
