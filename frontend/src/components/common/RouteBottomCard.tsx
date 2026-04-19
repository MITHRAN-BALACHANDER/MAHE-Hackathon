"use client";

import { Clock, MapPin, Navigation } from "lucide-react";
import type { RouteOption } from "@/src/types/route";

type Props = {
  route: RouteOption;
  eta: string;
  onStartNavigation: () => void;
  suggested?: boolean;
};

function signalInfo(score: number) {
  if (score >= 70) return { filled: 4, color: "#22c55e", glow: "rgba(34,197,94,0.25)" };
  if (score >= 50) return { filled: 3, color: "#eab308", glow: "rgba(234,179,8,0.25)" };
  if (score >= 30) return { filled: 2, color: "#f97316", glow: "rgba(249,115,22,0.25)" };
  return { filled: 1, color: "#ef4444", glow: "rgba(239,68,68,0.25)" };
}

export function RouteBottomCard({ route, eta, onStartNavigation, suggested }: Props) {
  const sig = signalInfo(route.signal_score);

  return (
    <div className="absolute bottom-0 left-0 right-0 z-[1000] animate-slide-up">
      <div className="mx-4 mb-4 glass-card rounded-2xl overflow-hidden">
        {/* Signal strength bar -- thin color strip across top */}
        <div
          className="h-[3px] w-full"
          style={{ background: `linear-gradient(90deg, ${sig.color}00 0%, ${sig.color} 30%, ${sig.color} 70%, ${sig.color}00 100%)` }}
        />

        <div className="px-4 pt-3 pb-3.5">
          {/* Top row: route info + signal indicator + start button */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3 min-w-0">
              {/* Signal bars */}
              <div
                className="flex items-end gap-[2px] p-2 rounded-lg"
                style={{ background: sig.glow }}
              >
                {[6, 10, 14, 18].map((h, i) => (
                  <div
                    key={i}
                    className="w-[4px] rounded-[1px] transition-all"
                    style={{
                      height: h,
                      backgroundColor: i < sig.filled ? sig.color : "rgba(255,255,255,0.1)",
                    }}
                  />
                ))}
              </div>
              {/* Route name */}
              <div className="min-w-0">
                <p className="text-[11px] text-white/35 leading-none mb-1">Selected route</p>
                <p className="text-[13px] font-semibold text-white truncate leading-none">
                  {route.name}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2.5 shrink-0 ml-3">
              {suggested && (
                <span className="text-[9px] font-bold bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded-full">
                  Suggested
                </span>
              )}
              <button
                type="button"
                onClick={onStartNavigation}
                className="group bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white pl-3 pr-4 py-2 rounded-xl text-[13px] font-bold flex items-center gap-2 cursor-pointer transition-all shadow-[0_0_20px_rgba(6,182,212,0.3)] hover:shadow-[0_0_28px_rgba(6,182,212,0.45)]"
              >
                <Navigation size={14} />
                Start
              </button>
            </div>
          </div>

          {/* Stats row */}
          <div className="flex items-center gap-2 mt-3">
            <div className="flex-1 flex items-center justify-center gap-1.5 bg-slate-800/80 rounded-lg py-2">
              <Clock size={12} className="text-cyan-400" />
              <span className="text-[13px] font-bold text-white">{route.eta}</span>
              <span className="text-[10px] text-white/35">min</span>
            </div>
            <div className="flex-1 flex items-center justify-center gap-1.5 bg-slate-800/80 rounded-lg py-2">
              <MapPin size={12} className="text-blue-400" />
              <span className="text-[13px] font-bold text-white">{route.distance}</span>
              <span className="text-[10px] text-white/35">km</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
