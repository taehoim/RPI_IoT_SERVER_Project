"""GET /health smoke test."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_health_returns_ok():
    # main.app은 lifespan에서 MQTT 연결을 시도하므로 mock 필요
    # 단순화: app 직접 import 후 health endpoint만 호출
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # lifespan 우회 — 직접 호출
        resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body
