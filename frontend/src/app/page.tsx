"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { ActionButtons } from "@/src/components/actions/ActionButtons";
import { RouteBottomCard } from "@/src/components/common/RouteBottomCard";
import { Toast } from "@/src/components/common/Toast";
import { FilterPanel } from "@/src/components/filters/FilterPanel";
import { MapContainer } from "@/src/components/map/MapContainer";
import { SearchBar } from "@/src/components/search/SearchBar";
import { RouteSidebar } from "@/src/components/sidebar/RouteSidebar";
import { useGeolocation } from "@/src/hooks/useGeolocation";
import { useHeatmap, useReroute, useRoutes } from "@/src/hooks/useMapData";
import { useNetworkDetect } from "@/src/hooks/useNetworkDetect";
import { useTracking } from "@/src/hooks/useTracking";
import type { TelecomMode } from "@/src/types/route";

export default function Home() {
  // Search state -- empty on load
  const [source, setSource] = useState("");
  const [destination, setDestination] = useState("");
  const [searchTrigger, setSearchTrigger] = useState(0);
  const [hasSearched, setHasSearched] = useState(false);

  // Filter state
  const [preference, setPreference] = useState(50);
  const [telecom, setTelecom] = useState<TelecomMode>("all");

  // UI state
  const [selectedRouteIndex, setSelectedRouteIndex] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [trackingActive, setTrackingActive] = useState(false);
  const [suggestedRoute, setSuggestedRoute] = useState<string>("");

  // Geolocation
  const geo = useGeolocation();

  // Network detection
  const networkInfo = useNetworkDetect();

  // Only query routes when we have both source and destination and user has searched
  const queryParams = useMemo(
    () =>
      hasSearched && source && destination
        ? { source, destination, preference, telecom }
        : null,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [source, destination, preference, telecom, searchTrigger, hasSearched],
  );

  const { data: routeData, isLoading: routesLoading } = useRoutes(
    queryParams ?? { source: "", destination: "", preference: 50, telecom: "all" },
  );
  const { data: heatmapData } = useHeatmap();
  const reroute = useReroute();

  const routes = hasSearched ? (routeData?.routes ?? []) : [];
  const recommendedRoute = routeData?.recommended_route ?? "";
  const heatmapZones = heatmapData?.zones ?? [];

  const selectedRoute = routes[selectedRouteIndex] ?? routes[0];
  const trackingPath = selectedRoute?.path ?? [];
  const { position: trackingPosition } = useTracking(trackingPath, trackingActive);

  const etaDisplay = selectedRoute ? `${selectedRoute.eta} min` : "--";

  // Toast message
  const toastMessage = reroute.data?.advisory ?? null;
  const toastType = reroute.data ? ("reroute" as const) : ("info" as const);

  // When geolocation resolves, reverse-geocode to a readable name
  useEffect(() => {
    if (geo.location && !source) {
      // Use nearest known area name based on coords (Bangalore area)
      const areas = [
        { name: "Electronic City", lat: 12.839, lng: 77.678 },
        { name: "Koramangala", lat: 12.935, lng: 77.624 },
        { name: "Indiranagar", lat: 12.972, lng: 77.641 },
        { name: "Whitefield", lat: 12.970, lng: 77.750 },
        { name: "MG Road", lat: 12.975, lng: 77.607 },
        { name: "Jayanagar", lat: 12.930, lng: 77.584 },
        { name: "HSR Layout", lat: 12.912, lng: 77.638 },
        { name: "Hebbal", lat: 13.035, lng: 77.597 },
        { name: "Marathahalli", lat: 12.956, lng: 77.701 },
        { name: "BTM Layout", lat: 12.916, lng: 77.616 },
        { name: "Rajajinagar", lat: 12.988, lng: 77.557 },
        { name: "Silk Board", lat: 12.917, lng: 77.623 },
        { name: "Peenya", lat: 13.032, lng: 77.523 },
        { name: "Yelahanka", lat: 13.101, lng: 77.594 },
        { name: "Bannerghatta", lat: 12.880, lng: 77.598 },
        { name: "KR Puram", lat: 13.008, lng: 77.696 },
        { name: "Sarjapur Road", lat: 12.910, lng: 77.685 },
        { name: "JP Nagar", lat: 12.907, lng: 77.586 },
        { name: "Majestic", lat: 12.977, lng: 77.572 },
      ];
      let closest = areas[0];
      let minDist = Infinity;
      for (const a of areas) {
        const d = Math.hypot(a.lat - geo.location.lat, a.lng - geo.location.lng);
        if (d < minDist) {
          minDist = d;
          closest = a;
        }
      }
      setSource(closest.name);
    }
  }, [geo.location, source]);

  const handleSearch = useCallback(() => {
    if (!source || !destination) return;
    setSearchTrigger((n) => n + 1);
    setHasSearched(true);
    setSidebarOpen(true);
    setSelectedRouteIndex(0);
    setSuggestedRoute("");
  }, [source, destination]);

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
      setSuggestedRoute("Suggested");
      setHasSearched(true);
      setSearchTrigger((n) => n + 1);
      setSidebarOpen(true);
      setSelectedRouteIndex(0);
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
        onRouteClick={handleRouteSelect}
        trackingPosition={trackingPosition}
        userLocation={geo.location}
      />

      {/* Search bar (top-left) */}
      <SearchBar
        source={source}
        destination={destination}
        onSourceChange={setSource}
        onDestinationChange={setDestination}
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
      />

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
      <ActionButtons
        tracking={trackingActive}
        loading={routesLoading || reroute.isPending}
        onToggleTracking={() => setTrackingActive((v) => !v)}
        onReroute={handleReroute}
        onLocateMe={handleLocateMe}
        geoLoading={geo.loading}
        geoError={geo.error}
      />

      {/* Toast notifications */}
      <Toast message={toastMessage} type={toastType} />
    </div>
  );
}
