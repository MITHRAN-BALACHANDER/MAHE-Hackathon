import axios from "axios";

import type {
  HeatmapResponse,
  OfflineBundle,
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

export const offlineService = {
  async downloadBundle(
    source: string,
    destination: string,
    preference = 50,
    telecom = "all",
  ): Promise<OfflineBundle> {
    const { data } = await client.get<OfflineBundle>("/api/offline-bundle", {
      params: { source, destination, preference, telecom },
    });
    return data;
  },

  saveToStorage(bundle: OfflineBundle): void {
    const key = `offline_${bundle.source}_${bundle.destination}`;
    localStorage.setItem(key, JSON.stringify(bundle));
  },

  loadFromStorage(source: string, destination: string): OfflineBundle | null {
    const key = `offline_${source}_${destination}`;
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as OfflineBundle;
    } catch {
      return null;
    }
  },

  listSavedBundles(): string[] {
    const keys: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key?.startsWith("offline_")) keys.push(key);
    }
    return keys;
  },
};

export type GeocodeSuggestion = {
  city: string;   // full Nominatim display_name
  lat: number;
  lon: number;
};

export const geocodeService = {
  async search(q: string, limit = 5): Promise<GeocodeSuggestion[]> {
    if (!q || q.trim().length < 2) return [];
    try {
      const { data } = await client.get<GeocodeSuggestion[]>("/api/geocode", {
        params: { q: q.trim(), limit },
      });
      return data;
    } catch {
      return [];
    }
  },
};

