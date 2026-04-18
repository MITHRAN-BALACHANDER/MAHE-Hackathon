"use client";

import { Crosshair, Locate, Navigation, RotateCcw, Zap } from "lucide-react";

type Props = {
  tracking: boolean;
  loading: boolean;
  onToggleTracking: () => void;
  onReroute: () => void;
  onLocateMe?: () => void;
  geoLoading?: boolean;
  geoError?: string | null;
};

export function ActionButtons({
  tracking,
  loading,
  onToggleTracking,
  onReroute,
  onLocateMe,
  geoLoading,
  geoError,
}: Props) {
  const btnBase =
    "w-12 h-12 rounded-full flex items-center justify-center cursor-pointer transition-all duration-200 focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:outline-none";

  return (
    <div className="absolute bottom-6 right-4 z-[1000] flex flex-col gap-2">
      {/* My location */}
      {onLocateMe && (
        <button
          type="button"
          onClick={onLocateMe}
          disabled={geoLoading}
          className={`${btnBase} glass-card text-white/60 hover:text-white hover:scale-105 disabled:opacity-40`}
          title={geoError ?? "Use my location"}
        >
          {geoLoading ? (
            <RotateCcw size={20} className="animate-spin" />
          ) : (
            <Crosshair size={20} />
          )}
        </button>
      )}

      {/* Live tracking */}
      <button
        type="button"
        onClick={onToggleTracking}
        className={`${btnBase} ${
          tracking
            ? "bg-gradient-to-br from-cyan-500 to-blue-600 text-white shadow-lg shadow-cyan-500/30 animate-pulse-ring"
            : "glass-card text-white/60 hover:text-white hover:scale-105"
        }`}
        title={tracking ? "Stop tracking" : "Start live tracking"}
      >
        {tracking ? <Navigation size={20} /> : <Locate size={20} />}
      </button>

      {/* Smart reroute */}
      <button
        type="button"
        onClick={onReroute}
        disabled={loading}
        className={`${btnBase} glass-card text-white/60 hover:text-cyan-400 hover:scale-105 disabled:opacity-40`}
        title="Smart reroute"
      >
        {loading ? (
          <RotateCcw size={20} className="animate-spin" />
        ) : (
          <Zap size={20} />
        )}
      </button>
    </div>
  );
}
