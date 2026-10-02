"""Hub settings from the environment (.env). Every variable is documented in .env.example.

Runtime-editable settings (persona, budget, safety texts...) live in the database
instead: see app/services/settings_service.py.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent

PROVIDER_DEFAULTS = {
    # provider -> (answer model, classifier model)
    "groq": ("llama-3.3-70b-versatile", "llama-3.1-8b-instant"),
    "anthropic": ("claude-sonnet-5-5", "claude-haiku-4-5-20251001"),
    "fake": ("fake-answer", "fake-classifier"),
}

# Env vars whose values must never reach a log line (app/logging_setup.py).
SECRET_FIELDS = (
    "secret_key",
    "admin_password",
    "llm_api_key",
    "wa_access_token",
    "wa_app_secret",
    "wa_verify_token",
    "meta_page_access_token",
    "meta_app_secret",
    "meta_verify_token",
    "smtp_password",
    "postgres_password",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    app_env: str = "dev"
    log_level: str = "INFO"
    timezone: str = "Asia/Jakarta"
    # Public URL of the API (webhook URLs shown in Settings) and the admin UI (CORS).
    api_base_url: str = "http://localhost:8000"
    web_base_url: str = "http://localhost:3000"
    cors_origins: str = ""  # extra comma-separated origins

    database_url: str = "postgresql+asyncpg://onti:onti@localhost:5432/onti"
    postgres_password: str = ""
    # Empty = no Redis: jobs run in-process and SSE uses an in-memory broker (tests).
    redis_url: str = ""

    secret_key: str = "change-me"
    cookie_secure: bool = False
    session_hours: int = 12
    admin_email: str = ""
    admin_password: str = ""
    admin_name: str = "Admin"

    llm_provider: str = "groq"  # groq | anthropic | fake
    llm_api_key: str = ""
    # Anthropic keys that aren't scoped to a workspace must name one per request.
    anthropic_workspace_id: str = ""
    llm_model_answer: str = ""
    llm_model_classifier: str = ""
    usd_to_idr: float = 16500.0
    llm_timeout_seconds: float = 45.0

    kb_dir: Path = ROOT / "kb"
    flags_file: Path = ROOT / "config" / "flags.yaml"

    wa_access_token: str = ""
    wa_phone_number_id: str = ""
    wa_business_account_id: str = ""
    wa_app_secret: str = ""
    wa_verify_token: str = ""
    wa_graph_version: str = "v25.0"
    graph_base_url: str = "https://graph.facebook.com"

    enable_messenger: bool = False
    enable_instagram: bool = False
    meta_page_id: str = ""
    meta_page_access_token: str = ""
    meta_ig_account_id: str = ""
    # Default to the WhatsApp app's values when Messenger/Instagram use the same Meta app.
    meta_app_secret: str = ""
    meta_verify_token: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_starttls: bool = True
    alert_emails: str = ""  # comma-separated; empty = all active admins and agents

    # Sending broadcast templates: messages per second (Cloud API allows far more;
    # kept low for a test number).
    broadcast_rate_per_second: float = 5.0
    broadcast_max_attempts: int = 3

    worker_max_jobs: int = 10
    test_mode: bool = Field(default=False, description="set by the test suite")

    @property
    def answer_model(self) -> str:
        return self.llm_model_answer or PROVIDER_DEFAULTS.get(self.llm_provider, ("", ""))[0]

    @property
    def classifier_model(self) -> str:
        return self.llm_model_classifier or PROVIDER_DEFAULTS.get(self.llm_provider, ("", ""))[1]

    @property
    def app_secret_meta(self) -> str:
        return self.meta_app_secret or self.wa_app_secret

    @property
    def verify_token_meta(self) -> str:
        return self.meta_verify_token or self.wa_verify_token

    @property
    def allowed_origins(self) -> list[str]:
        extra = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return list(dict.fromkeys([self.web_base_url, *extra]))

    @property
    def whatsapp_configured(self) -> bool:
        return bool(self.wa_access_token and self.wa_phone_number_id and self.wa_app_secret)

    def secret_values(self) -> list[str]:
        return [v for f in SECRET_FIELDS if (v := str(getattr(self, f, "") or "")) and len(v) >= 6]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
