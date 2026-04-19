"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { ActionButtons } from "@/src/components/actions/ActionButtons";
import { HeatmapLegend } from "@/src/components/common/HeatmapLegend";
import { RouteBottomCard } from "@/src/components/common/RouteBottomCard";
import { Toast } from "@/src/components/common/Toast";
import { OnboardingTour } from "@/src/components/common/OnboardingTour";
import { FilterPanel } from "@/src/components/filters/FilterPanel";
import { MapContainer, type HeatmapFilterType } from "@/src/components/map/MapContainer";
import { SearchBar } from "@/src/components/search/SearchBar";
import { RouteSidebar } from "@/src/components/sidebar/RouteSidebar";
import { useGeolocation } from "@/src/hooks/useGeolocation";
import { useFastRoutes, useEarlyDeadZones, useHeatmap, useReroute, useRoutes, useTowerMarkers } from "@/src/hooks/useMapData";
import { useNetworkDetect } from "@/src/hooks/useNetworkDetect";
import { useTracking } from "@/src/hooks/useTracking";
import { useAuth } from "@/src/hooks/useAuth";
import { offlineService, mapboxSearchService, routeService, alertsService } from "@/src/services/api";
import type { TelecomMode, WeatherInfo, CallDropStats, RouteOption } from "@/src/types/route";

