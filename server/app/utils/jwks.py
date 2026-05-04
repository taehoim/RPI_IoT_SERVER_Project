"""Keycloak JWKS fetch + cache + RSA public key resolve.

httpx로 JWKS endpoint 호출 → kid → RSA public key (jose JWK 형식) 캐시.
TTL 만료 시 lazy refresh. 실패 시 caller가 401.
"""

from __future__ import annotations

import time
from threading import Lock
from typing import Any

import httpx
import structlog

log = structlog.get_logger("jwks")


class JWKSCache:
    """Thread-safe JWKS public key 캐시 (kid → key dict)."""

    def __init__(self, jwks_url: str, ttl_sec: int = 3600, timeout_sec: int = 5) -> None:
        self._url = jwks_url
        self._ttl = ttl_sec
        self._timeout = timeout_sec
        self._keys: dict[str, dict[str, Any]] = {}
        self._fetched_at: float = 0.0
        self._lock = Lock()

    def _is_stale(self) -> bool:
        return time.time() - self._fetched_at > self._ttl

    def _fetch(self) -> None:
        log.info("fetching JWKS", url=self._url)
        try:
            resp = httpx.get(self._url, timeout=self._timeout)
            resp.raise_for_status()
            jwks = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.error("JWKS fetch failed", url=self._url, error=str(exc))
            raise

        keys = jwks.get("keys", [])
        if not isinstance(keys, list):
            raise ValueError(f"JWKS 'keys' must be list, got {type(keys).__name__}")
        new_map: dict[str, dict[str, Any]] = {}
        for k in keys:
            kid = k.get("kid")
            if kid:
                new_map[kid] = k
        self._keys = new_map
        self._fetched_at = time.time()
        log.info("JWKS cached", count=len(new_map))

    def get_key(self, kid: str) -> dict[str, Any] | None:
        """kid에 해당하는 JWK dict 반환. 없거나 stale이면 refresh."""
        with self._lock:
            if self._is_stale() or kid not in self._keys:
                try:
                    self._fetch()
                except Exception:  # noqa: BLE001 — caller가 401로 처리
                    return None
            return self._keys.get(kid)


_CACHE: JWKSCache | None = None


def get_cache(jwks_url: str, ttl_sec: int, timeout_sec: int) -> JWKSCache:
    """Process-wide singleton JWKS cache."""
    global _CACHE
    if _CACHE is None:
        _CACHE = JWKSCache(jwks_url, ttl_sec=ttl_sec, timeout_sec=timeout_sec)
    return _CACHE


def reset_cache_for_tests() -> None:
    """pytest fixture에서 cache reset."""
    global _CACHE
    _CACHE = None
