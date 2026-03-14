from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "content-engine-ai"
    APP_ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # MySQL Database
    SQLALCHEMY_DATABASE_URI: str = "mysql+pymysql://root:root@localhost:3306/content_engine"

    # Temporal Cloud
    TEMPORAL_TARGET: str = "bizzbuzzai.g8vlk.tmprl.cloud:7233"
    TEMPORAL_NAMESPACE: str = "bizzbuzzai.g8vlk"
    TEMPORAL_TASK_QUEUE: str = "content-engine-queue"
    TEMPORAL_TLS_KEY_FILE: str = "/certs/BizzBuzzAI.pkcs8.key"
    TEMPORAL_TLS_CERT_FILE: str = "/certs/BizzBuzzAI.crt"

    # Apify
    APIFY_TOKEN: str = ""

    # AI / LLM
    LLM_PROVIDER: str = "claude"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_DEEP_RESEARCH_MODEL: str = "o4-mini"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # AI Classification
    TOP_N_RESULTS: int = 10
    TRENDING_DATE_RANGE_DAYS: int = 7
    TOP_N_HASHTAGS: int = 10

    # Content Engine
    CONTENT_FINE_TUNING_URL: str = ""
    CONTENT_ENGINE_DEBUG: str = "off"

    @property
    def DATABASE_URL(self) -> str:
        return self.SQLALCHEMY_DATABASE_URI

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        return self.SQLALCHEMY_DATABASE_URI.replace("mysql+pymysql://", "mysql+aiomysql://", 1)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
