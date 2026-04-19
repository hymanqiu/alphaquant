from pathlib import Path

from pydantic_settings import BaseSettings


def _find_env_file() -> Path:
    """Locate .env by walking up from this file to the repo root."""
    current = Path(__file__).resolve().parent
    for _ in range(5):
        candidate = current / ".env"
        if candidate.exists():
            return candidate
        current = current.parent
    return Path(".env")


class Settings(BaseSettings):
    sec_user_agent: str = "AlphaQuant Research contact@alphaquant.dev"
    sec_base_url: str = "https://data.sec.gov"
    sec_ticker_url: str = "https://www.sec.gov/files/company_tickers.json"
    sec_rate_limit: float = 0.1  # seconds between requests (10 req/s)
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]
    fmp_api_key: str = ""
    fmp_base_url: str = "https://financialmodelingprep.com"

    model_config = {
        "env_prefix": "AQ_",
        "env_file": str(_find_env_file()),
    }


settings = Settings()
