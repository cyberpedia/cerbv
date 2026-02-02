"""
Cerberus CTF Platform - Application Configuration
Pydantic Settings with environment variable support
"""

from functools import lru_cache
from typing import List, Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # ==========================================================================
    # Application
    # ==========================================================================
    app_name: str = "Cerberus CTF Platform"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "production"
    
    # ==========================================================================
    # Server
    # ==========================================================================
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    
    # ==========================================================================
    # Database
    # ==========================================================================
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://cerberus_admin:password@localhost:5432/cerberus"
    )
    database_pool_size: int = 20
    database_max_overflow: int = 10
    database_pool_timeout: int = 30
    database_echo: bool = False
    
    # ==========================================================================
    # Redis
    # ==========================================================================
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")
    redis_password: str = ""
    redis_pool_size: int = 10
    
    # ==========================================================================
    # Security
    # ==========================================================================
    secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    
    # Password hashing (Argon2id)
    argon2_time_cost: int = 2
    argon2_memory_cost: int = 65536
    argon2_parallelism: int = 4
    
    # Request signing
    require_request_signing: bool = False
    request_signing_key: str = ""
    
    # ==========================================================================
    # CORS
    # ==========================================================================
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    
    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    # ==========================================================================
    # Rate Limiting
    # ==========================================================================
    rate_limit_enabled: bool = True
    rate_limit_default: str = "100/minute"
    rate_limit_auth: str = "10/minute"
    rate_limit_submit: str = "30/minute"
    
    # ==========================================================================
    # Logging
    # ==========================================================================
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "json"
    
    # ==========================================================================
    # Feature Flags
    # ==========================================================================
    feature_flag_cache_ttl: int = 60  # seconds
    
    # ==========================================================================
    # MinIO / Object Storage
    # ==========================================================================
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_secure: bool = False
    minio_bucket_challenges: str = "challenge-files"
    minio_bucket_backups: str = "backups"
    
    # ==========================================================================
    # CTF Settings
    # ==========================================================================
    ctf_name: str = "Cerberus CTF"
    ctf_start_time: str | None = None
    ctf_end_time: str | None = None
    flag_prefix: str = "CERB{"
    flag_suffix: str = "}"
    
    # ==========================================================================
    # Anti-cheat
    # ==========================================================================
    anticheat_enabled: bool = True
    anticheat_flag_sharing_detection: bool = True
    anticheat_ip_correlation: bool = True
    anticheat_submission_velocity_limit: int = 10  # per minute


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
