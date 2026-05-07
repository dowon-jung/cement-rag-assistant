from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # === 외부 API 키 ===
    bok_api_key: str = ""
    naver_client_id: str = ""
    naver_client_secret: str = ""
    weather_api_key: str = ""

    # === LLM 백엔드 ===
    llm_backend: Literal["local", "bedrock", "anthropic"] = "local"
    anthropic_api_key: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-sonnet-4-5"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "gemma2:9b"
    vllm_host: str = "http://localhost:8001"

    # === 에어갭 모드 ===
    airgap_mode: bool = False

    # === 데이터베이스 ===
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "cement_rag"
    postgres_user: str = "cement"
    postgres_password: str = "cement_pass"

    redis_host: str = "localhost"
    redis_port: int = 6379

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    elasticsearch_host: str = "http://localhost:9200"

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j_pass"

    # === Kafka ===
    kafka_bootstrap_servers: str = "localhost:9092"

    # === 모델 경로 ===
    embedding_model_path: str = "jhgan/ko-sroberta-multitask"
    reranker_model_path: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # === 모니터링 ===
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "cement-rag"
    jaeger_host: str = "localhost"
    jaeger_port: int = 6831

    # === 앱 설정 ===
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
