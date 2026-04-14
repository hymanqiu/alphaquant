"""AlphaQuant FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.config import settings
from backend.services.market_data import market_data_client
from backend.services.sec_client import sec_client
from backend.services.ticker_resolver import ticker_resolver


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: pre-load ticker -> CIK mapping
    await ticker_resolver.load()
    yield
    # Shutdown: close HTTP clients
    await sec_client.close()
    await market_data_client.close()


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

app.include_router(router)
