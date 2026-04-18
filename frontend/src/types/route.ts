export type TelecomMode = "all" | "jio" | "airtel" | "vi" | "multi";

export type Coordinate = {
  lat: number;
  lng: number;
};

export type BadZone = {
  start_coord: Coordinate;
  end_coord: Coordinate;
  length_km: number;
  min_signal: number;
  time_to_zone_min: number;
  zone_duration_min: number;
  edge_zone_name?: string | null;
  warning: string;
};

export type MultiSimCarrier = {
  avg_connectivity: number;
  continuity_score: number;
  stability_score: number;
  drop_segments: number;
  signal_variance: number;
};

export type MultiSimInfo = {
  per_carrier: Record<string, MultiSimCarrier>;
  best_carrier: string;
  combined_avg_signal: number;
  combined_continuity: number;
  combined_variance: number;
  best_carrier_per_segment: string[];
};

export type RouteOption = {
  name: string;
  eta: number;
  distance: number;
  signal_score: number;
  weighted_score: number;
  zones: string[];
  path: Coordinate[];
  rejected?: boolean;
  // Stability metrics
  stability_score?: number;
  continuity_score?: number;
  signal_variance?: number;
  longest_stable_window?: number;
  // Bad zone predictions
  bad_zones?: BadZone[];
  // Multi-SIM
  multi_sim?: MultiSimInfo;
};

export type RoutesResponse = {
  source: string;
  destination: string;
  preference: number;
  max_eta_factor?: number;
  routes: RouteOption[];
  recommended_route: string;
  cache_hit?: boolean;
};

export type HeatmapZone = {
  name: string;
  lat: number;
  lng: number;
  score: number;
  signal_strength: "strong" | "medium" | "weak";
  color: string;
};

export type HeatmapResponse = {
  zones: HeatmapZone[];
};

export type TowerMarker = {
  tower_id: string;
  lat: number;
  lng: number;
  operator: string;
  signal_score: number;
  zone?: string;
};

export type TowerMarkersResponse = {
  towers: TowerMarker[];
  count: number;
};

export type PredictionResponse = {
  zone: string;
  horizon_minutes: number;
  expected_signal_score: number;
  message: string;
};

export type RerouteRequest = {
  source: string;
  destination: string;
  current_zone?: string;
  preference: number;
  telecom: TelecomMode;
};

export type RerouteResponse = {
  message: string;
  selected_route: RouteOption;
  advisory: string;
};

export type RouteQueryParams = {
  source: string;
  destination: string;
  preference: number;
  telecom: TelecomMode;
  max_eta_factor?: number;
};

export type TowerSummary = {
  source: string;
  count: number;
  operators: Record<string, number>;
  zones: Record<string, number>;
  radio_types?: Record<string, number>;
  towers_with_signal?: number;
};

export type OfflineBundleRoute = RouteOption & {
  segment_signals?: number[];
  segment_colors?: string[];
};

export type OfflineBundle = {
  source: string;
  destination: string;
  generated_at: number;
  routes: OfflineBundleRoute[];
  heatmap: HeatmapZone[];
  offline: boolean;
};
