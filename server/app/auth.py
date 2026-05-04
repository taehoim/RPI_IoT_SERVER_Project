"""JWT 검증 + 사용자 컨텍스트.

Phase 2 보안 설계:
  - 기본: Keycloak JWKS fetch (httpx) → kid → RSA public key → RS256 verify
    (audience, issuer, exp, nbf 검증 포함)
  - dev escape: kc_verify_signature=False AND app_env=dev AND localhost issuer 만 허용
    (config.validate_security()가 위 3 조건 강제)
  - get_current_user: SELECT only (auto-upsert 제거 → DB pollution 방지). 사용자는
    별도 admin endpoint로 사전 provisioning. 또는 SQL seed.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import User
from app.utils import jwks


class TokenPayload:
    """디코드된 JWT payload — minimal facade."""

    def __init__(self, raw: dict):
        self.raw = raw
        self.sub: str = raw.get("sub", "")
        self.email: str = raw.get("email", "")
        self.preferred_username: str = raw.get("preferred_username", "")
        self.realm_roles: list[str] = (raw.get("realm_access") or {}).get("roles", [])

    def has_role(self, role: str) -> bool:
        return role in self.realm_roles


def _decode_jwt(token: str) -> dict:
    """RS256 verify (default) 또는 dev escape decode-only."""
    settings = get_settings()

    if not settings.kc_verify_signature:
        # dev escape — config.validate_security()가 이미 issuer/env 강제
        try:
            return jwt.decode(
                token,
                key="",
                options={"verify_signature": False, "verify_aud": False, "verify_iss": False},
            )
        except JWTError as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token") from exc

    # production path: JWKS RS256 verify
    try:
        unverified = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "malformed token header") from exc
    kid = unverified.get("kid")
    if not kid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token missing kid")

    cache = jwks.get_cache(
        settings.jwks_url(),
        ttl_sec=settings.kc_jwks_cache_ttl_sec,
        timeout_sec=settings.kc_jwks_fetch_timeout_sec,
    )
    public_key = cache.get_key(kid)
    if public_key is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"unknown kid {kid}")

    try:
        return jwt.decode(
            token,
            key=public_key,
            algorithms=list(settings.kc_allowed_algorithms),
            audience=settings.kc_audience,
            issuer=settings.kc_issuer,
            options={
                "verify_signature": True,
                "verify_aud": True,
                "verify_iss": True,
                "verify_exp": True,
                "verify_nbf": True,
            },
        )
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {exc}") from exc


async def get_token(
    authorization: Annotated[str | None, Header(description="Bearer <jwt>")] = None,
) -> TokenPayload:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    raw = _decode_jwt(authorization.removeprefix("Bearer ").strip())
    return TokenPayload(raw)


async def get_current_user(
    token: Annotated[TokenPayload, Depends(get_token)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """JWT sub로 user lookup. 없으면 401 (auto-upsert 제거 — DB pollution 방지).

    User provisioning은 admin endpoint 또는 SQL seed로 사전 등록.
    Keycloak event hook으로 사용자 가입 시 자동 user row 생성도 가능 (Phase 4+).
    """
    if not token.sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "no sub claim")
    res = await session.execute(select(User).where(User.keycloak_user_id == token.sub))
    user = res.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"user {token.sub} not provisioned in iot_platform DB — contact admin",
        )
    return user
