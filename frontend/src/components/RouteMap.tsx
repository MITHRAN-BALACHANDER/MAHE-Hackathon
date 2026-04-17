"use client";

import dynamic from "next/dynamic";

import type { HeatmapZone, RouteOption } from "@/src/types/route";

const RouteMapClient = dynamic(
  () => import("@/src/components/RouteMapClient"),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-95 items-center justify-center rounded-2xl border border-white/10 bg-[#0f1b2d] text-slate-400">
        Loading map...
      </div>
    ),
  },
);

type RouteMapProps = {
  routes: RouteOption[];
  heatmapZones: HeatmapZone[];
};

export function RouteMap({ routes, heatmapZones }: RouteMapProps) {
  return <RouteMapClient routes={routes} heatmapZones={heatmapZones} />;
}
