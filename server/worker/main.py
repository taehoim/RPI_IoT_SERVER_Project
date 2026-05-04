"""Worker 진입점.

aiomqtt subscribe gw/+/+ → topic 별 handler dispatch → DB 저장.

systemd Type=notify + WatchdogSec=30 — sd_notify READY/WATCHDOG 자동 발행.
"""

from __future__ import annotations

import asyncio
import signal

import aiomqtt
import structlog

from app.config import get_settings
from app.db import dispose_engine, get_sessionmaker
from app.utils import sd
from worker.handlers import dispatch

log = structlog.get_logger("worker")


async def _consume(ready_event: asyncio.Event) -> None:
    settings = get_settings()
    Session = get_sessionmaker()
    log.info("starting worker", broker=f"{settings.mqtt_host}:{settings.mqtt_port}")

    async with aiomqtt.Client(
        hostname=settings.mqtt_host,
        port=settings.mqtt_port,
        username=settings.mqtt_username,
        password=settings.mqtt_password,
        keepalive=settings.mqtt_keepalive,
        identifier="iot-worker",
    ) as client:
        # `gw/+/#` covers gw/{id}/telemetry (3 segments) AND gw/{id}/command/response (4 segments).
        # `gw/+/+` would silently drop all 4-segment topics.
        await client.subscribe("gw/+/#", qos=1)
        log.info("subscribed", topic="gw/+/#")
        ready_event.set()
        async for msg in client.messages:
            try:
                async with Session() as session:
                    await dispatch(session, msg.topic.value, msg.payload)
            except Exception as exc:  # noqa: BLE001 — handler 자체에서 swallow하면 손실
                log.error("dispatch failed", topic=msg.topic.value, error=str(exc))


async def _main() -> None:
    settings = get_settings()
    sd._setup_logging_basic(settings.log_level)
    sd.status("starting")

    stop = asyncio.Event()
    ready_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    consumer = asyncio.create_task(_consume(ready_event), name="mqtt-consumer")
    wdog = asyncio.create_task(sd.watchdog_loop(interval_sec=10), name="sd-watchdog")

    try:
        await asyncio.wait_for(ready_event.wait(), timeout=60)
    except asyncio.TimeoutError:
        log.error("worker not ready in 60s — systemd will treat as failed start")
        consumer.cancel()
        wdog.cancel()
        return

    sd.ready()
    sd.status("subscribed gw/+/#")

    await stop.wait()
    log.info("shutdown signal received")
    sd.status("stopping")
    sd.stopping()
    consumer.cancel()
    wdog.cancel()
    for t in (consumer, wdog):
        try:
            await t
        except asyncio.CancelledError:
            pass
    await dispose_engine()


def run() -> None:
    """systemd ExecStart entry — `iot-worker`."""
    asyncio.run(_main())


if __name__ == "__main__":
    run()
