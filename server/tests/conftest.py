"""pytest fixtures — 임시 SQLite + httpx test client.

Phase 2 단순화: SQLite in-memory (PostgreSQL 의존성 없이 unit test 가능).
실 PostgreSQL 검증은 deploy/scripts/install-server.sh 후 통합 테스트로.
"""

from __future__ import annotations

import os

# DATABASE_URL을 메모리 SQLite로 (테스트 격리)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("KC_VERIFY_SIGNATURE", "false")
os.environ.setdefault("MQTT_HOST", "127.0.0.1")
