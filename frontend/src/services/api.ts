import axios from "axios";

import type {
  HeatmapResponse,
  PredictionResponse,
  RerouteRequest,
  RerouteResponse,
  RouteQueryParams,
  RoutesResponse,
  TowerSummary,
} from "@/src/types/route";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 12_000,
});

export const routeService = {
  async getRoutes(params: RouteQueryParams): Promise<RoutesResponse> {
    const { data } = await client.get<RoutesResponse>("/api/routes", { params });
    return data;
  },

  async reroute(request: RerouteRequest): Promise<RerouteResponse> {
    const { data } = await client.post<RerouteResponse>("/api/reroute", request);
    return data;
  },
};

export const heatmapService = {
  async getHeatmap(): Promise<HeatmapResponse> {
    const { data } = await client.get<HeatmapResponse>("/api/heatmap");
    return data;
  },
};

export const predictionService = {
  async getPrediction(zone: string, minutes = 15): Promise<PredictionResponse> {
    const { data } = await client.get<PredictionResponse>("/api/predict", {
      params: { zone, minutes },
    });
    return data;
  },
};

export const towerService = {
  async getTowers(): Promise<TowerSummary> {
    const { data } = await client.get<TowerSummary>("/api/towers");
    return data;
  },
};
