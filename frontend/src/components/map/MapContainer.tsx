"use client";

import dynamic from "next/dynamic";
import type { Coordinate, HeatmapZone, RouteOption, TowerMarker } from "@/src/types/route";
import type { HeatmapFilterType } from "./MapView";

const MapView = dynamic(() => import("./MapView"), {
  ssr: false,
  loading: () => (
    <div className="absolute inset-0 bg-slate-900 flex flex-col items-center justify-center gap-4">
      <div className="relative">
        <div className="w-12 h-12 border-[3px] border-white/10 border-t-cyan-400 rounded-full animate-spin" />
        <div className="absolute inset-0 w-12 h-12 border-[3px] border-transparent border-b-blue-400 rounded-full animate-spin" style={{ animationDirection: "reverse", animationDuration: "1.5s" }} />
      </div>
      <p className="text-sm text-white/50 tracking-wide">Loading map</p>
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
