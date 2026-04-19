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
    logger.info("Starting Cellular Maze API...")
    await MongoClient.connect()
    logger.info("Cellular Maze API ready")

    yield

    # Shutdown
    logger.info("Shutting down Cellular Maze API...")
    await MongoClient.disconnect()
    logger.info("Cellular Maze API stopped")