export default function Home() {
  const router = useRouter();
  const { isAuthenticated, hydrated } = useAuth();

  // Redirect once AuthProvider has read localStorage and user is not authenticated
  useEffect(() => {
    if (hydrated && !isAuthenticated) {
      router.replace("/login");
    }
  }, [hydrated, isAuthenticated, router]);
  // Search state -- empty on load
  const [source, setSource] = useState("");
  const [destination, setDestination] = useState("");
  const [searchTrigger, setSearchTrigger] = useState(0);
  const [hasSearched, setHasSearched] = useState(false);

  // Geocoded coordinate state (set when user selects a Nominatim result)
  const [sourceCoords, setSourceCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [destCoords, setDestCoords] = useState<{ lat: number; lng: number } | null>(null);

  // Filter state
  const [preference, setPreference] = useState(50);
  // Multi-ISP selection: [] = all networks, one = specific carrier, 2+ = multi-SIM mode
  const [selectedIsps, setSelectedIsps] = useState<string[]>([]);
  const [maxEtaFactor, setMaxEtaFactor] = useState(1.5);
  const [heatmapFilter, setHeatmapFilter] = useState<HeatmapFilterType>("none");

  // Derive telecom API param from selectedIsps
  const telecom: TelecomMode = useMemo(() => {
    if (selectedIsps.length === 0) return "all";
    if (selectedIsps.length === 1) {
      const id = selectedIsps[0];
      if (id === "jio" || id === "airtel" || id === "vi") return id;
      return "all"; // bsnl → all (backend does not score bsnl separately)
    }
    return "multi";
  }, [selectedIsps]);

  // UI state
  const [selectedRouteIndex, setSelectedRouteIndex] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [trackingActive, setTrackingActive] = useState(false);
  const [suggestedRoute, setSuggestedRoute] = useState<string>("");
  const [offlineReady, setOfflineReady] = useState(false);
  const [alertToast, setAlertToast] = useState<string | null>(null);
  const [weatherInfo, setWeatherInfo] = useState<WeatherInfo | null>(null);

  // Geolocation
  const geo = useGeolocation();

  // Network detection (uses both browser API and ISP detection)
  const networkInfo = useNetworkDetect();

  // Snapshot: source/dest resolved at search-time to prevent React Query cancels
  const [snapshotSrc, setSnapshotSrc] = useState("");
  const [snapshotDst, setSnapshotDst] = useState("");

  // Route query params -- source/dest are snapshotted, filters are reactive
  const queryParams = useMemo(
    () =>
      hasSearched && snapshotSrc && snapshotDst
        ? { source: snapshotSrc, destination: snapshotDst, preference, telecom, max_eta_factor: maxEtaFactor }
        : null,
    [hasSearched, snapshotSrc, snapshotDst, preference, telecom, maxEtaFactor, searchTrigger],
  );

  // -----------------------------------------------------------------------
  // Two-phase route loading:
  //   Phase 1 (fast): TomTom geometry only -- shows routes on map in ~1-2s
  //   Phase 2 (full): ML signal scoring, dead zones, weather -- enriches UI
  // -----------------------------------------------------------------------
  const { data: fastRouteData, isLoading: fastLoading } = useFastRoutes(
    snapshotSrc, snapshotDst, hasSearched,
  );
  const { data: routeData, isLoading: fullLoading } = useRoutes(
    queryParams ?? { source: "", destination: "", preference: 50, telecom: "all" },
  );
  const { data: heatmapData } = useHeatmap(heatmapFilter, heatmapFilter !== "none");
  const { data: towerMarkersData } = useTowerMarkers();
  const reroute = useReroute();

  // Use full routes if available, otherwise show fast routes (heuristic scoring)
  const hasFull = !!routeData?.routes?.length;

  // Early dead zone fetch -- triggered as soon as fast routes arrive, in parallel
  // with full ML scoring. Gives dead zone warnings ~5-10s faster than waiting for
  // the full route response which takes 30-60s.
  const earlyDzEnabled = hasSearched && !!snapshotSrc && !!snapshotDst && !!fastRouteData?.routes?.length && !hasFull;
  const { data: earlyDeadZoneData } = useEarlyDeadZones(snapshotSrc, snapshotDst, earlyDzEnabled);
  const displayRoutes: RouteOption[] = useMemo(() => {
    if (!hasSearched) return [];
    if (hasFull) return routeData.routes;
    // Convert fast routes to RouteOption shape with heuristic scores
    if (fastRouteData?.routes?.length) {
      return fastRouteData.routes.map((r) => ({
        name: r.name,
        eta: r.eta,
        distance: r.distance,
        path: r.path,
        signal_score: r.signal_score,
        weighted_score: r.weighted_score,
        zones: r.zones ?? [],
      }));
    }
    return [];
  }, [hasSearched, hasFull, routeData, fastRouteData]);

  const routes = displayRoutes;
  const recommendedRoute = (hasFull ? routeData?.recommended_route : fastRouteData?.recommended_route) ?? "";
  const routesLoading = hasSearched && !routes.length && (fastLoading || fullLoading);

  // Client-side preference re-ranking: instantly resort displayed routes when
  // the slider moves, giving immediate visual feedback on the map before the
  // new backend query resolves. Only applies when we have full ML-scored routes.
  const sortedRoutes = useMemo(() => {
    if (!hasFull || routes.length < 2) return routes;
    const maxEta = Math.max(...routes.map((r) => r.eta), 1);
    return [...routes].sort((a, b) => {
      const etaScoreA = ((maxEta - a.eta) / maxEta) * 100;
      const etaScoreB = ((maxEta - b.eta) / maxEta) * 100;
      const w = preference / 100;
      const scoreA = w * a.signal_score + (1 - w) * etaScoreA;
      const scoreB = w * b.signal_score + (1 - w) * etaScoreB;
      return scoreB - scoreA;
    });
  }, [routes, preference, hasFull]);

  // When preference changes and we have full routes, reset selection to new top route
  const prevPreferenceRef = useRef(preference);
  useEffect(() => {
    if (prevPreferenceRef.current !== preference && hasFull && sortedRoutes.length > 0) {
      setSelectedRouteIndex(0);
    }
    prevPreferenceRef.current = preference;
  }, [preference, hasFull, sortedRoutes]);

  const heatmapZones = heatmapFilter !== "none" ? (heatmapData?.zones ?? []) : [];
  const towerMarkers = towerMarkersData ?? [];

  const selectedRoute = sortedRoutes[selectedRouteIndex] ?? sortedRoutes[0];
  const trackingPath = selectedRoute?.path ?? [];
  const { position: trackingPosition, progress: trackingProgress } = useTracking(trackingPath, trackingActive);

  const etaDisplay = selectedRoute ? `${selectedRoute.eta} min` : "--";

  // Dynamic call drop stats: recomputed whenever selected route changes.
  // Compares the currently selected route's drop count vs the worst alternative.
  const callDropStats: CallDropStats | null = useMemo(() => {
    if (!sortedRoutes.length || !hasFull) return null;
    const selDrops = selectedRoute?.segment_drop_count ?? 0;
    const altDrops = sortedRoutes
      .filter((_, i) => i !== selectedRouteIndex)
      .map((r) => r.segment_drop_count ?? 0);
    const worstAlt = altDrops.length > 0 ? Math.max(...altDrops) : selDrops;
    const avoided = Math.max(0, worstAlt - selDrops);
    let message: string;
    if (avoided > 0) {
      message = `~${avoided} potential call drop(s) avoided by choosing this route`;
    } else if (selDrops === 0) {
      message = "No call drop risk on this route";
    } else {
      message = `${selDrops} weak segment(s) with potential call drop risk`;
    }
    return { drops_avoided: avoided, recommended_drops: selDrops, worst_alternative_drops: worstAlt, message };
  }, [routes, selectedRouteIndex, selectedRoute, hasFull]);

  // -----------------------------------------------------------------------
  // Periodic re-prediction during active navigation
  // -----------------------------------------------------------------------
  // Re-evaluates the route every ~20% of remaining distance (or every 2 min
  // minimum).  If an incident/accident changes conditions, the backend returns
  // a better route which is applied automatically with a toast.
  const lastRepredictProgress = useRef(0);
  const repredictTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    // Clean up timer when navigation stops
    if (!trackingActive) {
      if (repredictTimer.current) {
        clearInterval(repredictTimer.current);
        repredictTimer.current = null;
      }
      lastRepredictProgress.current = 0;
      return;
    }

    // Calculate re-prediction interval based on route ETA
    // Minimum 2 minutes, check every ~20% of total ETA
    const etaMinutes = selectedRoute?.eta ?? 10;
    const intervalMs = Math.max(2 * 60_000, (etaMinutes * 60_000 * 0.2));

    repredictTimer.current = setInterval(() => {
      // Only re-predict if we've moved at least 15% since last check
      const progressDelta = trackingProgress - lastRepredictProgress.current;
      if (progressDelta < 0.15) return;
      lastRepredictProgress.current = trackingProgress;

      // Skip if near the end (>90% done)
      if (trackingProgress > 0.9) return;

      // Get the current position on the path as the new source
      const currentPos = trackingPosition;
      if (!currentPos || !destination) return;

      const src = `@${currentPos.lat},${currentPos.lng}`;
      const dst = destCoords ? `@${destCoords.lat},${destCoords.lng}` : destination;

      routeService
        .getRoutes({
          source: src,
          destination: dst,
          preference: Math.min(preference + 10, 100),
          telecom,
          max_eta_factor: maxEtaFactor,
        })
        .then((newData) => {
          if (!newData?.routes?.length) return;
          const best = newData.routes[0];
          const current = selectedRoute;
          // Apply new route if signal score improved by >10 or ETA dropped by >15%
          if (
            !current ||
            best.signal_score > current.signal_score + 10 ||
            best.eta < current.eta * 0.85
          ) {
            setSnapshotSrc(src);
            setSnapshotDst(dst);
            setSearchTrigger((n) => n + 1);
            setHasSearched(true);
            setSelectedRouteIndex(0);
            setSuggestedRoute(best.name);
          }
        })
        .catch(() => {});
    }, intervalMs);

    return () => {
      if (repredictTimer.current) {
        clearInterval(repredictTimer.current);
        repredictTimer.current = null;
      }
    };
  }, [trackingActive, selectedRoute, trackingProgress, trackingPosition, destination, destCoords, preference, telecom, maxEtaFactor]);

  // -----------------------------------------------------------------------
  // Congestion / crowd alert polling during active navigation
  // -----------------------------------------------------------------------
  // Polls /api/alerts every 30 s. When a persistent high-congestion event
  // is detected on the route, a toast is shown and (if flagged) a reroute
  // is triggered automatically.
  const alertTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!trackingActive || !trackingPosition) {
      if (alertTimerRef.current) {
        clearInterval(alertTimerRef.current);
        alertTimerRef.current = null;
      }
      return;
    }

    const checkAlerts = () => {
      if (!trackingPosition) return;
      const upcomingPath = selectedRoute?.path ?? [];
      alertsService
        .getAlerts(trackingPosition.lat, trackingPosition.lng, upcomingPath)
        .then((res) => {
          if (res.alerts.length === 0) {
            setAlertToast(null);
            return;
          }
          const top = res.alerts[0];
          setAlertToast(top.message);
          // Auto-trigger reroute for on-route high-severity persistent events
          if (top.suggest_reroute && top.severity === "high" && !reroute.isPending) {
            const src = `@${trackingPosition.lat},${trackingPosition.lng}`;
            const dst = destCoords
              ? `@${destCoords.lat},${destCoords.lng}`
              : destination;
            reroute.mutate({
              source: src,
              destination: dst,
              current_zone: selectedRoute?.zones?.[0] ?? "",
              preference: Math.min(preference + 20, 100),
              telecom,
            });
          }
        })
        .catch(() => {});
    };

    checkAlerts();
    alertTimerRef.current = setInterval(checkAlerts, 30_000);

    return () => {
      if (alertTimerRef.current) {
        clearInterval(alertTimerRef.current);
        alertTimerRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trackingActive, trackingPosition, selectedRoute]);

  // Extract weather from route response
  useEffect(() => {
    if (routeData?.weather) setWeatherInfo(routeData.weather);
  }, [routeData]);

  // Offline cache alert: warn user when a dead zone is approaching
  const offlineAlert = selectedRoute?.offline_alerts?.[0]?.message ?? null;

  // Dead zone warning: prefer per-route data from full response, fall back to
  // early dead zone fetch (arrives ~5-10s after fast routes, before full ML scoring).
  const fullDeadZoneCount = selectedRoute?.carrier_dead_zones?.length ?? 0;
  const earlyDeadZoneCount = (!hasFull && earlyDeadZoneData) ? (earlyDeadZoneData.total_dead_zones ?? 0) : 0;
  const deadZoneCount = fullDeadZoneCount > 0 ? fullDeadZoneCount : earlyDeadZoneCount;
  const deadZoneWarning = deadZoneCount > 0
    ? `${deadZoneCount} dead zone(s) ahead where all carriers are weak`
    : null;

  // Toast priority: offline alert > crowd alert > dead zone > reroute > bad zone
  const badZoneWarning = selectedRoute?.bad_zones?.[0]?.warning ?? null;
  const toastMessage =
    offlineAlert ?? alertToast ?? deadZoneWarning ?? reroute.data?.advisory ?? badZoneWarning;
  const toastType =
    offlineAlert ? ("warning" as const)
    : alertToast ? ("warning" as const)
    : deadZoneWarning ? ("warning" as const)
    : reroute.data ? ("reroute" as const)
    : ("info" as const);

  // When geolocation resolves, reverse-geocode GPS coords to a readable name via Mapbox
  useEffect(() => {
    if (geo.location && !source) {
      const { lat, lng } = geo.location;
      mapboxSearchService
        .reverseGeocode(lat, lng)
        .then((name) => {
          if (name) {
            setSource(name);
            setSourceCoords({ lat, lng });
          }
        })
        .catch(() => {/* silently ignore */});
    }
  }, [geo.location, source]);

  const handleSearch = useCallback(() => {
    if (!source || !destination) return;
    const src = sourceCoords ? `@${sourceCoords.lat},${sourceCoords.lng}` : source;
    const dst = destCoords ? `@${destCoords.lat},${destCoords.lng}` : destination;
    setSnapshotSrc(src);
    setSnapshotDst(dst);
    setSearchTrigger((n) => n + 1);
    setHasSearched(true);
    setSidebarOpen(true);
    setSelectedRouteIndex(0);
    setSuggestedRoute("");
  }, [source, destination, sourceCoords, destCoords]);

  const handleRouteSelect = useCallback((index: number) => {
    setSelectedRouteIndex(index);
    setTrackingActive(false);
  }, []);

  const handleReroute = useCallback(() => {
    if (!source || !destination) return;
    const currentZone = routes[selectedRouteIndex]?.zones?.[0] ?? source;
    reroute.mutate({
      source,
      destination,
      current_zone: currentZone,
      preference: Math.min(preference + 20, 100),
      telecom,
    });
  }, [reroute, source, destination, preference, telecom, routes, selectedRouteIndex]);

  const handleStartNavigation = useCallback(() => {
    setTrackingActive(true);
    setSidebarOpen(false);
  }, []);

  const handleLocateMe = useCallback(() => {
    if (geo.location) {
      // Already have location, trigger reverse geocode via the effect
      setSource("");
      setTimeout(() => {
        // Force re-trigger
        geo.request();
      }, 50);
    } else {
      geo.request();
    }
  }, [geo]);

  const handleChatApply = useCallback(
    (chatSource: string, chatDest: string, pref: number, tel: TelecomMode) => {
      setSource(chatSource);
      setDestination(chatDest);
      setPreference(pref);
      // Map single TelecomMode from chatbot back to selectedIsps
      if (tel === "all" || tel === "multi") {
        setSelectedIsps([]);
      } else {
        setSelectedIsps([tel]);
      }
      setSnapshotSrc(chatSource);
      setSnapshotDst(chatDest);
      setSuggestedRoute("Suggested");
      setHasSearched(true);
      setSearchTrigger((n) => n + 1);
      setSidebarOpen(true);
      setSelectedRouteIndex(0);
    },
    [],
  );

  const handleDownloadOffline = useCallback(async () => {
    if (!source || !destination) return;
    try {
      const bundle = await offlineService.downloadBundle(
        source, destination, preference, telecom,
      );
      offlineService.saveToStorage(bundle);
      setOfflineReady(true);
    } catch {
      // Silently fail -- user can retry
    }
  }, [source, destination, preference, telecom]);

  // Handle pin drag from map
  const handlePinDrag = useCallback(
    (type: "source" | "destination", lat: number, lng: number) => {
      if (type === "source") {
        setSourceCoords({ lat, lng });
        // Reverse geocode to get name
        mapboxSearchService.reverseGeocode(lat, lng).then((name) => {
          if (name) setSource(name);
        }).catch(() => {});
      } else {
        setDestCoords({ lat, lng });
        mapboxSearchService.reverseGeocode(lat, lng).then((name) => {
          if (name) setDestination(name);
        }).catch(() => {});
      }
      // Re-trigger route search after short delay
      setTimeout(() => {
        setSearchTrigger((n) => n + 1);
        setHasSearched(true);
      }, 300);
    },
    [],
  );

  // While auth is hydrating or user is not authenticated, show nothing
  if (!hydrated || !isAuthenticated) {
    return null;
  }

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-white">
      {/* Full-screen map */}
      <MapContainer
        routes={sortedRoutes}
        selectedRouteIndex={selectedRouteIndex}
        heatmapZones={heatmapZones}
        towerMarkers={towerMarkers}
        onRouteClick={handleRouteSelect}
        trackingPosition={trackingPosition}
        userLocation={geo.location}
        heatmapFilter={heatmapFilter}
        onPinDrag={handlePinDrag}
      />

      {/* Search bar (top-left) */}
      <SearchBar
        source={source}
        destination={destination}
        onSourceChange={(v) => { setSource(v); if (!v) setSourceCoords(null); }}
        onDestinationChange={(v) => { setDestination(v); if (!v) setDestCoords(null); }}
        onSourceCoords={(lat, lon) =>
          setSourceCoords(lat !== null && lon !== null ? { lat, lng: lon } : null)
        }
        onDestCoords={(lat, lon) =>
          setDestCoords(lat !== null && lon !== null ? { lat, lng: lon } : null)
        }
        onSearch={handleSearch}
        onUseMyLocation={handleLocateMe}
        geoLoading={geo.loading}
      />

      {/* Signal vs Speed preference slider */}
      <div className="absolute top-[120px] left-4 z-[1000] w-[360px] glass-card rounded-xl px-3 pt-2.5 pb-3">
        <div className="flex justify-between items-center mb-2">
          <span className="text-[11px] text-white/45 font-medium">Speed</span>
          <span className="text-[11px] font-semibold text-cyan-400">
            {preference <= 25 ? "Fastest Route" : preference >= 75 ? "Best Signal" : "Balanced"}
          </span>
          <span className="text-[11px] text-white/45 font-medium">Signal</span>
        </div>
        <input
          type="range"
          min={0}
          max={100}
          value={preference}
          onChange={(e) => setPreference(Number(e.target.value))}
          className="w-full cursor-pointer accent-cyan-400"
        />
      </div>

      {/* Enriching indicator */}
      {/* {hasSearched && !hasFull && fullLoading && routes.length > 0 && (
        <div className="absolute top-[215px] left-4 z-[900] glass-card rounded-lg px-3 py-2 text-xs text-white/50 flex items-center gap-2 animate-fade-in">
          <span className="inline-block h-2 w-2 rounded-full bg-cyan-400 animate-pulse" />
          Running ML models for precise signal scores...
        </div>
      )} */}
      {/* Filter panel (top-right) */}
      <FilterPanel
        selectedIsps={selectedIsps}
        onIspsChange={setSelectedIsps}
        onChatApply={handleChatApply}
        detectedNetwork={networkInfo.type}
        heatmapFilter={heatmapFilter}
        onHeatmapFilterChange={setHeatmapFilter}
        weather={weatherInfo}
      />

      {/* Call-drop stats badge */}
      {callDropStats && callDropStats.drops_avoided > 0 && (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-[1000] glass-card rounded-xl px-4 py-2 text-sm whitespace-nowrap">
          <p className="font-medium text-emerald-400">{callDropStats.message}</p>
        </div>
      )}

      {/* Route sidebar (left) */}
      <RouteSidebar
        routes={sortedRoutes}
        selectedIndex={selectedRouteIndex}
        recommendedRoute={recommendedRoute}
        suggestedRoute={suggestedRoute ? recommendedRoute : ""}
        onSelect={handleRouteSelect}
        onClose={() => setSidebarOpen(false)}
        visible={sidebarOpen && sortedRoutes.length > 0}
        enriching={hasSearched && !hasFull && fullLoading}
        tracking={trackingActive}
        onStartNavigation={handleStartNavigation}
        onStopNavigation={() => setTrackingActive(false)}
      />

      {/* Bottom route card */}
      {selectedRoute && !sidebarOpen && (
        <RouteBottomCard
          route={selectedRoute}
          eta={etaDisplay}
          onStartNavigation={handleStartNavigation}
          suggested={!!suggestedRoute && selectedRoute.name === recommendedRoute}
        />
      )}

      {/* Heatmap color legend (bottom-right) -- only when a layer is active */}
      {heatmapFilter !== "none" && (
        <div className="absolute bottom-44 right-4 z-[900]">
          <HeatmapLegend filter={heatmapFilter} />
        </div>
      )}

      {/* Action buttons (bottom-right) */}
      <div id="action-btns">
        <ActionButtons
          tracking={trackingActive}
          loading={routesLoading || reroute.isPending}
          onToggleTracking={() => setTrackingActive((v) => !v)}
          onReroute={handleReroute}
          onLocateMe={handleLocateMe}
          geoLoading={geo.loading}
          geoError={geo.error}
        />
      </div>

      {/* Toast notifications */}
      <Toast message={toastMessage} type={toastType} />

      {/* Onboarding tour (after first signup) */}
      <OnboardingTour onComplete={() => {}} />
    </div>
  );
}
