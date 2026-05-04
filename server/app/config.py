"""Settings — pydantic-settings 기반.

환경 변수 우선 (12-factor). /etc/iot-platform/backend.env에서 systemd가 주입.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_name: str = "iot-gateway-backend"
    app_env: str = Field("dev", description="dev | staging | prod")
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://iot_user:iot_pw@localhost:5432/iot_platform"
    db_pool_size: int = 10
    db_max_overflow: int = 5

    # MQTT (Backend가 command publish용)
    mqtt_host: str = "127.0.0.1"
    mqtt_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_keepalive: int = 30
    mqtt_client_id: str = "iot-backend"

    # Keycloak — JWKS RS256 검증 (default ON, dev escape hatch는 below)
    kc_issuer: str = "http://localhost:8080/realms/iot-platform"
    kc_audience: str = "iot-backend"  # Keycloak client_id (audience claim)
    kc_jwks_url: str | None = None  # None이면 issuer + /protocol/openid-connect/certs 자동
    kc_verify_signature: bool = True  # Phase 2부터 ON. dev escape는 _validate_dev_unsafe()
    kc_jwks_cache_ttl_sec: int = 3600  # JWKS public key 캐시 (1시간)
    kc_jwks_fetch_timeout_sec: int = 5
    kc_allowed_algorithms: tuple[str, ...] = ("RS256",)
    kc_leeway_sec: int = 30  # 시계 동기 오차 허용

    # Command defaults
    command_default_expires_sec: int = 5
    command_default_timeout_ms: int = 3000

    # Offline detection
    offline_threshold_sec: int = 90  # heartbeat 30s × 3

    def jwks_url(self) -> str:
        """JWKS endpoint URL (auto-derive from issuer if not explicit)."""
        if self.kc_jwks_url:
            return self.kc_jwks_url
        return self.kc_issuer.rstrip("/") + "/protocol/openid-connect/certs"

    def validate_security(self) -> list[str]:
        """기동 시 보안 설정 검증. 위험한 조합이면 경고 list 반환."""
        warnings: list[str] = []
        if not self.kc_verify_signature:
            # dev escape: app_env=dev AND issuer가 localhost인 경우만 허용
            issuer_local = "localhost" in self.kc_issuer or "127.0.0.1" in self.kc_issuer
            if self.app_env != "dev" or not issuer_local:
                warnings.append(
                    "SECURITY: kc_verify_signature=False 는 app_env=dev AND localhost issuer 일 때만 허용. "
                    "현재 app_env=%s, issuer=%s — production 노출 위험."
                    % (self.app_env, self.kc_issuer)
                )
        return warnings


@lru_cache
def get_settings() -> Settings:
    return Settings()
