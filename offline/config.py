"""Runtime settings, read from OFFLINE_* environment variables or a .env file."""

from enum import StrEnum
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Mode(StrEnum):
    OFFLINE = "offline"
    CLOUD = "cloud"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OFFLINE_", env_file=".env", extra="ignore")

    mode: Mode = Mode.OFFLINE
    database_url: str = "postgresql://offline@localhost:5432/offline"
    ollama_url: str = "http://localhost:11434"
    chat_model: str = "llama3.1:8b"
    embed_model: str = "nomic-embed-text"
    embed_dim: int = 768
    anthropic_api_key: str = ""
    cloud_model: str = "claude-sonnet-5-5"
    sources_file: Path = Path("sources.yaml")
    data_dir: Path = Path("data")
    top_k: int = 6
    min_score: float = 0.35
    rate_limit_per_minute: int = 20

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def lock_file(self) -> Path:
        return self.data_dir / "sources.lock.json"

    @property
    def audit_file(self) -> Path:
        return self.data_dir / "audit.jsonl"

    @property
    def tokens_file(self) -> Path:
        return self.data_dir / "tokens.json"
