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
      { color: "#22c55e", label: "Strong " },
      { color: "#eab308", label: "Medium " },
      { color: "#ef4444", label: "Weak " },
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
  weather: {
    title: "Weather Conditions",
    items: [
      { color: "#22c55e", label: "Clear / Sunny" },
      { color: "#eab308", label: "Cloudy / Drizzle" },
      { color: "#ef4444", label: "Rain / Storm" },
    ],
  },
  road: {
    title: "Road Quality",
    items: [
      { color: "#22c55e", label: "Good" },
      { color: "#eab308", label: "Fair" },
      { color: "#ef4444", label: "Poor" },
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
