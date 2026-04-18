"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ActionButtons } from "@/src/components/actions/ActionButtons";
import { RouteBottomCard } from "@/src/components/common/RouteBottomCard";
import { Toast } from "@/src/components/common/Toast";
import { WeatherBadge } from "@/src/components/common/WeatherBadge";
import { OnboardingTour } from "@/src/components/common/OnboardingTour";
import { FilterPanel } from "@/src/components/filters/FilterPanel";
import { MapContainer, type HeatmapFilterType } from "@/src/components/map/MapContainer";
import { SearchBar } from "@/src/components/search/SearchBar";
import { RouteSidebar } from "@/src/components/sidebar/RouteSidebar";
import { useGeolocation } from "@/src/hooks/useGeolocation";
import { useHeatmap, useReroute, useRoutes, useTowerMarkers } from "@/src/hooks/useMapData";
import { useNetworkDetect } from "@/src/hooks/useNetworkDetect";
import { useTracking } from "@/src/hooks/useTracking";
import { offlineService, geocodeService, reverseGeocodeService, routeService, alertsService } from "@/src/services/api";
import type { TelecomMode, WeatherInfo, CallDropStats } from "@/src/types/route";

export default function Home() {
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
  const [telecom, setTelecom] = useState<TelecomMode>("all");
  const [maxEtaFactor, setMaxEtaFactor] = useState(1.5);
  const [heatmapFilter, setHeatmapFilter] = useState<HeatmapFilterType>("signal");

  // UI state
  const [selectedRouteIndex, setSelectedRouteIndex] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [trackingActive, setTrackingActive] = useState(false);
  const [suggestedRoute, setSuggestedRoute] = useState<string>("");
  const [offlineReady, setOfflineReady] = useState(false);
  const [alertToast, setAlertToast] = useState<string | null>(null);
  const [weatherInfo, setWeatherInfo] = useState<WeatherInfo | null>(null);
  const [callDropStats, setCallDropStats] = useState<CallDropStats | null>(null);

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

  const { data: routeData, isLoading: routesLoading } = useRoutes(
    queryParams ?? { source: "", destination: "", preference: 50, telecom: "all" },
  );
  const { data: heatmapData } = useHeatmap();
  const { data: towerMarkersData } = useTowerMarkers();
  const reroute = useReroute();

  const routes = hasSearched ? (routeData?.routes ?? []) : [];
  const recommendedRoute = routeData?.recommended_route ?? "";
  const heatmapZones = heatmapData?.zones ?? [];
  const towerMarkers = towerMarkersData ?? [];

  const selectedRoute = routes[selectedRouteIndex] ?? routes[0];
  const trackingPath = selectedRoute?.path ?? [];
  const { position: trackingPosition, progress: trackingProgress } = useTracking(trackingPath, trackingActive);

  const etaDisplay = selectedRoute ? `${selectedRoute.eta} min` : "--";

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

  // Extract weather + call-drop stats from route response
  useEffect(() => {
    if (routeData?.weather) setWeatherInfo(routeData.weather);
    if (routeData?.call_drop_stats) setCallDropStats(routeData.call_drop_stats);
  }, [routeData]);

  // Offline cache alert: warn user when a dead zone is approaching
  const offlineAlert = selectedRoute?.offline_alerts?.[0]?.message ?? null;

  // Dead zone warning from carrier-level prediction
  const deadZoneCount = selectedRoute?.carrier_dead_zones?.length ?? 0;
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

  // When geolocation resolves, reverse-geocode GPS coords to a readable name via Nominatim
  useEffect(() => {
    if (geo.location && !source) {
      const { lat, lng } = geo.location;
      reverseGeocodeService
        .lookup(lat, lng)
        .then((result) => {
          if (result) {
            const short = result.city.split(",").slice(0, 2).join(",").trim();
            setSource(short);
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
      setTelecom(tel);
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
        geocodeService.search(`${lat},${lng}`, 1).then((results) => {
          if (results.length > 0) {
            setSource(results[0].city.split(",").slice(0, 2).join(",").trim());
          }
        }).catch(() => {});
      } else {
        setDestCoords({ lat, lng });
        geocodeService.search(`${lat},${lng}`, 1).then((results) => {
          if (results.length > 0) {
            setDestination(results[0].city.split(",").slice(0, 2).join(",").trim());
          }
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

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-white">
      {/* Full-screen map */}
      <MapContainer
        routes={routes}
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

      {/* Filter panel (top-right) */}
      <FilterPanel
        preference={preference}
        telecom={telecom}
        onPreferenceChange={setPreference}
        onTelecomChange={setTelecom}
        onChatApply={handleChatApply}
        detectedNetwork={networkInfo.type}
        maxEtaFactor={maxEtaFactor}
        onMaxEtaFactorChange={setMaxEtaFactor}
        onDownloadOffline={hasSearched ? handleDownloadOffline : undefined}
        offlineReady={offlineReady}
        heatmapFilter={heatmapFilter}
        onHeatmapFilterChange={setHeatmapFilter}
      />

      {/* Weather badge (top-right, below filter panel) */}
      {weatherInfo && (
        <div className="absolute top-52 right-4 z-[1000]">
          <WeatherBadge weather={weatherInfo} />
        </div>
      )}

      {/* Call-drop stats badge */}
      {callDropStats && callDropStats.drops_avoided > 0 && (
        <div className="absolute top-72 right-4 z-[1000] rounded-xl bg-green-50 px-3 py-2 shadow-md ring-1 ring-green-200 text-sm">
          <p className="font-medium text-green-700">{callDropStats.message}</p>
        </div>
      )}

      {/* Route sidebar (left) */}
      <RouteSidebar
        routes={routes}
        selectedIndex={selectedRouteIndex}
        recommendedRoute={recommendedRoute}
        suggestedRoute={suggestedRoute ? recommendedRoute : ""}
        onSelect={handleRouteSelect}
        onClose={() => setSidebarOpen(false)}
        visible={sidebarOpen && routes.length > 0}
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
