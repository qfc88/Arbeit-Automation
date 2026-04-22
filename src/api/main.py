"""FastAPI entry point. Run with: uvicorn src.api.main:app --host 0.0.0.0 --port 8001"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Pool
from .routes import admin as admin_routes
from .routes import public as public_routes

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await Pool.get()
    try:
        yield
    finally:
        await Pool.close()


app = FastAPI(
    title="Deutsch DE Job API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — restrict to the home nginx origin in prod via env var.
import os

_origins = os.getenv("API_CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(public_routes.router, prefix="/api")
app.include_router(admin_routes.router, prefix="/api")
