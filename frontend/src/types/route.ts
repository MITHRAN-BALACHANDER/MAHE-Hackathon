export type TelecomMode = "all" | "jio" | "airtel" | "vi";

export type Coordinate = {
  lat: number;
  lng: number;
};

export type RouteOption = {
  name: string;
  eta: number;
  distance: number;
  signal_score: number;
  weighted_score: number;
  zones: string[];
  path: Coordinate[];
};

export type RoutesResponse = {
  source: string;
  destination: string;
  preference: number;
  routes: RouteOption[];
  recommended_route: string;
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
