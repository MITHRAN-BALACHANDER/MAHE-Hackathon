import axios from "axios";

import type {
  CongestionAlert,
  HeatmapResponse,
  OfflineBundle,
  PredictionResponse,
  RerouteRequest,
  RerouteResponse,
  RouteQueryParams,
  RoutesResponse,
  TowerSummary,
  TowerMarker,
  TowerMarkersResponse,
  WeatherInfo,
  CarrierSignalSummary,
  CarrierDeadZone,
} from "@/src/types/route";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60_000,
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

export const towerGeoService = {
  async fetchAll(maxTowers = 300): Promise<TowerMarker[]> {
    const { data } = await client.get<TowerMarkersResponse>("/api/towers/geo", {
      params: { max_towers: maxTowers },
    });
    return data.towers ?? [];
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

export const reverseGeocodeService = {
  async lookup(lat: number, lon: number): Promise<GeocodeSuggestion | null> {
    try {
      const { data } = await client.get<GeocodeSuggestion>("/api/reverse-geocode", {
        params: { lat, lon },
      });
      return data;
    } catch {
      return null;
    }
  },
};

export const weatherService = {
  async getWeather(lat: number, lng: number): Promise<WeatherInfo | null> {
    try {
      const { data } = await client.get<WeatherInfo>("/api/weather", {
        params: { lat, lng },
      });
      return data;
    } catch {
      return null;
    }
  },
};

export const alertsService = {
  async getAlerts(
    userLat: number,
    userLng: number,
    path: Array<{ lat: number; lng: number }>,
  ): Promise<{ alerts: CongestionAlert[]; count: number }> {
    try {
      // Sample path to keep URL small (max 25 points)
      const sampled =
        path.length <= 25
          ? path
          : path.filter((_, i) => i % Math.ceil(path.length / 25) === 0);
      const { data } = await client.get<{ alerts: CongestionAlert[]; count: number }>(
        "/api/alerts",
        {
          params: {
            user_lat: userLat,
            user_lng: userLng,
            path: JSON.stringify(sampled),
          },
        },
      );
      return data;
    } catch {
      return { alerts: [], count: 0 };
    }
  },
};

export type DeadZoneResponse = {
  source: string;
  destination: string;
  time_hour: number;
  weather: WeatherInfo;
  route_name: string;
  route_distance_km: number;
  carriers: Record<string, { avg: number; min: number; weak_segments: number }>;
  dead_zones: CarrierDeadZone[];
  total_dead_zones: number;
  best_carrier_per_point: string[];
};

export const deadZoneService = {
  async predict(
    source: string,
    destination: string,
    timeHour = -1,
  ): Promise<DeadZoneResponse | null> {
    try {
      const { data } = await client.get<DeadZoneResponse>("/api/dead-zones", {
        params: { source, destination, time_hour: timeHour },
      });
      return data;
    } catch {
      return null;
    }
  },
};

