"""Async client for the external ML signal prediction service.

Includes retry, timeout, graceful fallback, and in-memory caching.
"""

import time
from dataclasses import dataclass

import httpx

from backend.core.config import settings
from backend.core.logging import logger
from backend.schemas.signal_schema import (
    SignalPoint,
    SignalPrediction,
    SignalPredictionRequest,
    SignalPredictionResponse,
)


@dataclass
class _CacheEntry:
    prediction: SignalPrediction
    expires_at: float


class SignalClient:
    """Async client that calls POST {MODEL_URL}/predict for batch signal predictions."""

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (base_url or settings.MODEL_URL).rstrip("/")
        self._timeout = settings.ML_TIMEOUT_S
        self._cache: dict[tuple[float, float, float], _CacheEntry] = {}
        self._cache_ttl = settings.SIGNAL_CACHE_TTL_S
        self._cache_max = settings.SIGNAL_CACHE_MAX_SIZE

    async def predict_batch(
        self, points: list[SignalPoint]
    ) -> list[SignalPrediction]:
        """Predict signal for a batch of points. Uses cache + external ML call."""
        results: list[SignalPrediction | None] = [None] * len(points)
        uncached_indices: list[int] = []

        # Check cache first
        now = time.monotonic()
        for i, pt in enumerate(points):
            key = (round(pt.lat, 5), round(pt.lon, 5), round(pt.time, 0))
            entry = self._cache.get(key)
            if entry and entry.expires_at > now:
                results[i] = entry.prediction
            else:
                uncached_indices.append(i)

        if not uncached_indices:
            return results  # type: ignore[return-value]

        # Batch call for uncached points
        uncached_points = [points[i] for i in uncached_indices]
        predictions = await self._call_ml(uncached_points)

        # Merge results and update cache
        now = time.monotonic()
        for idx, pred in zip(uncached_indices, predictions):
            results[idx] = pred
            pt = points[idx]
            key = (round(pt.lat, 5), round(pt.lon, 5), round(pt.time, 0))
            self._cache[key] = _CacheEntry(
                prediction=pred,
                expires_at=now + self._cache_ttl,
            )

        self._evict_if_needed()
        return results  # type: ignore[return-value]

    async def _call_ml(
        self, points: list[SignalPoint], _retry: bool = True
    ) -> list[SignalPrediction]:
        """Call external ML service with one retry on failure."""
        url = f"{self._base_url}/predict"
        payload = SignalPredictionRequest(points=points).model_dump()

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                parsed = SignalPredictionResponse(**data)
                return parsed.predictions
        except (httpx.HTTPError, Exception) as exc:
            if _retry:
                logger.warning(f"ML call failed ({exc}), retrying once...")
                return await self._call_ml(points, _retry=False)
            logger.error(f"ML call failed after retry: {exc}")
            return self._fallback(len(points))

    @staticmethod
    def _fallback(count: int) -> list[SignalPrediction]:
        """Return neutral predictions when ML service is unavailable."""
        return [
            SignalPrediction(signal_strength=50.0, drop_probability=0.1)
            for _ in range(count)
        ]

    def _evict_if_needed(self) -> None:
        """Evict oldest entries if cache exceeds max size."""
        if len(self._cache) <= self._cache_max:
            return
        sorted_keys = sorted(self._cache, key=lambda k: self._cache[k].expires_at)
        to_remove = len(self._cache) - self._cache_max
        for key in sorted_keys[:to_remove]:
            del self._cache[key]
