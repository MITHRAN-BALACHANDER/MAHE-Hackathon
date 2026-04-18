"""Application lifecycle management: startup and shutdown hooks."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from backend.core.logging import logger
from backend.db.base import MongoClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown."""
    # Startup
    logger.info("Starting SignalRoute API...")
    await MongoClient.connect()
    logger.info("SignalRoute API ready")

    yield

    # Shutdown
    logger.info("Shutting down SignalRoute API...")
    await MongoClient.disconnect()
    logger.info("SignalRoute API stopped")
