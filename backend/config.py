from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    POSTGRES_USER: str = "satyavani_user"
    POSTGRES_PASSWORD: str = "change_me_letters_and_numbers_only"
    POSTGRES_DB: str = "satyavani_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = "postgresql+psycopg2://postgres:mySecretPass@localhost:5432/satyavani_db"

    # LLM Settings
    LLM_PROVIDER: str = "nvidia"  # nvidia | ollama | gemini | groq
    LLM_MODEL: str = "meta/llama-3.2-11b-vision-instruct"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

    # External APIs
    GOOGLE_FACTCHECK_API_KEY: Optional[str] = None

    # Embeddings & Retrieval
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIM: int = 1024
    SIMILARITY_THRESHOLD: float = 0.55
    RETRIEVAL_TOP_K: int = 6
    EVIDENCE_WINDOW_DAYS: int = 7

    # Ingestion & Maintenance
    ARTICLE_RETENTION_DAYS: int = 14
    INGEST_INTERVAL_MINUTES: int = 45

    # Backend & Rate Limiting
    BACKEND_URL: str = "http://localhost:8000"
    RATE_LIMIT_PER_MINUTE: int = 20

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
