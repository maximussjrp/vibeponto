"""Configurações centralizadas do sistema."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações da aplicação carregadas de variáveis de ambiente."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "Vibe Ponto"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    secret_key: str = Field(default="CHANGE_ME_IN_PRODUCTION_123456789")
    
    # API
    api_prefix: str = "/api/v1"
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173", "*"]

    # Database
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://dev:devpass@localhost:5432/vibe"
    )
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # Redis
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")

    # JWT
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Storage (MinIO/S3)
    storage_endpoint: str = "localhost:9000"
    storage_access_key: str = "minio"
    storage_secret_key: str = "minio123"
    storage_bucket: str = "vibe-ponto"
    storage_use_ssl: bool = False
    storage_region: str = "us-east-1"

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

    # LGPD
    data_retention_years: int = 5
    audit_log_retention_months: int = 36


@lru_cache
def get_settings() -> Settings:
    """Retorna instância cacheada das configurações."""
    return Settings()


settings = get_settings()
