"""Configurações centralizadas do sistema."""

import secrets
from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, PostgresDsn, RedisDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações da aplicação carregadas de variáveis de ambiente."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
        hide_input_in_errors=True,
    )

    # App
    app_name: str = "Vibe Ponto"
    app_version: str = "0.1.0"
    app_public_url: str = "http://localhost:3000"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    secret_key: str = Field(default="", validation_alias=AliasChoices("SECRET_KEY", "JWT_SECRET_KEY"), repr=False)

    # API
    api_prefix: str = "/api/v1"
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
    ]
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
    ]

    # Database
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://dev:devpass@localhost:5432/vibe"
    )
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # Redis
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")
    celery_broker_url: str = "amqp://guest:guest@localhost:5672//"
    celery_result_backend: str = ""

    # JWT
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    mfa_encryption_key: str = Field(default="", repr=False)
    mfa_backup_codes_count: int = 10
    mfa_attempts_limit: int = 5
    mfa_attempts_window_seconds: int = 300

    # Storage (MinIO/S3)
    storage_endpoint: str = "http://localhost:9000"
    storage_public_endpoint: str = ""
    storage_access_key: str = "minio"
    storage_secret_key: str = "minio123"
    storage_bucket: str = "vibe-ponto"
    storage_use_ssl: bool = False
    storage_region: str = "us-east-1"
    upload_max_size_bytes: int = 10 * 1024 * 1024
    upload_image_max_size_bytes: int = 5 * 1024 * 1024

    # Reconhecimento Facial
    facial_provider: str = "mock"  # mock, local, aws, azure
    facial_threshold: float = 0.6  # Limiar de similaridade (0.0 a 1.0)

    # AWS (para Rekognition e S3 em produção)
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # Geofencing
    default_geofence_radius_meters: int = 100
    max_geofences_per_user: int = 5

    # AuditorIA
    auditoria_score_threshold: float = 0.75
    auditoria_auto_approve_threshold: float = 0.90

    # Observability
    structured_logging: bool = True
    log_level: str = "INFO"
    request_id_header: str = "X-Request-ID"
    metrics_enabled: bool = True
    otel_enabled: bool = False
    otel_service_name: str = "vibeponto-api"
    otel_exporter_otlp_endpoint: str = ""
    otel_exporter_otlp_headers: str = ""
    otel_traces_sampler: str = "parentbased_traceidratio"
    otel_traces_sampler_arg: str = "0.10"

    # LGPD
    data_retention_years: int = 5
    audit_log_retention_months: int = 36

    @model_validator(mode="after")
    def validate_security(self):
        if self.environment != "development":
            key = self.secret_key
            if (len(key) < 32 or len(set(key)) < 12
                    or any(word in key.lower() for word in ("change", "secret", "sua-chave", "example"))):
                raise ValueError("Configure SECRET_KEY with a randomly generated secret of at least 32 characters")
            if self.debug or "*" in self.cors_origins:
                raise ValueError("Disable DEBUG and configure explicit CORS origins outside development")
            if not self.mfa_encryption_key:
                raise ValueError("Configure MFA_ENCRYPTION_KEY outside development")
        elif not self.secret_key:
            # Only for a single local process; configure a shared key for multiple workers.
            self.secret_key = secrets.token_urlsafe(48)
        if not self.mfa_encryption_key:
            self.mfa_encryption_key = secrets.token_urlsafe(32)
        if not self.celery_result_backend:
            self.celery_result_backend = str(self.redis_url)
        return self


@lru_cache
def get_settings() -> Settings:
    """Retorna instância cacheada das configurações."""
    return Settings()


settings = get_settings()
