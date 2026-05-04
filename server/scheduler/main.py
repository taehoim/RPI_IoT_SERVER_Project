"""Scheduler 진입점 — 단순 asyncio loop로 job 주기 실행.

cron 대신 in-process tick (Phase 2 단순화). Phase 5+에서 APScheduler 도입 검토.
systemd Type=notify + WatchdogSec=30 — sd_notify READY/WATCHDOG 자동.
"""

from __future__ import annotations

import asyncio
import signal

import structlog

from app.config import get_settings
from app.db import dispose_engine, get_sessionmaker
from app.utils import sd
from scheduler.jobs import command_timeout, offline_detector, partition_manager

log = structlog.get_logger("scheduler")


async def _tick(name: str, interval_sec: int, fn) -> None:
    Session = get_sessionmaker()
    log.info("job started", job=name, interval_sec=interval_sec)
    while True:
        try:
            async with Session() as session:
                await fn(session)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — keep loop alive
            log.error("job failed", job=name, error=str(exc))
        await asyncio.sleep(interval_sec)


async def _main() -> None:
    settings = get_settings()
    sd._setup_logging_basic(settings.log_level)
    sd.status("starting")

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    # 첫 partition_manager 1회 즉시 실행 → DEFAULT partition + N+1, N+2, N+3 보장
    Session = get_sessionmaker()
    try:
        async with Session() as session:
            await partition_manager.run(session)
    except Exception as exc:  # noqa: BLE001 — partition 실패해도 다른 job은 진행
        log.error("initial partition_manager failed", error=str(exc))

    tasks = [
        asyncio.create_task(_tick("offline_detector", 30, offline_detector.run)),
        asyncio.create_task(_tick("command_timeout", 10, command_timeout.run)),
        asyncio.create_task(_tick("partition_manager", 6 * 3600, partition_manager.run)),
        asyncio.create_task(sd.watchdog_loop(interval_sec=10), name="sd-watchdog"),
    ]

    sd.ready()
    sd.status("3 jobs running")

    await stop.wait()
    log.info("shutdown")
    sd.status("stopping")
    sd.stopping()
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await dispose_engine()


def run() -> None:
    """systemd ExecStart entry — `iot-scheduler`."""
    asyncio.run(_main())


if __name__ == "__main__":
    run()
