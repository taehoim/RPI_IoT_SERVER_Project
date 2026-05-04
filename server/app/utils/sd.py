"""systemd sd_notify 헬퍼 — Type=notify 서비스의 READY/WATCHDOG/STOPPING 발행.

systemd 비-환경에서는 silent no-op (NOTIFY_SOCKET 미설정 시).
sdnotify (https://github.com/bb4242/sdnotify) — pure Python, no compilation.
"""

from __future__ import annotations

import asyncio
import logging
import os

import structlog

try:
    import sdnotify

    _NOTIFIER: sdnotify.SystemdNotifier | None = sdnotify.SystemdNotifier()
except ImportError:  # pragma: no cover — sdnotify always installed in prod
    _NOTIFIER = None

log = structlog.get_logger("sd")


def _enabled() -> bool:
    """systemd notify socket 존재 시에만 호출 의미 있음."""
    return _NOTIFIER is not None and bool(os.environ.get("NOTIFY_SOCKET"))


def ready() -> None:
    """READY=1 — 서비스 초기화 완료, Type=notify가 active 전환."""
    if _enabled():
        _NOTIFIER.notify("READY=1")
        log.info("sd_notify ready")


def watchdog() -> None:
    """WATCHDOG=1 — WatchdogSec 내 발행해야 hang 판정 회피."""
    if _enabled():
        _NOTIFIER.notify("WATCHDOG=1")


def stopping() -> None:
    """STOPPING=1 — graceful shutdown 진입 알림."""
    if _enabled():
        _NOTIFIER.notify("STOPPING=1")


def status(text: str) -> None:
    """STATUS=... — systemctl status에 노출되는 단일 줄 메시지."""
    if _enabled():
        _NOTIFIER.notify(f"STATUS={text}")


async def watchdog_loop(interval_sec: int = 10) -> None:
    """주기적으로 WATCHDOG=1 emit. WatchdogSec=30이면 interval=10이 안전.

    asyncio.create_task로 백그라운드 실행. cancel하면 cleanup.
    """
    if not _enabled():
        # systemd 환경 아니면 무한 sleep만 (cancel 가능)
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            return

    log.info("watchdog loop started", interval_sec=interval_sec)
    try:
        while True:
            await asyncio.sleep(interval_sec)
            watchdog()
    except asyncio.CancelledError:
        log.info("watchdog loop stopped")
        raise


def _setup_logging_basic(level: str = "INFO") -> None:
    """structlog + stdlib 기본 설정 — main.py에서 호출."""
    logging.basicConfig(format="%(message)s", level=level)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )
