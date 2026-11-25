from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_PROJECT_ROOT / ".env", ".env"),
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

    # Hugging Face Stable Diffusion 3.5 Large Configuration
    hf_token: str = ""
    sd35_default_steps: int = 28
    sd35_space_url: str = "https://stabilityai-stable-diffusion-3-5-large.hf.space"
    preview_storage_path: Path = Path("./data/assets/previews")

    # Dynamic Image Provider Switching & 9Router Configuration
    image_provider_default: str = "9router"
    image_fallback_chain: str = "9router,sd35_large_hf,mock"
    ninerouter_base_url: str = "http://127.0.0.1:8080/v1"
    ninerouter_api_key: str = "sk-3f8dbe69b93ed880-df5qur-b3936273"
    ninerouter_default_model: str = "gemini-3.1-flash-image"
    ninerouter_combo_models: str = "gemini-3.1-flash-image"
    ninerouter_timeout_seconds: float = 60.0
    ninerouter_max_retries: int = 2

    @property
    def effective_preview_storage_path(self) -> Path:
        if self.preview_storage_path.is_absolute():
            return self.preview_storage_path
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        return project_root / self.preview_storage_path

    @property
    def effective_ninerouter_base_url(self) -> str:
        return self.ninerouter_base_url or "http://127.0.0.1:8080/v1"

    @property
    def effective_ninerouter_api_key(self) -> str:
        return self.ninerouter_api_key or "sk-3f8dbe69b93ed880-df5qur-b3936273"

    @property
    def ninerouter_combo_list(self) -> list[str]:
        return [
            m.strip()
            for m in self.ninerouter_combo_models.split(",")
            if m.strip()
        ]

    @property
    def fallback_chain_list(self) -> list[str]:
        return [
            p.strip().lower()
            for p in self.image_fallback_chain.split(",")
            if p.strip()
        ]

    # LLM Screenplay Writer Configuration
    llm_base_url: str = "http://127.0.0.1:8080/v1"
    llm_api_key: str = "sk-3f8dbe69b93ed880-df5qur-b3936273"
    llm_model: str = "geminis"
    llm_timeout_seconds: float = 180.0
    openai_base_url: str | None = None
    openai_api_key: str | None = None

    @property
    def effective_llm_base_url(self) -> str:
        return self.openai_base_url or self.llm_base_url or "http://127.0.0.1:8080/v1"

    @property
    def effective_llm_api_key(self) -> str:
        return self.openai_api_key or self.llm_api_key or "sk-3f8dbe69b93ed880-df5qur-b3936273"

    # Polia AI Director RAG Bridge (Local Port 8765)
    polia_rag_enabled: bool = True
    polia_rag_url: str = "http://127.0.0.1:8765"
    polia_rag_token: str = ""
    polia_rag_timeout_sec: float = 1.5

    # Polia AI Screenwriter RAG Bridge (Local Port 8766)
    screenwriter_rag_enabled: bool = True
    screenwriter_rag_url: str = "http://127.0.0.1:8766"
    screenwriter_rag_timeout: float = 1.5

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
