"use client";

import { ChevronLeft, Clock, MapPin, Navigation, Signal } from "lucide-react";
import type { RouteOption } from "@/src/types/route";

type Props = {
  routes: RouteOption[];
  selectedIndex: number;
  recommendedRoute: string;
  suggestedRoute?: string;
  onSelect: (index: number) => void;
  onClose: () => void;
  visible: boolean;
};

function signalBadge(score: number) {
  if (score >= 70) return { label: "Strong", color: "bg-green-100 text-green-700" };
  if (score >= 40) return { label: "Medium", color: "bg-yellow-100 text-yellow-700" };
  return { label: "Weak", color: "bg-red-100 text-red-700" };
}

export function RouteSidebar({
  routes,
  selectedIndex,
  recommendedRoute,
  suggestedRoute,
  onSelect,
  onClose,
  visible,
}: Props) {
  if (!visible || routes.length === 0) return null;

  return (
    <div className="absolute top-[120px] left-0 z-[800] max-h-[calc(100vh-130px)] w-[380px] bg-white shadow-xl flex flex-col rounded-tr-xl rounded-br-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100">
        <button
          type="button"
          onClick={onClose}
          className="p-1 hover:bg-gray-100 rounded-full cursor-pointer"
        >
          <ChevronLeft size={20} className="text-gray-600" />
        </button>
        <h2 className="text-sm font-semibold text-gray-800">Routes</h2>
        <span className="ml-auto text-xs text-gray-400">
          {routes.length} options
        </span>
      </div>

      {/* Route list */}
      <div className="flex-1 overflow-y-auto">
        {routes.map((route, i) => {
          const isSelected = i === selectedIndex;
          const isRecommended = route.name === recommendedRoute;
          const isSuggested = route.name === suggestedRoute;
          const badge = signalBadge(route.signal_score);

          return (
            <button
              key={route.name}
              type="button"
              onClick={() => onSelect(i)}
              className={`w-full text-left px-4 py-4 border-b border-gray-50 cursor-pointer transition-colors ${
                isSelected
                  ? "bg-blue-50 border-l-4 border-l-blue-500"
                  : "hover:bg-gray-50 border-l-4 border-l-transparent"
              }`}
            >
              {/* Route name & badges */}
              <div className="flex items-center gap-2 mb-1.5">
                <Navigation
                  size={14}
                  className={isSelected ? "text-blue-600" : "text-gray-400"}
                />
                <span
                  className={`text-sm font-medium ${
                    isSelected ? "text-blue-700" : "text-gray-800"
                  }`}
                >
                  {route.name}
                </span>
                {isSuggested && (
                  <span className="text-[10px] font-semibold bg-green-500 text-white px-1.5 py-0.5 rounded-full">
                    Suggested
                  </span>
                )}
              </div>

              {/* Stats row */}
              <div className="flex items-center gap-4 text-xs text-gray-500">
                <span className="flex items-center gap-1">
                  <Clock size={12} />
                  {route.eta} min
                </span>
                <span className="flex items-center gap-1">
                  <MapPin size={12} />
                  {route.distance} km
                </span>
                <span
                  className={`flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium ${badge.color}`}
                >
                  <Signal size={10} />
                  {badge.label} {Math.round(route.signal_score)}
                </span>
              </div>

              {/* Zones */}
              <div className="mt-2 flex flex-wrap gap-1">
                {route.zones.map((z) => (
                  <span
                    key={z}
                    className="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded"
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
