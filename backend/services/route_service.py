"""Route service: orchestrates OSRM, ML signal prediction, scoring, and RL."""

import asyncio
from datetime import datetime, timezone

from backend.core.logging import logger
from backend.routing.osrm_client import OSRMClient, CandidateRoute
from backend.schemas.route_schema import RouteGeometryPoint, RouteResult
from backend.schemas.signal_schema import SignalPoint
from backend.services.scoring_service import (
    compute_drop_probability,
    compute_final_score,
    compute_signal_score,
    normalize_eta,
)
from backend.services.signal_client import SignalClient
from backend.services.rl_service import RLService
from backend.utils.geo import sample_points_along_route
from backend.utils.time_encoding import encode_time


class RouteService:
    """Main orchestrator: fetch routes -> predict signals -> score -> rank."""

    def __init__(
        self,
        osrm: OSRMClient,
        signal_client: SignalClient,
        rl_service: RLService | None = None,
    ) -> None:
        self._osrm = osrm
        self._signal = signal_client
        self._rl = rl_service

    async def get_ranked_routes(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        weight: float = 0.5,
        user_id: str | None = None,
    ) -> list[RouteResult]:
        # 1. Fetch candidate routes from OSRM
        candidates = await self._osrm.get_routes(
            origin_lat, origin_lon, dest_lat, dest_lon
        )
        if not candidates:
            logger.warning("No candidate routes returned")
            return []

        logger.info(f"Got {len(candidates)} candidate routes")

        # 2. Apply RL personalization to weight if user_id provided
        effective_weight = weight
        if user_id and self._rl:
            rl_sample = await self._rl.sample(user_id)
            # Blend user preference with RL-learned preference
            effective_weight = 0.6 * weight + 0.4 * rl_sample
            logger.info(
                f"RL-adjusted weight: {weight:.2f} -> {effective_weight:.2f}"
            )

        # 3. Batch ML predictions for all routes concurrently
        current_time = encode_time(datetime.now(timezone.utc))
        prediction_tasks = [
            self._predict_route_signals(route, current_time)
            for route in candidates
        ]
        all_predictions = await asyncio.gather(*prediction_tasks)

        # 4. Compute scores
        all_etas = [c.eta_seconds for c in candidates]
        results: list[RouteResult] = []

        for candidate, predictions in zip(candidates, all_predictions):
            signal_score = compute_signal_score(predictions)
            drop_prob = compute_drop_probability(predictions)
            eta_score = normalize_eta(candidate.eta_seconds, all_etas)
            final_score = compute_final_score(effective_weight, signal_score, eta_score)

            geometry = [
                RouteGeometryPoint(lat=lat, lon=lon)
                for lat, lon in candidate.geometry
            ]

            results.append(
                RouteResult(
                    eta=round(candidate.eta_seconds / 60.0, 1),
                    signal_score=round(signal_score, 1),
                    drop_prob=round(drop_prob, 3),
                    final_score=round(final_score, 4),
                    geometry=geometry,
                )
            )

        # 5. Rank by final_score descending
        results.sort(key=lambda r: r.final_score, reverse=True)

        logger.info(
            f"Ranked {len(results)} routes, top score={results[0].final_score}"
        )
        return results

    async def _predict_route_signals(
        self, route: CandidateRoute, current_time: float
    ):
        """Sample points along a route and batch-predict signal quality."""
        sampled = sample_points_along_route(route.geometry, interval_m=500.0)
        points = [
            SignalPoint(lat=lat, lon=lon, time=current_time)
            for lat, lon in sampled
        ]
        return await self._signal.predict_batch(points)

