"use client";

import type { HeatmapFilterType } from "@/src/components/map/MapView";

type ActiveFilter = Exclude<HeatmapFilterType, "none">;

type Props = {
  filter: ActiveFilter;
};

const LEGENDS: Record<ActiveFilter, { title: string; items: { color: string; label: string }[] }> = {
  signal: {
    title: "Signal Strength",
    items: [
      { color: "#22c55e", label: "Strong (70+)" },
      { color: "#eab308", label: "Medium (40-69)" },
      { color: "#ef4444", label: "Weak (<40)" },
    ],
  },
  weather: {
    title: "Weather Impact",
    items: [
      { color: "#22c55e", label: "Clear (minimal impact)" },
      { color: "#eab308", label: "Moderate (some degradation)" },
      { color: "#ef4444", label: "Severe (heavy disruption)" },
    ],
  },
  traffic: {
    title: "Traffic Congestion",
    items: [
      { color: "#22c55e", label: "Light (free flow)" },
      { color: "#eab308", label: "Moderate (some delays)" },
      { color: "#ef4444", label: "Heavy (congested)" },
    ],
  },
  road: {
    title: "Road Type",
    items: [
      { color: "#3b82f6", label: "Highway" },
      { color: "#f59e0b", label: "Urban Main" },
      { color: "#22c55e", label: "Suburban" },
      { color: "#a855f7", label: "Residential" },
    ],
  },
};

export function HeatmapLegend({ filter }: Props) {
  const legend = LEGENDS[filter];

  return (
    <div className="glass-card rounded-xl px-3 py-2.5 animate-fade-in">
      <p className="text-[11px] font-semibold text-white/70 mb-2">{legend.title}</p>
      <div className="flex flex-col gap-1.5">
        {legend.items.map((item) => (
          <div key={item.label} className="flex items-center gap-2">
            <span
              className="w-3 h-3 rounded-full shrink-0 ring-1 ring-white/10"
              style={{ backgroundColor: item.color }}
            />
            <span className="text-[11px] text-white/60">{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
