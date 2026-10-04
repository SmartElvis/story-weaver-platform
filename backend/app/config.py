from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    SECRET_KEY: str

    LLM_BASE_URL: str
    LLM_API_KEY: str
    LLM_MODEL: str

    EMBEDDING_MODEL: str
    EMBEDDING_DIM: int = 1024

    RERANK_MODEL: str
    RECALL_TOP_N: int = 20
    RRF_K: int = 60

    # Directory used to spool uploaded style files so the ARQ worker (a separate
    # process) can read them. Should point at a volume shared by api + worker.
    FILE_STAGING_DIR: str = "/tmp/story_staging"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
