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
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    # Narrative-tier model (thesis, reports). Fall back to the main LLM when empty.
    llm_narrative_api_key: str = ""
    llm_narrative_base_url: str = ""
    llm_narrative_model: str = ""
    # USD per 1M tokens for the primary provider (used for cost accounting logs).
    llm_price_input_per_mtok: float = 0.14
    llm_price_output_per_mtok: float = 0.28
    # Request-level defaults for the shared httpx client.
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 1
    # --- Cost guardrails (admin can override at runtime via /api/admin/settings) ---
    # Daily global LLM budget in USD. When exceeded, LLM calls raise and nodes
    # degrade gracefully.
    llm_daily_budget_usd: float = 5.0
    # Per-IP 24h LLM spend cap. Prevents a single client from burning the whole
    # global budget within their rate-limit quota.
    llm_per_ip_daily_budget_usd: float = 0.25
    # IP rate limits (count of requests per 24h per IP).
    rate_limit_analyze_per_ip_day: int = 3
    rate_limit_recalculate_per_ip_day: int = 30
    # Admin bearer token for /api/admin/*. Empty disables the admin endpoints.
    admin_token: str = ""
    # --- Phase 2: persistence + auth ---
    # PostgreSQL DSN, e.g. postgresql+asyncpg://alpha:alpha@localhost:5432/alphaquant
    database_url: str = ""
    # Default tier assigned to newly registered users.
    default_user_tier: str = "free"
    # JWT signing key for session tokens (HS256). MUST be set in production.
    jwt_secret: str = ""
    jwt_issuer: str = "alphaquant"
    jwt_access_ttl_seconds: int = 60 * 60 * 24 * 7  # 7 days
    # Magic-link configuration
    magic_link_secret: str = ""        # itsdangerous signing key
    magic_link_ttl_seconds: int = 60 * 15  # 15 min
    magic_link_base_url: str = ""      # frontend base, e.g. http://localhost:3000
    resend_api_key: str = ""           # optional; logs to stderr when empty
    resend_from_email: str = "AlphaQuant <noreply@alphaquant.dev>"
    # Google OAuth
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_url: str = ""  # e.g. http://localhost:8000/api/auth/google/callback
    finnhub_api_key: str = ""
    finnhub_base_url: str = "https://finnhub.io/api/v1"

    model_config = {
        "env_prefix": "AQ_",
        "env_file": str(_find_env_file()),
        "extra": "ignore",
    }


settings = Settings()
