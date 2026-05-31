"""
app/core/config.py
------------------
Central configuration loaded from environment variables / .env file.
All settings are strongly typed via Pydantic Settings v2.
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import AnyHttpUrl, Field, PostgresDsn, RedisDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Master settings object.  Every value can be overridden by a matching
    environment variable (case-insensitive) or a ```.env``` file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ──────────────────────────────────────────────
    # Application
    # ──────────────────────────────────────────────
    APP_NAME: str = "AI Digital Human Platform"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(64))

    # Derived helpers
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    # ──────────────────────────────────────────────
    # Server
    # ──────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1  # Increase in production (must be 1 when using in-process GPU models)
    RELOAD: bool = False
    ROOT_PATH: str = ""

    # ──────────────────────────────────────────────
    # CORS
    # ──────────────────────────────────────────────
    CORS_ORIGINS: list[AnyHttpUrl | str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"]
    )
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # ──────────────────────────────────────────────
    # Database (PostgreSQL)
    # ──────────────────────────────────────────────
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "avatar_user"
    POSTGRES_PASSWORD: str = "changeme"
    POSTGRES_DB: str = "avatar_db"
    DATABASE_URL: PostgresDsn | None = None
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 1800  # 30 min
    DATABASE_ECHO: bool = False

    @model_validator(mode="after")
    def assemble_db_url(self) -> "Settings":
        if self.DATABASE_URL is None:
            self.DATABASE_URL = PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_SERVER,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )
        return self

    # ──────────────────────────────────────────────
    # Redis
    # ──────────────────────────────────────────────
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None
    REDIS_DB: int = 0
    REDIS_URL: RedisDsn | None = None
    REDIS_MAX_CONNECTIONS: int = 50
    REDIS_SOCKET_TIMEOUT: int = 5
    REDIS_SOCKET_CONNECT_TIMEOUT: int = 5
    CACHE_TTL_DEFAULT: int = 3600  # 1 hour in seconds

    @model_validator(mode="after")
    def assemble_redis_url(self) -> "Settings":
        if self.REDIS_URL is None:
            auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
            self.REDIS_URL = RedisDsn(  # type: ignore[assignment]
                f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
            )
        return self

    # ──────────────────────────────────────────────
    # Celery
    # ──────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: list[str] = ["json"]
    CELERY_TIMEZONE: str = "UTC"
    CELERY_TASK_SOFT_TIME_LIMIT: int = 600   # 10 min
    CELERY_TASK_TIME_LIMIT: int = 900        # 15 min hard limit
    CELERY_MAX_RETRIES: int = 3
    CELERY_DEFAULT_RETRY_DELAY: int = 60     # seconds

    # ──────────────────────────────────────────────
    # JWT / Authentication
    # ──────────────────────────────────────────────
    JWT_SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(64))
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ISSUER: str = "avatar-platform"
    JWT_AUDIENCE: str = "avatar-users"

    # ──────────────────────────────────────────────
    # OAuth2 (Google / GitHub — add more as needed)
    # ──────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/github/callback"

    # ──────────────────────────────────────────────
    # MinIO (Object Storage)
    # ──────────────────────────────────────────────
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_REGION: str = "us-east-1"
    MINIO_BUCKET_AVATARS: str = "avatars"
    MINIO_BUCKET_VIDEOS: str = "videos"
    MINIO_BUCKET_AUDIO: str = "audio"
    MINIO_BUCKET_MODELS: str = "models"
    MINIO_BUCKET_TEMP: str = "temp"
    MINIO_PRESIGNED_EXPIRY: int = 3600  # 1 hour

    # ──────────────────────────────────────────────
    # Qdrant (Vector Database)
    # ──────────────────────────────────────────────
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str | None = None
    QDRANT_GRPC_PORT: int = 6334
    QDRANT_PREFER_GRPC: bool = False
    QDRANT_COLLECTION_AVATARS: str = "avatar_embeddings"
    QDRANT_COLLECTION_VOICES: str = "voice_embeddings"
    QDRANT_COLLECTION_KNOWLEDGE: str = "knowledge_base"
    QDRANT_VECTOR_SIZE: int = 512

    # ──────────────────────────────────────────────
    # OpenAI
    # ──────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL_CHAT: str = "gpt-4o"
    OPENAI_MODEL_EMBEDDING: str = "text-embedding-3-large"
    OPENAI_MAX_TOKENS: int = 4096
    OPENAI_TEMPERATURE: float = 0.7

    # ──────────────────────────────────────────────
    # Groq (FREE — https://console.groq.com)
    # 14,400 req/day · llama-3.3-70b-versatile
    # ──────────────────────────────────────────────
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # ──────────────────────────────────────────────
    # Google Gemini (FREE — https://aistudio.google.com)
    # 1,500 req/day · gemini-1.5-flash
    # ──────────────────────────────────────────────
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # ──────────────────────────────────────────────
    # DeepSeek (very cheap — https://platform.deepseek.com)
    # ──────────────────────────────────────────────
    DEEPSEEK_API_KEY: str = ""

    # ──────────────────────────────────────────────
    # GPU / Hardware
    # ──────────────────────────────────────────────
    USE_GPU: bool = True
    GPU_DEVICE_IDS: list[int] = [0]
    GPU_MEMORY_FRACTION: float = 0.8
    CUDA_VISIBLE_DEVICES: str = "0"
    FP16_ENABLED: bool = True          # Mixed precision inference
    BATCH_SIZE_DEFAULT: int = 1
    NUM_CPU_WORKERS: int = 4

    # ──────────────────────────────────────────────
    # Model Paths
    # ──────────────────────────────────────────────
    MODELS_BASE_DIR: Path = Path("/opt/models")

    # LivePortrait
    LIVEPORTRAIT_MODEL_DIR: Path = Path("/opt/models/LivePortrait")
    LIVEPORTRAIT_CHECKPOINT: str = "appearance_feature_extractor.safetensors"

    # MuseTalk
    MUSETALK_MODEL_DIR: Path = Path("/opt/models/MuseTalk")
    MUSETALK_CHECKPOINT: str = "musetalk.json"
    MUSETALK_WHISPER_MODEL: str = "tiny"

    # Wav2Lip
    WAV2LIP_MODEL_DIR: Path = Path("/opt/models/Wav2Lip")
    WAV2LIP_CHECKPOINT: str = "wav2lip_gan.pth"

    # Whisper (Speech-to-Text)
    WHISPER_MODEL_SIZE: Literal["tiny", "base", "small", "medium", "large", "large-v3"] = "base"
    WHISPER_DEVICE: str = "cuda"
    WHISPER_COMPUTE_TYPE: Literal["float16", "float32", "int8"] = "float16"
    WHISPER_DOWNLOAD_DIR: Path = Path("/opt/models/whisper")

    # XTTS-v2 (Text-to-Speech)
    XTTS_MODEL_DIR: Path = Path("/opt/models/XTTS-v2")
    XTTS_CONFIG_PATH: Path = Path("/opt/models/XTTS-v2/config.json")
    XTTS_VOCAB_PATH: Path = Path("/opt/models/XTTS-v2/vocab.json")
    XTTS_SPEAKER_EMBEDDING_DIR: Path = Path("/opt/models/XTTS-v2/speakers")

    # InsightFace / Face Analysis
    INSIGHTFACE_MODEL_DIR: Path = Path("/opt/models/insightface")
    INSIGHTFACE_DET_MODEL: str = "buffalo_l"

    # ──────────────────────────────────────────────
    # Storage Paths (local scratch / cache)
    # ──────────────────────────────────────────────
    STORAGE_BASE_DIR: Path = Path("/tmp/avatar-platform")
    UPLOAD_DIR: Path = Path("/tmp/avatar-platform/uploads")
    PROCESSED_DIR: Path = Path("/tmp/avatar-platform/processed")
    CACHE_DIR: Path = Path("/tmp/avatar-platform/cache")
    TEMP_DIR: Path = Path("/tmp/avatar-platform/tmp")

    # ──────────────────────────────────────────────
    # Upload Limits
    # ──────────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 500
    MAX_IMAGE_SIZE_MB: int = 20
    MAX_AUDIO_SIZE_MB: int = 100
    MAX_VIDEO_SIZE_MB: int = 500

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def max_image_size_bytes(self) -> int:
        return self.MAX_IMAGE_SIZE_MB * 1024 * 1024

    @property
    def max_audio_size_bytes(self) -> int:
        return self.MAX_AUDIO_SIZE_MB * 1024 * 1024

    @property
    def max_video_size_bytes(self) -> int:
        return self.MAX_VIDEO_SIZE_MB * 1024 * 1024

    # ──────────────────────────────────────────────
    # Rate Limiting
    # ──────────────────────────────────────────────
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_AUTH: str = "10/minute"
    RATE_LIMIT_UPLOAD: str = "20/minute"
    RATE_LIMIT_INFERENCE: str = "30/minute"
    RATE_LIMIT_WS: str = "5/minute"

    # ──────────────────────────────────────────────
    # Observability
    # ──────────────────────────────────────────────
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1
    SENTRY_PROFILES_SAMPLE_RATE: float = 0.1
    PROMETHEUS_ENABLED: bool = True
    PROMETHEUS_METRICS_PATH: str = "/metrics"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "json"
    LOG_FILE: Path | None = None

    # ──────────────────────────────────────────────
    # HeyGen (Cloud Avatar Video Generation)
    # ──────────────────────────────────────────────
    HEYGEN_API_KEY: str = ""
    HEYGEN_DEFAULT_AVATAR_ID: str = ""
    HEYGEN_DEFAULT_VOICE_ID: str = ""
    HEYGEN_TEST_MODE: bool = True   # Set False in production to avoid test watermark

    # ──────────────────────────────────────────────
    # Sync.so (Cloud Lip-Sync)
    # ──────────────────────────────────────────────
    SYNCSO_API_KEY: str = ""

    # ──────────────────────────────────────────────
    # Stripe (Billing)
    # ──────────────────────────────────────────────
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_STARTER: str = ""       # price_xxx from Stripe dashboard
    STRIPE_PRICE_PROFESSIONAL: str = ""
    STRIPE_PRICE_ENTERPRISE: str = ""

    # ──────────────────────────────────────────────
    # Email (SMTP)
    # ──────────────────────────────────────────────
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@daneshavaran.ai"
    SMTP_FROM_NAME: str = "Daneshavaran AI"
    SMTP_TLS: bool = True

    # ──────────────────────────────────────────────
    # Supported Languages
    # ──────────────────────────────────────────────
    SUPPORTED_LANGUAGES: list[str] = [
        "fa",  # Persian (Farsi) — primary language
        "en", "es", "fr", "de", "it", "pt", "nl",
        "ru", "zh", "ja", "ko", "ar", "hi", "tr",
        "pl", "sv", "da", "fi", "no", "cs",
    ]
    DEFAULT_LANGUAGE: str = "fa"

    # ──────────────────────────────────────────────
    # WebSocket
    # ──────────────────────────────────────────────
    WS_HEARTBEAT_INTERVAL: int = 30   # seconds
    WS_MAX_CONNECTIONS_PER_USER: int = 5
    WS_MESSAGE_MAX_SIZE: int = 1024 * 1024  # 1 MB

    # ──────────────────────────────────────────────
    # Pagination defaults
    # ──────────────────────────────────────────────
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()


# Convenience alias used across the codebase
settings: Settings = get_settings()
