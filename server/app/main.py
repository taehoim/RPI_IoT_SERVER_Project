"""FastAPI 진입점 — lifespan에 MQTT publisher 연결, sd_notify, routers 등록."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.config import get_settings
from app.db import dispose_engine
from app.mqtt_publisher import mqtt_lifespan
from app.routers import (
    actuator_channels,
    commands,
    companies,
    gateways,
    health,
    sensor_channels,
    sensor_profiles,
    sites,
    telemetry,
)
from app.utils import sd


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    sd._setup_logging_basic(settings.log_level)
    sd.status("starting")

    # 보안 설정 검증 — kc_verify_signature=False가 production에서 켜지면 명시 경고
    import structlog as _sl

    _slog = _sl.get_logger("startup")
    for warn in settings.validate_security():
        _slog.warning(warn)
        sd.status(f"WARNING: {warn[:60]}")

    # MQTT publisher 연결 (broker down이면 실패 → systemd가 재시도)
    async with mqtt_lifespan():
        # 모든 의존성 OK 후 systemd에 READY 발행 (= Type=notify active 전환)
        sd.ready()
        sd.status("active")

        # WatchdogSec=30 대응: 매 10초 WATCHDOG=1 emit
        wdog = asyncio.create_task(sd.watchdog_loop(interval_sec=10), name="sd-watchdog")
        try:
            yield
        finally:
            sd.status("stopping")
            sd.stopping()
            wdog.cancel()
            try:
                await wdog
            except asyncio.CancelledError:
                pass

    await dispose_engine()


app = FastAPI(
    title="IoT Gateway Server",
    version=__version__,
    description="Self-hosted IoT Gateway Fleet Management Platform — Backend API",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(companies.router, prefix="/api")
app.include_router(sites.router, prefix="/api")
app.include_router(gateways.router, prefix="/api")
app.include_router(sensor_profiles.router, prefix="/api")
app.include_router(sensor_channels.router, prefix="/api")
app.include_router(actuator_channels.router, prefix="/api")
app.include_router(commands.router, prefix="/api")
app.include_router(telemetry.router, prefix="/api")


def run() -> None:
    """systemd ExecStart entry — `iot-backend` 명령."""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        workers=1,  # systemd가 외부에서 다중 인스턴스 관리 가능
        access_log=True,
    )
