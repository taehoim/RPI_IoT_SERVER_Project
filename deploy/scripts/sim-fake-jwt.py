#!/usr/bin/env python3
"""sim-fake-jwt.py — Sim 모드 API 호출용 unsigned JWT 발급.

Server는 KC_VERIFY_SIGNATURE=false일 때 signature를 검증하지 않으므로 unsigned token으로
충분. iss/aud/sub/exp만 맞춰주면 됨.

Production은 절대 사용 금지. Keycloak이 발급한 RS256 token만 허용.
"""

from __future__ import annotations

import base64
import json
import sys
import time

# Defaults — install-sim.sh의 server.env와 일치
ISS = "http://localhost:8080/realms/iot-sim"
AUD = "iot-backend"
SUB = "sim-admin"
EMAIL = "admin@sim.local"
NAME = "Sim Admin"
TTL_SEC = 3600


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def main() -> int:
    now = int(time.time())
    header = {"alg": "none", "typ": "JWT"}
    payload = {
        "iss": ISS,
        "aud": AUD,
        "sub": SUB,
        "email": EMAIL,
        "name": NAME,
        "iat": now,
        "exp": now + TTL_SEC,
        # realm_access.roles는 일부 backend 권한 검사에 사용될 수 있음
        "realm_access": {"roles": ["system_admin", "company_admin"]},
    }
    h = b64url(json.dumps(header, separators=(",", ":")).encode())
    p = b64url(json.dumps(payload, separators=(",", ":")).encode())
    # alg=none → signature 부분 비움
    sig = ""
    print(f"{h}.{p}.{sig}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
