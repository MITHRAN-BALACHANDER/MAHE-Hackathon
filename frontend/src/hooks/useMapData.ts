"use client";

import { useMutation, useQuery } from "@tanstack/react-query";

import { heatmapService, predictionService, routeService, towerService, towerGeoService } from "@/src/services/api";
import type { RerouteRequest, RouteQueryParams } from "@/src/types/route";

export function useRoutes(params: RouteQueryParams) {
  return useQuery({
    queryKey: ["routes", params],
    queryFn: () => routeService.getRoutes(params),
    enabled: !!params.source && !!params.destination,
    staleTime: 30_000,
    retry: 1,
  });
}

export function useHeatmap() {
  return useQuery({
    queryKey: ["heatmap"],
    queryFn: () => heatmapService.getHeatmap(),
    staleTime: 60_000,
  });
}

export function usePrediction(zone: string, minutes = 15) {
  return useQuery({
    queryKey: ["prediction", zone, minutes],
    queryFn: () => predictionService.getPrediction(zone, minutes),
    enabled: !!zone,
  });
}

export function useReroute() {
  return useMutation({
    mutationFn: (request: RerouteRequest) => routeService.reroute(request),
  });
}

export function useTowers() {
  return useQuery({
    queryKey: ["towers"],
    queryFn: () => towerService.getTowers(),
    staleTime: 120_000,
  });
}

export function useTowerMarkers() {
  return useQuery({
    queryKey: ["tower-markers"],
    queryFn: () => towerGeoService.fetchAll(500),
    staleTime: 5 * 60_000,
    retry: 1,
  });
}
