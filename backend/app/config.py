from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables only."""

    model_config = SettingsConfigDict(extra="ignore")

    database_url: str = ""
    redis_url: str = ""
    s3_endpoint_url: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "maestro-especiais"
    s3_region: str = "us-east-1"
    # Development only: create the bucket on startup if it does not exist.
    s3_create_bucket: bool = False
    # Development only: simulated users chosen with the X-Dev-User header. OIDC replaces it (D6).
    dev_auth: bool = False
    max_upload_bytes: int = 200 * 1024 * 1024
    # LLM (SPEC 6.1): model names only here, from the environment; fake for tests and offline
    llm_provider: str = "gemini"  # gemini | fake
    gemini_api_key: str = ""
    llm_model_drafting: str = ""
    llm_model_extraction: str = ""
    llm_model_embedding: str = ""
    llm_rpm: int = 10  # requests per minute (free quota)
    llm_rpd: int = 200  # requests per day
    llm_max_retries: int = 4  # on 429/503
    llm_backoff_s: float = 2.0  # first wait, doubled at each retry
    llm_timeout_s: float = 60.0
    # Fernet key for the technicians' profiles (make env generates one)
    profile_encryption_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
