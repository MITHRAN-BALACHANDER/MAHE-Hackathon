import axios from "axios";

import type {
  HeatmapResponse,
  PredictionResponse,
  RerouteRequest,
  RerouteResponse,
  RoutesResponse,
  TelecomMode,
} from "@/src/types/route";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 12_000,
});

export async function fetchRoutes(params: {
  source: string;
  destination: string;
  preference: number;
  telecom: TelecomMode;
}): Promise<RoutesResponse> {
  const { data } = await client.get<RoutesResponse>("/api/routes", { params });
  return data;
}

export async function fetchHeatmap(): Promise<HeatmapResponse> {
  const { data } = await client.get<HeatmapResponse>("/api/heatmap");
  return data;
}

export async function fetchPrediction(
  zone: string,
  minutes = 15,
): Promise<PredictionResponse> {
  const { data } = await client.get<PredictionResponse>("/api/predict", {
    params: { zone, minutes },
  });
  return data;
}

export async function reroute(
  request: RerouteRequest,
): Promise<RerouteResponse> {
  const { data } = await client.post<RerouteResponse>("/api/reroute", request);
  return data;
}
