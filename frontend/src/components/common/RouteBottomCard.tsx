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
  if (score >= 70) return { label: "Strong", color: "text-emerald-400", bg: "bg-emerald-500/15" };
  if (score >= 40) return { label: "Medium", color: "text-amber-400", bg: "bg-amber-500/15" };
  return { label: "Weak", color: "text-red-400", bg: "bg-red-500/15" };
}

export function RouteBottomCard({ route, eta, onStartNavigation, suggested }: Props) {
  const signal = signalLevel(route.signal_score);

  return (
    <div className="absolute bottom-0 left-0 right-0 z-[1000] animate-slide-up">
      <div className="mx-4 mb-4 glass-card rounded-2xl p-4">

        {/* Header row: route name + Start button */}
        <div className="flex items-center justify-between mb-4">
          <div className="min-w-0">
            <p className="text-xs text-white/40 mb-0.5">Selected route</p>
            <p className="text-sm font-semibold text-white truncate">via {route.name}</p>
          </div>
          <div className="flex items-center gap-2 shrink-0 ml-3">
            {suggested && (
              <span className="text-[10px] font-semibold bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded-full ring-1 ring-emerald-500/30">
                Suggested
              </span>
            )}
            <button
              type="button"
              onClick={onStartNavigation}
              className="bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white px-5 py-2.5 rounded-full text-sm font-semibold flex items-center gap-2 cursor-pointer transition-all shadow-lg shadow-cyan-500/25"
            >
              <Navigation size={16} />
              Start
            </button>
          </div>
        </div>

        {/* Stat tiles */}
        <div className="grid grid-cols-4 gap-2">
          {/* ETA */}
          <div className="bg-slate-800 rounded-xl px-3 py-2.5 flex flex-col items-center gap-1">
            <Clock size={13} className="text-cyan-400" />
            <span className="text-base font-bold text-white leading-none">{route.eta}</span>
            <span className="text-[10px] text-white/40 leading-none">min</span>
          </div>

          {/* Distance */}
          <div className="bg-slate-800 rounded-xl px-3 py-2.5 flex flex-col items-center gap-1">
            <MapPin size={13} className="text-blue-400" />
            <span className="text-base font-bold text-white leading-none">{route.distance}</span>
            <span className="text-[10px] text-white/40 leading-none">km</span>
          </div>

          {/* Signal */}
          <div className={`${signal.bg} rounded-xl px-3 py-2.5 flex flex-col items-center gap-1`}>
            <Signal size={13} className={signal.color} />
            <span className={`text-base font-bold leading-none ${signal.color}`}>{Math.round(route.signal_score)}</span>
            <span className="text-[10px] text-white/40 leading-none">{signal.label}</span>
          </div>

          {/* Score */}
          <div className="bg-slate-800 rounded-xl px-3 py-2.5 flex flex-col items-center gap-1">
            <TrendingUp size={13} className="text-violet-400" />
            <span className="text-base font-bold text-white leading-none">{Math.round(route.weighted_score)}</span>
            <span className="text-[10px] text-white/40 leading-none">score</span>
          </div>
        </div>
      </div>
    </div>
  );
}
