"use client";

import { AlertTriangle, ChevronLeft, Clock, MapPin, Navigation, Signal, Shield, Wifi } from "lucide-react";
import type { RouteOption } from "@/src/types/route";

type Props = {
  routes: RouteOption[];
  selectedIndex: number;
  recommendedRoute: string;
  suggestedRoute?: string;
  onSelect: (index: number) => void;
  onClose: () => void;
  visible: boolean;
  enriching?: boolean;
};

function signalBadge(score: number) {
  if (score >= 70) return { label: "Strong", color: "bg-emerald-500/20 text-emerald-400 ring-emerald-500/30" };
  if (score >= 40) return { label: "Medium", color: "bg-amber-500/20 text-amber-400 ring-amber-500/30" };
  return { label: "Weak", color: "bg-red-500/20 text-red-400 ring-red-500/30" };
}

function stabilityLabel(score: number | undefined) {
  if (score === undefined) return null;
  if (score >= 70) return { label: "Stable", color: "text-emerald-400" };
  if (score >= 40) return { label: "Variable", color: "text-amber-400" };
  return { label: "Unstable", color: "text-red-400" };
}

export function RouteSidebar({
  routes,
  selectedIndex,
  recommendedRoute,
  suggestedRoute,
  onSelect,
  onClose,
  visible,
  enriching,
}: Props) {
  if (!visible || routes.length === 0) return null;

  return (
    <div className="absolute top-[207px] left-3 z-[800] max-h-[calc(100vh-217px)] w-[360px] glass-card flex flex-col rounded-2xl overflow-hidden animate-slide-in-left">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-700/60">
        <button
          type="button"
          onClick={onClose}
          className="p-1.5 hover:bg-white/10 rounded-full cursor-pointer transition-colors"
        >
          <ChevronLeft size={18} className="text-white/60" />
        </button>
        <h2 className="text-sm font-semibold text-white/90">Routes</h2>
        <span className="ml-auto text-xs text-white/40">
          {routes.length} options
          {enriching && (
            <span className="ml-1.5 text-cyan-400 animate-pulse">refining...</span>
          )}
        </span>
      </div>

      {/* Route list */}
      <div className="flex-1 overflow-y-auto">
        {routes.map((route, i) => {
          const isSelected = i === selectedIndex;
          const isSuggested = route.name === suggestedRoute;
          const badge = signalBadge(route.signal_score);
          const stability = stabilityLabel(route.stability_score);
          const isRejected = route.rejected === true;
          const hasBadZones = (route.bad_zones?.length ?? 0) > 0;
          const hasMultiSim = !!route.multi_sim;

          return (
            <button
              key={route.name}
              type="button"
              onClick={() => onSelect(i)}
              className={`w-full text-left px-4 py-3.5 border-b border-slate-700/30 cursor-pointer transition-all duration-200 ${
                isRejected
                  ? "bg-red-500/10 border-l-4 border-l-red-500/50 opacity-60"
                  : isSelected
                  ? "bg-cyan-500/10 border-l-4 border-l-cyan-400"
                  : "hover:bg-slate-800/70 border-l-4 border-l-transparent"
              }`}
            >
              {/* Route name & badges */}
              <div className="flex items-center gap-2 mb-1.5">
                <Navigation
                  size={14}
                  className={isSelected ? "text-cyan-400" : "text-white/30"}
                />
                <span
                  className={`text-sm font-medium ${
                    isRejected ? "text-red-400 line-through" : isSelected ? "text-cyan-300" : "text-white/85"
                  }`}
                >
                  {route.name}
                </span>
                {isRejected && (
                  <span className="text-[10px] font-semibold bg-red-500/20 text-red-400 px-1.5 py-0.5 rounded-full">
                    Too Slow
                  </span>
                )}
                {isSuggested && (
                  <span className="text-[10px] font-semibold bg-emerald-500/20 text-emerald-400 px-1.5 py-0.5 rounded-full">
                    Suggested
                  </span>
                )}
              </div>

              {/* Stats row */}
              <div className="flex items-center gap-2 mt-2">
                {/* ETA chip */}
                <div className="flex items-center gap-1.5 bg-slate-800 rounded-lg px-2.5 py-1.5 min-w-0">
                  <Clock size={11} className="text-cyan-400 shrink-0" />
                  <span className="text-sm font-bold text-white leading-none">{route.eta}</span>
                  <span className="text-[10px] text-white/40 leading-none">min</span>
                </div>
                {/* Distance chip */}
                <div className="flex items-center gap-1.5 bg-slate-800 rounded-lg px-2.5 py-1.5 min-w-0">
                  <MapPin size={11} className="text-blue-400 shrink-0" />
                  <span className="text-sm font-bold text-white leading-none">{route.distance}</span>
                  <span className="text-[10px] text-white/40 leading-none">km</span>
                </div>
                {/* Signal badge */}
                <span
                  className={`flex items-center gap-1 px-2 py-1.5 rounded-lg text-[11px] font-semibold ring-1 ${badge.color}`}
                >
                  <Signal size={10} />
                  {badge.label} {Math.round(route.signal_score)}
                  {enriching && <span className="ml-0.5 text-white/30 animate-pulse">~</span>}
                </span>
              </div>

              {/* Stability row */}
              {stability && (
                <div className="flex items-center gap-3 mt-1.5 text-xs">
                  <span className={`flex items-center gap-1 ${stability.color}`}>
                    <Shield size={10} />
                    {stability.label} ({Math.round(route.stability_score ?? 0)})
                  </span>
                  {route.longest_stable_window !== undefined && route.longest_stable_window > 0 && (
                    <span className="text-white/30">
                      {route.longest_stable_window} stable segments
                    </span>
                  )}
                </div>
              )}

              {/* Multi-SIM info */}
              {hasMultiSim && route.multi_sim && (
                <div className="mt-1.5 px-2 py-1 bg-purple-500/15 rounded text-[10px] text-purple-300 flex items-center gap-1.5">
                  <Wifi size={10} />
                  Best: <span className="font-semibold">{route.multi_sim.best_carrier}</span>
                  <span className="text-purple-400/60 ml-1">
                    (signal {route.multi_sim.combined_avg_signal})
                  </span>
                </div>
              )}

              {/* Bad zone warnings */}
              {hasBadZones && (
                <div className="mt-1.5 space-y-0.5">
                  {route.bad_zones!.slice(0, 2).map((bz, j) => (
                    <div
                      key={j}
                      className="flex items-start gap-1 text-[10px] text-orange-400 bg-orange-500/10 px-2 py-1 rounded"
                    >
                      <AlertTriangle size={10} className="mt-0.5 shrink-0" />
                      <span>
                        Dead zone in ~{Math.round(bz.time_to_zone_min)} min
                        ({bz.length_km} km, ~{bz.zone_duration_min.toFixed(1)} min)
                        {bz.edge_zone_name ? ` -- ${bz.edge_zone_name}` : ""}
                      </span>
                    </div>
                  ))}
                  {(route.bad_zones?.length ?? 0) > 2 && (
                    <span className="text-[10px] text-orange-500/60 pl-2">
                      +{(route.bad_zones?.length ?? 0) - 2} more zones
                    </span>
                  )}
                </div>
              )}

              {/* Zones */}
              <div className="mt-2 flex flex-wrap gap-1">
                {route.zones.map((z) => (
                  <span
                    key={z}
                    className="text-[10px] bg-slate-800 text-white/40 px-1.5 py-0.5 rounded"
                  >
                    {z}
                  </span>
                ))}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
