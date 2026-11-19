from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "MovieAIProducer"
    app_env: str = "development"
    debug: bool = False

    public_base_url: str = "https://producer.apologets.com"

    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)

    log_level: str = "INFO"
    service_name: str = "movieai-producer"

    database_path: Path = Path("./data/movieai.db")
    database_url: str | None = None
    asset_storage_path: Path = Path("./data/assets")

    allowed_hosts: str = (
        "localhost,127.0.0.1,testserver,producer.apologets.com"
    )

    # Google OAuth 2.0 Credentials
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "https://producer.apologets.com/api/v1/auth/google/callback"

    # Frontend & Session Security
    frontend_url: str = "https://producer.apologets.com"
    jwt_secret_key: str = "temporary-dev-jwt-secret-key-32-chars-long"
    jwt_algorithm: str = "HS256"
    jwt_expires_in_hours: int = 168
    cookie_domain: str | None = None
    cookie_secure: bool = False
    cookie_name: str = "movieai_session"
    cookie_samesite: str = "lax"

    # Access Control: "whitelist" or "open"
    auth_access_mode: str = "whitelist"
    allowed_gmail_users: str = "needgenius19@gmail.com"

    @property
    def allowed_users_list(self) -> list[str]:
        return [
            email.strip().lower()
            for email in self.allowed_gmail_users.split(",")
            if email.strip()
        ]

    @property
    def async_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite+aiosqlite:///{self.database_path}"

    @property
    def allowed_host_list(self) -> list[str]:
        return [
            host.strip()
            for host in self.allowed_hosts.split(",")
            if host.strip()
        ]

@lru_cache
def get_settings() -> Settings:
    return Settings()
