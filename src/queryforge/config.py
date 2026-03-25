"""Configuration for QueryForge."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Config:
    """Runtime configuration for the QueryForge engine."""

    dialect: str = "sqlite"          # sqlite | postgresql | mysql
    validate: bool = True            # run SQL safety checks
    log_level: str = "INFO"          # DEBUG, INFO, WARNING, ERROR
    llm_api_key: str | None = None   # optional LLM fallback key

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            dialect=os.getenv("QUERYFORGE_DIALECT", "sqlite"),
            validate=os.getenv("QUERYFORGE_VALIDATE", "true").lower() == "true",
            log_level=os.getenv("QUERYFORGE_LOG_LEVEL", "INFO"),
            llm_api_key=os.getenv("OPENAI_API_KEY"),
        )
