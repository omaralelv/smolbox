from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Smolbox"
    environment: str = "local"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://smolbox:smolbox@localhost:5432/smolbox"
    upload_dir: Path = Path("uploads")
    max_upload_bytes: int = 10 * 1024 * 1024
    allowed_attachment_types: list[str] = [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "application/xml",
        "text/xml",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
    ]
    cfdi_receiver_rfc: str | None = None
    textract_enabled: bool = False
    textract_store_raw_response: bool = False
    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    auto_create_schema: bool = False
    auth_token_secret: str = "local-dev-secret-change-me"
    auth_token_ttl_minutes: int = 8 * 60
    cognito_enabled: bool = False
    cognito_issuer: str | None = None
    cognito_app_client_id: str | None = None
    cognito_jwks_url: str | None = None
    cors_allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
