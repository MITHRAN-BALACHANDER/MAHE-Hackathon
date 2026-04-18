"use client";

import { Clock, MapPin, Navigation, Signal, TrendingUp } from "lucide-react";
import type { RouteOption } from "@/src/types/route";

type Props = {
  route: RouteOption;
  eta: string;
  onStartNavigation: () => void;
  suggested?: boolean;
};

function signalLevel(score: number) {
  if (score >= 70) return { label: "Strong Signal", color: "text-green-600" };
  if (score >= 40) return { label: "Medium Signal", color: "text-yellow-600" };
  return { label: "Weak Signal", color: "text-red-500" };
}

export function RouteBottomCard({ route, eta, onStartNavigation, suggested }: Props) {
  const signal = signalLevel(route.signal_score);

  return (
    <div className="absolute bottom-0 left-0 right-0 z-[1000]">
      <div className="mx-4 mb-4 bg-white rounded-2xl shadow-xl p-4">
        {/* Top row */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold text-gray-900">{eta}</span>
            <span className="text-sm text-gray-500">({route.distance} km)</span>
            {suggested && (
              <span className="text-[10px] font-semibold bg-green-500 text-white px-2 py-0.5 rounded-full">
                Suggested
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={onStartNavigation}
            className="bg-blue-500 hover:bg-blue-600 text-white px-5 py-2.5 rounded-full text-sm font-semibold flex items-center gap-2 cursor-pointer transition-colors"
          >
            <Navigation size={16} />
            Start
          </button>
        </div>

        {/* Stats */}
        <div className="flex items-center gap-5 text-xs text-gray-500">
          <span className="flex items-center gap-1">
            <Clock size={13} />
            {route.eta} min
          </span>
          <span className="flex items-center gap-1">
            <MapPin size={13} />
            {route.zones.length} zones
          </span>
          <span className={`flex items-center gap-1 ${signal.color}`}>
            <Signal size={13} />
            {signal.label} ({Math.round(route.signal_score)})
          </span>
          <span className="flex items-center gap-1">
            <TrendingUp size={13} />
            Score {Math.round(route.weighted_score)}
          </span>
        </div>

        {/* Route name */}
        <div className="mt-2 text-xs text-gray-400">
          via {route.name}
        </div>
      </div>
    </div>
  );
}
