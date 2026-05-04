"""MQTT topic dispatcher — gw/{serial}/{kind} → handler.

Wire 식별자는 슬러그(`gw/GW-DEV01/telemetry`). dispatcher가 serial → UUID 변환 후
기존 핸들러 시그니처 (`gateway_id: uuid.UUID`)로 위임.
"""

from __future__ import annotations

import json
import re

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from worker.handlers import command_response, heartbeat, state, telemetry as telemetry_h
from worker.handlers._lookups import gateway_uuid_by_serial

log = structlog.get_logger("worker.dispatch")

# Topic 형식: gw/{serial}/{kind}.
#   serial: ^[A-Za-z0-9_-]+$ (gateway YAML/DB와 동일 슬러그 형식)
#   kind:   [a-z_/]+ (예: telemetry, state, heartbeat, command/response, config/reported)
_TOPIC_RE = re.compile(r"^gw/(?P<serial>[A-Za-z0-9_-]+)/(?P<kind>[a-z_/]+)$")


async def dispatch(session: AsyncSession, topic: str, payload: bytes) -> None:
    m = _TOPIC_RE.match(topic)
    if not m:
        log.warning("unrecognized topic", topic=topic)
        return
    serial = m.group("serial")
    kind = m.group("kind")

    gateway_id = await gateway_uuid_by_serial(session, serial)
    if gateway_id is None:
        log.warning("unknown gateway serial", topic=topic, serial=serial)
        return

    try:
        body = json.loads(payload)
    except json.JSONDecodeError as exc:
        log.warning("payload not json", topic=topic, error=str(exc))
        return

    if kind == "telemetry":
        await telemetry_h.handle(session, gateway_id, body)
    elif kind == "state":
        await state.handle(session, gateway_id, body)
    elif kind == "heartbeat":
        await heartbeat.handle(session, gateway_id, body)
    elif kind == "command/response":
        await command_response.handle(session, gateway_id, body)
    elif kind in ("event", "ota/status", "config/reported"):
        # Phase 2-3 미구현 — log only
        log.info("unhandled topic kind", topic=topic, kind=kind)
    else:
        log.warning("unknown topic kind", topic=topic, kind=kind)
