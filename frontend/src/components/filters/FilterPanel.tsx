"use client";

import { Download, Filter, MessageCircle, Signal, CloudRain, Car, Route, X } from "lucide-react";
import { useState } from "react";
import type { TelecomMode } from "@/src/types/route";
import { ChatBot } from "@/src/components/chat/ChatBot";
import type { HeatmapFilterType } from "@/src/components/map/MapContainer";

type Props = {
  preference: number;
  telecom: TelecomMode;
  onPreferenceChange: (v: number) => void;
  onTelecomChange: (v: TelecomMode) => void;
  onChatApply?: (source: string, destination: string, preference: number, telecom: TelecomMode) => void;
  detectedNetwork: string;
  maxEtaFactor?: number;
  onMaxEtaFactorChange?: (v: number) => void;
  onDownloadOffline?: () => void;
  offlineReady?: boolean;
  heatmapFilter?: HeatmapFilterType;
  onHeatmapFilterChange?: (v: HeatmapFilterType) => void;
};

const PRESET_FILTERS = [
  { label: "Less Traffic", pref: 20 },
  { label: "Balanced", pref: 50 },
  { label: "Best Signal", pref: 90 },
];

const HEATMAP_OPTIONS: { value: HeatmapFilterType; label: string; icon: typeof Signal; color: string; activeColor: string }[] = [
  { value: "signal", label: "Signal", icon: Signal, color: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20", activeColor: "bg-emerald-500 text-white border-emerald-500" },
  { value: "weather", label: "Weather", icon: CloudRain, color: "bg-violet-500/10 text-violet-400 border-violet-500/20", activeColor: "bg-violet-500 text-white border-violet-500" },
  { value: "traffic", label: "Traffic", icon: Car, color: "bg-orange-500/10 text-orange-400 border-orange-500/20", activeColor: "bg-orange-500 text-white border-orange-500" },
  { value: "road", label: "Road Type", icon: Route, color: "bg-blue-500/10 text-blue-400 border-blue-500/20", activeColor: "bg-blue-500 text-white border-blue-500" },
];

export function FilterPanel({
  preference,
  telecom,
  onPreferenceChange,
  onTelecomChange,
  onChatApply,
  detectedNetwork,
  maxEtaFactor = 1.5,
  onMaxEtaFactorChange,
  onDownloadOffline,
  offlineReady,
  heatmapFilter = "signal",
  onHeatmapFilterChange,
}: Props) {
  const [open, setOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);

  return (
    <div id="filter-panel" className="absolute top-4 right-4 z-[1000]">
      <div className="flex items-center gap-2">
        <button
          id="chatbot-btn"
          type="button"
          onClick={() => { setChatOpen(!chatOpen); if (!chatOpen) setOpen(false); }}
          className="glass-card rounded-xl px-4 py-2.5 flex items-center gap-2 text-sm text-white/80 hover:text-white hover:bg-white/15 cursor-pointer transition-all"
        >
          <MessageCircle size={16} />
          Get Personalised Route
        </button>
        <button
          type="button"
          onClick={() => { setOpen(!open); if (!open) setChatOpen(false); }}
          className="glass-card rounded-xl px-4 py-2.5 flex items-center gap-2 text-sm text-white/80 hover:text-white hover:bg-white/15 cursor-pointer transition-all"
        >
          <Filter size={16} />
          Filters
        </button>
      </div>

      {chatOpen && (
        <div className="mt-2 glass-card rounded-xl w-80 overflow-hidden animate-slide-up" style={{ height: 440 }}>
          <ChatBot
            onClose={() => setChatOpen(false)}
            onApply={(src, dest, pref, tel) => { onChatApply?.(src, dest, pref, tel); setChatOpen(false); }}
            detectedNetwork={detectedNetwork}
          />
        </div>
      )}

      {open && (
        <div className="mt-2 glass-card rounded-xl w-72 p-4 animate-slide-up">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white/90">Route Preferences</h3>
            <button type="button" onClick={() => setOpen(false)} className="text-white/30 hover:text-white/70 cursor-pointer transition-colors">
              <X size={16} />
            </button>
          </div>

          <div className="flex gap-2 mb-4">
            {PRESET_FILTERS.map((p) => (
              <button
                key={p.label}
                type="button"
                onClick={() => onPreferenceChange(p.pref)}
                className={`flex-1 text-xs py-2 rounded-lg font-medium cursor-pointer transition-all ${preference === p.pref ? "bg-cyan-500 text-white shadow-md shadow-cyan-500/25" : "bg-white/10 text-white/60 hover:bg-white/15"}`}
              >
                {p.label}
              </button>
            ))}
          </div>

          {onHeatmapFilterChange && (
            <div className="mb-4">
              <label className="text-xs font-medium text-white/50 mb-2 block">Heatmap Layer</label>
              <div className="grid grid-cols-4 gap-1.5">
                {HEATMAP_OPTIONS.map((opt) => {
                  const isActive = heatmapFilter === opt.value;
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => onHeatmapFilterChange(opt.value)}
                      className={`heatmap-chip flex flex-col items-center gap-1 py-2 border rounded-lg cursor-pointer transition-all ${isActive ? opt.activeColor + " active" : opt.color}`}
                    >
                      <opt.icon size={14} />
                      <span className="text-[10px]">{opt.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {onMaxEtaFactorChange && (
            <div className="mb-4">
              <label className="text-xs font-medium text-white/50 mb-1 block">
                Max ETA Limit: {maxEtaFactor === 0 ? "None" : `${Math.round(maxEtaFactor * 100)}% of fastest`}
              </label>
              <input type="range" min={0} max={3} step={0.1} value={maxEtaFactor} onChange={(e) => onMaxEtaFactorChange(parseFloat(e.target.value))} className="w-full" />
              <div className="flex justify-between text-[10px] text-white/30 mt-0.5">
                <span>No limit</span><span>1.5x</span><span>3x</span>
              </div>
            </div>
          )}

          {detectedNetwork && detectedNetwork !== "unknown" && (
            <div className="mb-4 px-3 py-2 bg-cyan-500/10 rounded-lg border border-cyan-500/20">
              <p className="text-xs text-cyan-300">Detected network: <span className="font-semibold">{detectedNetwork}</span></p>
            </div>
          )}

          <div className="mb-4">
            <label className="text-xs font-medium text-white/50 mb-2 block">Network Provider</label>
            <div className="grid grid-cols-2 gap-1.5">
              {([ { value: "all" as TelecomMode, label: "All Networks" }, { value: "jio" as TelecomMode, label: "Jio" }, { value: "airtel" as TelecomMode, label: "Airtel" }, { value: "vi" as TelecomMode, label: "Vi" }, { value: "multi" as TelecomMode, label: "Multi-SIM" } ]).map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => onTelecomChange(opt.value)}
                  className={`text-xs py-2 rounded-lg font-medium cursor-pointer transition-all ${telecom === opt.value ? "bg-cyan-500 text-white shadow-md shadow-cyan-500/25" : "bg-white/10 text-white/60 hover:bg-white/15"}`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* {onDownloadOffline && (
            <button
              type="button"
              onClick={onDownloadOffline}
              className={`w-full text-xs py-2.5 rounded-lg font-medium cursor-pointer transition-all flex items-center justify-center gap-2 ${offlineReady ? "bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/30" : "bg-white/10 text-white/60 hover:bg-white/15"}`}
            >
              <Download size={14} />
              {offlineReady ? "Offline Data Ready" : "Download for Offline"}
            </button>
          )} */}
        </div>
      )}
    </div>
  );
}