"use client";

import { useCallback, useEffect, useState } from "react";

import {
  fetchHeatmap,
  fetchPrediction,
  fetchRoutes,
  reroute,
} from "@/src/lib/api";
import type {
  HeatmapZone,
  PredictionResponse,
  RerouteResponse,
  RouteOption,
  TelecomMode,
} from "@/src/types/route";

type UseRoutesArgs = {
  source: string;
  destination: string;
  preference: number;
  telecom: TelecomMode;
};

export function useRoutes({
  source,
  destination,
  preference,
  telecom,
}: UseRoutesArgs) {
  const [routes, setRoutes] = useState<RouteOption[]>([]);
  const [recommendedRoute, setRecommendedRoute] = useState<string>("");
  const [heatmapZones, setHeatmapZones] = useState<HeatmapZone[]>([]);
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);
  const [rerouteData, setRerouteData] = useState<RerouteResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [routeData, heatmapData, predictionData] = await Promise.all([
        fetchRoutes({ source, destination, preference, telecom }),
        fetchHeatmap(),
        fetchPrediction("Electronic City", 15),
      ]);

      setRoutes(routeData.routes);
      setRecommendedRoute(routeData.recommended_route);
      setHeatmapZones(heatmapData.zones);
      setPrediction(predictionData);
    } catch {
      setError("Unable to fetch route intelligence right now. Please retry.");
    } finally {
      setLoading(false);
    }
  }, [destination, preference, source, telecom]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void load();
    }, 0);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [load]);

  const requestReroute = useCallback(async () => {
    try {
      const selected = await reroute({
        source,
        destination,
        current_zone: "Electronic City",
        preference,
        telecom,
      });
      setRerouteData(selected);
    } catch {
      setError("Reroute service is currently unavailable.");
    }
  }, [destination, preference, source, telecom]);

  return {
    routes,
    recommendedRoute,
    heatmapZones,
    prediction,
    rerouteData,
    loading,
    error,
    reload: load,
    requestReroute,
  };
}
