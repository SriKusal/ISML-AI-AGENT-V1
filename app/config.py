"""Application configuration for ISML AI AGENT.

All settings are read from environment variables (or the .env file).
No secrets are ever hardcoded here.

New settings added:
  KNOWLEDGE_RETRIEVAL_MIN_RESOURCES  (ENH-006) — how many existing DB resources
      are considered "sufficient" before skipping discovery.
  KNOWLEDGE_RETRIEVAL_MIN_SCORE      (ENH-006) — minimum composite score (0-1)
      a resource must have to be counted as high-quality existing knowledge.
  QUALITY_THRESHOLD_EXCELLENT        (ENH-004) — composite score ≥ this → Excellent
  QUALITY_THRESHOLD_HIGH             (ENH-004) — composite score ≥ this → High Quality
  QUALITY_THRESHOLD_ACCEPTABLE       (ENH-004) — composite score ≥ this → Acceptable
      Below ACCEPTABLE → Review/Reject
  API_KEY_ENABLED                    (ENH-009) — set to "true" to require X-API-Key header
  API_KEY                            (ENH-009) — the expected API key value
"""

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"


def _load_env_file() -> None:
    if not ENV_FILE.exists():
        return

    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_env_file()


class Settings:
    # ---- core app ----
    APP_TITLE: str = os.getenv("APP_TITLE", "ISML AI AGENT")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() in {"1", "true", "yes", "on"}
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "*").split(",")
        if origin.strip()
    ]

    # ---- security (ENH-009) ----
    # Set API_KEY_ENABLED=true and API_KEY=<secret> in .env for production.
    # Defaults to disabled so local development works without configuration.
    API_KEY_ENABLED: bool = os.getenv("API_KEY_ENABLED", "false").lower() in {
        "1", "true", "yes", "on"
    }
    API_KEY: str = os.getenv("API_KEY", "")  # never logged

    # ---- knowledge retrieval (ENH-006) ----
    # Minimum number of high-quality existing resources required to skip discovery.
    KNOWLEDGE_RETRIEVAL_MIN_RESOURCES: int = int(
        os.getenv("KNOWLEDGE_RETRIEVAL_MIN_RESOURCES", "5")
    )
    # Minimum composite score (0-1) to count a resource as "high quality".
    KNOWLEDGE_RETRIEVAL_MIN_SCORE: float = float(
        os.getenv("KNOWLEDGE_RETRIEVAL_MIN_SCORE", "0.65")
    )

    # ---- quality thresholds (ENH-004) ----
    # All values are on the 0-1 scale used by ResourceScoringEngine.
    QUALITY_THRESHOLD_EXCELLENT: float = float(
        os.getenv("QUALITY_THRESHOLD_EXCELLENT", "0.90")
    )
    QUALITY_THRESHOLD_HIGH: float = float(
        os.getenv("QUALITY_THRESHOLD_HIGH", "0.80")
    )
    QUALITY_THRESHOLD_ACCEPTABLE: float = float(
        os.getenv("QUALITY_THRESHOLD_ACCEPTABLE", "0.70")
    )
    # Resources below ACCEPTABLE are flagged for review/reject.

    # ---- rate limiting (ENH-009) ----
    # Requests per minute allowed on expensive LLM endpoints.
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))

    # ---- response caching (ENH-007) ----
    # In-process LRU cache max entries. Set to 0 to disable.
    RESPONSE_CACHE_MAX_SIZE: int = int(os.getenv("RESPONSE_CACHE_MAX_SIZE", "128"))


settings = Settings()
