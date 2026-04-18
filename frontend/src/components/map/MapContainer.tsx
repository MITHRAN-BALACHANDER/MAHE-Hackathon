"use client";

import dynamic from "next/dynamic";
import type { Coordinate, HeatmapZone, RouteOption, TowerMarker } from "@/src/types/route";
import type { HeatmapFilterType } from "./MapView";

const MapView = dynamic(() => import("./MapView"), {
  ssr: false,
  loading: () => (
    <div className="absolute inset-0 bg-gray-50 flex flex-col items-center justify-center gap-4">
      <div className="w-10 h-10 border-3 border-gray-200 border-t-blue-500 rounded-full animate-spin" />
      <p className="text-sm text-gray-400">Loading map...</p>
    </div>
  ),
});

type Props = {
  routes: RouteOption[];
  selectedRouteIndex: number;
  heatmapZones: HeatmapZone[];
  towerMarkers?: TowerMarker[];
  onRouteClick?: (index: number) => void;
  trackingPosition?: Coordinate | null;
  userLocation?: Coordinate | null;
  heatmapFilter?: HeatmapFilterType;
  onPinDrag?: (type: "source" | "destination", lat: number, lng: number) => void;
};

export function MapContainer(props: Props) {
  return <MapView {...props} />;
}

export type { HeatmapFilterType };
