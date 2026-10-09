"""One configuration boundary for local and future internal model servers."""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POC_", env_file=".env", extra="ignore")

    model_name: str = "granite4.2:3b"
    model_base_url: str = "http://127.0.0.1:11434/v1"
    model_api_key: str = "ollama"
    source_mode: Literal["live", "fixture"] = "live"
    source_timeout: float = Field(default=15, gt=0)
    run_timeout: float = Field(default=180, gt=0)
    max_search_results: int = Field(default=3, ge=1, le=5)
    max_documents: int = Field(default=4, ge=1, le=8)
    excerpt_chars: int = Field(default=1500, ge=200, le=3000)
    max_tool_calls: int = Field(default=8, ge=1, le=16)
    max_model_requests: int = Field(default=6, ge=1, le=12)
    history_turns: int = Field(default=3, ge=0, le=5)
    max_sessions: int = Field(default=30, ge=1, le=100)
