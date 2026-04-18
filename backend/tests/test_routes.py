"""Comprehensive test suite for SignalRoute clean-architecture backend.

Tests route_service, signal_client, rl_service, scoring, and API endpoints.
All external services (ML, OSRM, MongoDB) are mocked -- no external deps needed.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.db.models.rl_profile import RLProfile
from backend.db.repository.rl_repo import RLRepository
from backend.routing.osrm_client import OSRMClient, CandidateRoute
from backend.routing.polyline import decode_polyline, encode_polyline
from backend.schemas.route_schema import RouteRequest, Coordinates
from backend.schemas.signal_schema import SignalPoint, SignalPrediction
from backend.services.rl_service import RLService
from backend.services.route_service import RouteService
from backend.services.scoring_service import (
    compute_drop_probability,
    compute_final_score,
    compute_signal_score,
    compute_signal_variance,
    compute_continuity_score,
    compute_longest_stable_window,
    compute_stability_score,
    normalize_eta,
)
from backend.services.signal_client import SignalClient
from backend.utils.geo import haversine, sample_points_along_route
from backend.utils.time_encoding import cyclic_hour, encode_time


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_rl_repo():
    """In-memory RL repository mock."""
    store: dict[str, RLProfile] = {}

    repo = AsyncMock(spec=RLRepository)

    async def _get(user_id):
        return store.get(user_id)

    async def _upsert(profile):
        store[profile.user_id] = profile

    async def _get_or_create(user_id):
        if user_id not in store:
            p = RLProfile(user_id=user_id)
            store[user_id] = p
        return store[user_id]

    repo.get_profile = AsyncMock(side_effect=_get)
    repo.upsert_profile = AsyncMock(side_effect=_upsert)
    repo.get_or_create = AsyncMock(side_effect=_get_or_create)
    repo._store = store
    return repo


@pytest.fixture
def rl_service(mock_rl_repo):
    return RLService(mock_rl_repo)


@pytest.fixture
def mock_osrm():
    client = OSRMClient(use_mock=True)
    return client


@pytest.fixture
def mock_signal_client():
    client = SignalClient.__new__(SignalClient)
    client._base_url = "http://test:8001"
    client._timeout = 5.0
    client._cache = {}
    client._cache_ttl = 300
    client._cache_max = 1000

    async def _predict(points):
        return [
            SignalPrediction(
                signal_strength=70.0 + i * 5,
                drop_probability=0.05 + i * 0.01,
            )
            for i, _ in enumerate(points)
        ]

    client.predict_batch = AsyncMock(side_effect=_predict)
    return client


@pytest.fixture
def route_service(mock_osrm, mock_signal_client, rl_service):
    return RouteService(
        osrm=mock_osrm,
        signal_client=mock_signal_client,
        rl_service=rl_service,
    )


# ---------------------------------------------------------------------------
# Scoring Tests
# ---------------------------------------------------------------------------


class TestScoringService:
    def test_compute_signal_score_normal(self):
        preds = [
            SignalPrediction(signal_strength=80, drop_probability=0.1),
            SignalPrediction(signal_strength=60, drop_probability=0.2),
        ]
        assert compute_signal_score(preds) == 70.0

    def test_compute_signal_score_empty(self):
        assert compute_signal_score([]) == 50.0

    def test_compute_drop_probability_normal(self):
        preds = [
            SignalPrediction(signal_strength=80, drop_probability=0.1),
            SignalPrediction(signal_strength=60, drop_probability=0.3),
        ]
        assert abs(compute_drop_probability(preds) - 0.2) < 1e-9

    def test_compute_drop_probability_empty(self):
        assert compute_drop_probability([]) == 0.1

    def test_normalize_eta_fastest(self):
        assert normalize_eta(100, [100, 200, 300]) == 1.0

    def test_normalize_eta_slowest(self):
        assert normalize_eta(300, [100, 200, 300]) == 0.0

    def test_normalize_eta_middle(self):
        assert abs(normalize_eta(200, [100, 200, 300]) - 0.5) < 1e-9

    def test_normalize_eta_single_route(self):
        assert normalize_eta(150, [150]) == 1.0

    def test_normalize_eta_identical(self):
        assert normalize_eta(100, [100, 100]) == 1.0

    def test_final_score_pure_signal(self):
        score = compute_final_score(weight=1.0, signal_score=80.0, eta_score=0.2, stability_score=50.0)
        # weight * sig_norm + (1-weight) * eta + stability_bonus
        # 1.0 * 0.8 + 0.0 * 0.2 + (50/100)*0.1*1.0 = 0.8 + 0.05 = 0.85
        assert abs(score - 0.85) < 1e-9

    def test_final_score_pure_speed(self):
        score = compute_final_score(weight=0.0, signal_score=80.0, eta_score=0.9, stability_score=50.0)
        # 0.0 * 0.8 + 1.0 * 0.9 + 0 = 0.9 (no stability bonus when weight=0)
        assert abs(score - 0.9) < 1e-9

    def test_final_score_balanced(self):
        score = compute_final_score(weight=0.5, signal_score=60.0, eta_score=0.8, stability_score=50.0)
        # 0.5 * 0.6 + 0.5 * 0.8 + (50/100)*0.1*0.5 = 0.3 + 0.4 + 0.025 = 0.725
        expected = 0.5 * 0.6 + 0.5 * 0.8 + 0.5 * 0.1 * 0.5
        assert abs(score - expected) < 1e-9

    def test_signal_variance(self):
        preds = [
            SignalPrediction(signal_strength=80, drop_probability=0.1),
            SignalPrediction(signal_strength=60, drop_probability=0.2),
        ]
        var = compute_signal_variance(preds)
        # mean=70, var = ((80-70)^2 + (60-70)^2) / 2 = 100
        assert abs(var - 100.0) < 1e-9

    def test_continuity_score(self):
        preds = [
            SignalPrediction(signal_strength=70, drop_probability=0.1),
            SignalPrediction(signal_strength=70, drop_probability=0.1),
        ]
        # std = 0, continuity = 100
        assert compute_continuity_score(preds) == 100.0

    def test_longest_stable_window(self):
        preds = [
            SignalPrediction(signal_strength=60, drop_probability=0.1),
            SignalPrediction(signal_strength=30, drop_probability=0.5),
            SignalPrediction(signal_strength=55, drop_probability=0.1),
            SignalPrediction(signal_strength=70, drop_probability=0.05),
            SignalPrediction(signal_strength=80, drop_probability=0.02),
        ]
        assert compute_longest_stable_window(preds) == 3

    def test_stability_score(self):
        preds = [
            SignalPrediction(signal_strength=70, drop_probability=0.1),
            SignalPrediction(signal_strength=70, drop_probability=0.1),
        ]
        # continuity=100, stable_fraction=1.0 -> stability=100
        assert compute_stability_score(preds) == 100.0


# ---------------------------------------------------------------------------
# Signal Client Tests
# ---------------------------------------------------------------------------


class TestSignalClient:
    @pytest.mark.asyncio
    async def test_predict_batch_success(self):
        """Successful ML call returns correct predictions."""
        client = SignalClient(base_url="http://test:8001")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "predictions": [
                {"signal_strength": 85.0, "drop_probability": 0.05},
                {"signal_strength": 42.0, "drop_probability": 0.3},
            ]
        }

        with patch("httpx.AsyncClient") as mock_async:
            mock_ctx = AsyncMock()
            mock_ctx.post = AsyncMock(return_value=mock_response)
            mock_async.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_async.return_value.__aexit__ = AsyncMock(return_value=False)

            points = [
                SignalPoint(lat=12.9, lon=77.6, time=10.0),
                SignalPoint(lat=12.95, lon=77.65, time=10.0),
            ]
            results = await client.predict_batch(points)

        assert len(results) == 2
        assert results[0].signal_strength == 85.0
        assert results[1].drop_probability == 0.3

    @pytest.mark.asyncio
    async def test_predict_batch_fallback(self):
        """ML failure falls back to neutral predictions."""
        client = SignalClient(base_url="http://test:8001")

        with patch("httpx.AsyncClient") as mock_async:
            mock_ctx = AsyncMock()
            mock_ctx.post = AsyncMock(side_effect=Exception("Connection refused"))
            mock_async.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_async.return_value.__aexit__ = AsyncMock(return_value=False)

            points = [
                SignalPoint(lat=12.9, lon=77.6, time=10.0),
                SignalPoint(lat=12.95, lon=77.65, time=10.0),
            ]
            results = await client.predict_batch(points)

        assert len(results) == 2
        for r in results:
            assert r.signal_strength == 50.0
            assert r.drop_probability == 0.1

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """Second call with same points should use cache."""
        client = SignalClient(base_url="http://test:8001")

        call_count = 0

        async def _mock_call(points, _retry=True):
            nonlocal call_count
            call_count += 1
            return [
                SignalPrediction(signal_strength=75.0, drop_probability=0.08)
                for _ in points
            ]

        client._call_ml = _mock_call

        points = [SignalPoint(lat=12.9, lon=77.6, time=10.0)]

        r1 = await client.predict_batch(points)
        r2 = await client.predict_batch(points)

        assert call_count == 1  # Second call should hit cache
        assert r1[0].signal_strength == r2[0].signal_strength


# ---------------------------------------------------------------------------
# RL Service Tests
# ---------------------------------------------------------------------------


class TestRLService:
    @pytest.mark.asyncio
    async def test_sample_returns_valid_range(self, rl_service):
        for _ in range(50):
            val = await rl_service.sample("user_a")
            assert 0.0 <= val <= 1.0

    @pytest.mark.asyncio
    async def test_update_success_increments_alpha(self, rl_service, mock_rl_repo):
        profile = await rl_service.update("user_b", success=True)
        assert profile.alpha == 2.0
        assert profile.beta == 1.0

    @pytest.mark.asyncio
    async def test_update_failure_increments_beta(self, rl_service, mock_rl_repo):
        profile = await rl_service.update("user_c", success=False)
        assert profile.alpha == 1.0
        assert profile.beta == 2.0

    @pytest.mark.asyncio
    async def test_multiple_updates(self, rl_service):
        await rl_service.update("user_d", success=True)
        await rl_service.update("user_d", success=True)
        profile = await rl_service.update("user_d", success=False)
        assert profile.alpha == 3.0
        assert profile.beta == 2.0

    @pytest.mark.asyncio
    async def test_get_profile_creates_default(self, rl_service):
        profile = await rl_service.get_profile("new_user")
        assert profile.alpha == 1.0
        assert profile.beta == 1.0


# ---------------------------------------------------------------------------
# Route Service Tests
# ---------------------------------------------------------------------------


class TestRouteService:
    @pytest.mark.asyncio
    async def test_returns_ranked_routes(self, route_service):
        results = await route_service.get_ranked_routes(
            origin_lat=12.84, origin_lon=77.67,
            dest_lat=12.97, dest_lon=77.75,
            weight=0.5,
        )
        assert len(results) == 3
        # Should be sorted by final_score descending
        for i in range(len(results) - 1):
            assert results[i].final_score >= results[i + 1].final_score

    @pytest.mark.asyncio
    async def test_route_fields_valid(self, route_service):
        results = await route_service.get_ranked_routes(
            origin_lat=12.84, origin_lon=77.67,
            dest_lat=12.97, dest_lon=77.75,
            weight=0.5,
        )
        for r in results:
            assert r.eta > 0
            assert 0 <= r.signal_score <= 100
            assert 0 <= r.drop_prob <= 1
            assert len(r.geometry) >= 2

    @pytest.mark.asyncio
    async def test_with_user_id_applies_rl(self, route_service):
        results = await route_service.get_ranked_routes(
            origin_lat=12.84, origin_lon=77.67,
            dest_lat=12.97, dest_lon=77.75,
            weight=0.5,
            user_id="test_user",
        )
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_weight_zero_favors_speed(self, route_service):
        results = await route_service.get_ranked_routes(
            origin_lat=12.84, origin_lon=77.67,
            dest_lat=12.97, dest_lon=77.75,
            weight=0.0,
        )
        # With weight=0, fastest route (lowest ETA) should rank first
        assert results[0].eta <= results[-1].eta

    @pytest.mark.asyncio
    async def test_weight_one_favors_signal(self, route_service):
        results = await route_service.get_ranked_routes(
            origin_lat=12.84, origin_lon=77.67,
            dest_lat=12.97, dest_lon=77.75,
            weight=1.0,
        )
        # With weight=1, highest signal should rank first
        assert results[0].signal_score >= results[-1].signal_score


# ---------------------------------------------------------------------------
# API Tests
# ---------------------------------------------------------------------------


class TestAPI:
    @pytest.fixture
    def app(self):
        """Create app with mocked dependencies."""
        from backend.app.main import app as real_app
        return real_app

    @pytest.mark.asyncio
    async def test_health(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_root(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/")
        assert resp.status_code == 200
        assert "SignalRoute" in resp.json()["service"]

    @pytest.mark.asyncio
    async def test_route_valid_request(self, app, route_service):
        """POST /route with valid input returns routes."""
        from backend.dependencies.auth import get_route_service

        app.dependency_overrides[get_route_service] = lambda: route_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/route",
                    json={
                        "origin": {"lat": 12.84, "lon": 77.67},
                        "destination": {"lat": 12.97, "lon": 77.75},
                        "weight": 0.5,
                    },
                )
            assert resp.status_code == 200
            data = resp.json()
            assert "routes" in data
            assert len(data["routes"]) == 3
            for route in data["routes"]:
                assert "eta" in route
                assert "signal_score" in route
                assert "drop_prob" in route
                assert "final_score" in route
                assert "geometry" in route
        finally:
            app.dependency_overrides.pop(get_route_service, None)

    @pytest.mark.asyncio
    async def test_route_invalid_coordinates(self, app, route_service):
        """Invalid lat/lon returns 422."""
        from backend.dependencies.auth import get_route_service

        app.dependency_overrides[get_route_service] = lambda: route_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/route",
                    json={
                        "origin": {"lat": 999.0, "lon": 77.67},
                        "destination": {"lat": 12.97, "lon": 77.75},
                        "weight": 0.5,
                    },
                )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.pop(get_route_service, None)

    @pytest.mark.asyncio
    async def test_route_invalid_weight(self, app, route_service):
        """Weight > 1 returns 422 from Pydantic validation."""
        from backend.dependencies.auth import get_route_service

        app.dependency_overrides[get_route_service] = lambda: route_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/route",
                    json={
                        "origin": {"lat": 12.84, "lon": 77.67},
                        "destination": {"lat": 12.97, "lon": 77.75},
                        "weight": 5.0,
                    },
                )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.pop(get_route_service, None)

    @pytest.mark.asyncio
    async def test_route_missing_fields(self, app, route_service):
        from backend.dependencies.auth import get_route_service

        app.dependency_overrides[get_route_service] = lambda: route_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/api/v1/route", json={})
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.pop(get_route_service, None)


# ---------------------------------------------------------------------------
# Utility Tests
# ---------------------------------------------------------------------------


class TestGeoUtils:
    def test_haversine_same_point(self):
        assert haversine(12.9, 77.6, 12.9, 77.6) == 0.0

    def test_haversine_known_distance(self):
        # MG Road to Electronic City ~16.6 km
        d = haversine(12.9716, 77.5946, 12.8399, 77.6670)
        assert 15_000 < d < 18_000

    def test_sample_points_short_route(self):
        pts = [(12.9, 77.6), (12.91, 77.61)]
        sampled = sample_points_along_route(pts, interval_m=500)
        assert len(sampled) >= 2
        assert sampled[0] == pts[0]
        assert sampled[-1] == pts[-1]


class TestPolyline:
    def test_roundtrip(self):
        original = [(12.9716, 77.5946), (12.9279, 77.6271), (12.8399, 77.6670)]
        encoded = encode_polyline(original)
        decoded = decode_polyline(encoded)
        assert len(decoded) == len(original)
        for (a_lat, a_lon), (b_lat, b_lon) in zip(original, decoded):
            assert abs(a_lat - b_lat) < 1e-4
            assert abs(a_lon - b_lon) < 1e-4


class TestTimeEncoding:
    def test_encode_time_range(self):
        val = encode_time()
        assert 0 <= val < 24

    def test_cyclic_hour_midnight(self):
        s, c = cyclic_hour(0.0)
        assert abs(s) < 1e-9
        assert abs(c - 1.0) < 1e-9

    def test_cyclic_hour_noon(self):
        s, c = cyclic_hour(12.0)
        assert abs(s) < 1e-9
        assert abs(c - (-1.0)) < 1e-9


# ---------------------------------------------------------------------------
# OSRM Client Tests
# ---------------------------------------------------------------------------


class TestOSRMClient:
    @pytest.mark.asyncio
    async def test_mock_routes_returns_three(self):
        client = OSRMClient(use_mock=True)
        routes = await client.get_routes(12.84, 77.67, 12.97, 77.75)
        assert len(routes) == 3
        for r in routes:
            assert r.eta_seconds > 0
            assert r.distance_meters > 0
            assert len(r.geometry) >= 2
