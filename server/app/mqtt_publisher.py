"""Backend가 command를 Gateway에 publish하는 MQTT 퍼블리셔.

aiomqtt context manager로 단일 client (FastAPI lifespan에서 관리).
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Any

import aiomqtt

from app.config import get_settings

log = logging.getLogger(__name__)

_client: aiomqtt.Client | None = None


@asynccontextmanager
async def mqtt_lifespan():
    """FastAPI app.lifespan에서 호출. Backend 살아있는 동안 MQTT 연결 유지."""
    global _client
    settings = get_settings()
    _client = aiomqtt.Client(
        hostname=settings.mqtt_host,
        port=settings.mqtt_port,
        username=settings.mqtt_username,
        password=settings.mqtt_password,
        keepalive=settings.mqtt_keepalive,
        identifier=settings.mqtt_client_id,
    )
    try:
        await _client.__aenter__()
        log.info("mqtt connected: %s:%d", settings.mqtt_host, settings.mqtt_port)
        yield
    finally:
        if _client is not None:
            try:
                await _client.__aexit__(None, None, None)
            except Exception as exc:  # noqa: BLE001 — best-effort shutdown
                log.warning("mqtt disconnect error: %s", exc)
            _client = None


async def publish(topic: str, payload: dict[str, Any], qos: int = 1, retain: bool = False) -> None:
    if _client is None:
        raise RuntimeError("mqtt client not initialized — check FastAPI lifespan")
    await _client.publish(topic, payload=json.dumps(payload), qos=qos, retain=retain)
