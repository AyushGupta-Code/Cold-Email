from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "local-recruiter-outreach"
    database_url: str = "sqlite:///./local_recruiter_outreach.db"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "mistral"
    ollama_temperature: float = 0.2
    searxng_base_url: str = ""
    semantic_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    semantic_reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    discovery_mode: str = "live"
    discovery_query_target_count: int = 30
    discovery_max_contacts: int = 5
    discovery_max_results_per_query: int = 8
    discovery_max_pages_to_fetch: int = 10
    discovery_max_extraction_chars: int = 2400
    discovery_bi_encoder_top_k: int = 12
    discovery_cross_encoder_top_k: int = 8
    discovery_request_delay_ms: int = 700
    discovery_use_playwright_fallback: bool = False
    discovery_log_progress: bool = True
    discovery_linkedin_only: bool = True
    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_sender_email: str = ""
    smtp_use_tls: bool = True
    allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ]
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
