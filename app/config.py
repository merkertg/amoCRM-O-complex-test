"""Конфигурация приложения.

Все настройки читаются из переменных окружения (или файла .env).
Секреты хранятся в SecretStr: их значение не попадает в repr/логи.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,  # пустая переменная = значение по умолчанию
        env_parse_none_str="none",  # LLM_TEMPERATURE=none -> параметр не отправляется
    )

    # --- Общие ---
    log_level: str = "INFO"
    cors_allow_origins: str = Field(
        default="",
        description="Список origin через запятую, например https://example.amocrm.ru",
    )

    # --- LLM (любой OpenAI-совместимый API) ---
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: SecretStr | None = None
    llm_model: str = "gpt-4.1-mini"
    llm_temperature: float | None = 0.2
    llm_max_tokens: int | None = None
    llm_json_mode: bool = True
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 2

    # --- База знаний ---
    knowledge_base_path: Path = PROJECT_ROOT / "data" / "knowledge_base.json"
    kb_top_k: int = 5

    # --- Ограничения входных данных и приватность ---
    max_message_chars: int = 4000
    max_history_chars: int = 12000
    max_history_messages: int = 30
    redact_pii_for_llm: bool = True

    # --- amoCRM ---
    amocrm_enabled: bool = False
    amocrm_base_url: str = Field(default="", description="https://<subdomain>.amocrm.ru")
    amocrm_access_token: SecretStr | None = None
    amocrm_client_id: str = Field(default="", description="ID интеграции (client_uuid в JWT)")
    amocrm_client_secret: SecretStr | None = None
    amocrm_webhook_secret: SecretStr | None = None
    amocrm_timeout_seconds: float = 10.0
    amocrm_history_limit: int = 20
    amocrm_message_ttl_hours: int = 24

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()
