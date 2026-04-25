"""AlphaQuant FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from backend.api.admin import router as admin_router
from backend.api.auth import router as auth_router
from backend.api.routes import router
from backend.config import settings
from backend.services.db import close_engine, is_db_configured
from backend.services.finnhub_client import finnhub_client
from backend.services.llm import close_llm_client
from backend.services.market_data import market_data_client
from backend.services.sec_client import sec_client
from backend.services.ticker_resolver import ticker_resolver


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: pre-load ticker -> CIK mapping
    await ticker_resolver.load()
    yield
    # Shutdown: close HTTP clients + DB engine
    await sec_client.close()
    await market_data_client.close()
    await finnhub_client.close()
    await close_llm_client()
    if is_db_configured():
        await close_engine()


app = FastAPI(
    title="AlphaQuant",
    version="0.1.0",
    description="AI-powered investment research system using SEC EDGAR data",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SessionMiddleware powers authlib's OAuth state cookie. Required even when
# Google OAuth is disabled — the middleware is a no-op until used.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.jwt_secret or "dev-session-fallback-change-me",
    session_cookie="aq_oauth_state",
    max_age=60 * 10,  # 10 min — only needs to outlive the OAuth round-trip
    same_site="lax",
)

app.include_router(router)
app.include_router(admin_router)
app.include_router(auth_router)
