"""datetime helper — 프로젝트 전역 timezone-aware UTC 강제.

전 코드베이스에서 `datetime.utcnow()` (naive) 금지.
대신 `from app.utils.time import utcnow` 사용.
PostgreSQL TIMESTAMPTZ + Python aware datetime 일관 보장.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """현재 시각 (timezone-aware UTC)."""
    return datetime.now(tz=timezone.utc)


def parse_iso8601(s: str | None) -> datetime:
    """ISO 8601 → aware datetime. None/빈 문자열은 utcnow() 반환.

    'Z' suffix 자동 처리 (Python <3.11 호환).
    """
    if not s:
        return utcnow()
    parsed = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        # naive 입력은 UTC로 가정 (gateway가 UTC publish 한다는 계약)
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
