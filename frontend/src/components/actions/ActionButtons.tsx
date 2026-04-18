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
  return (
    <div className="absolute bottom-6 right-4 z-[1000] flex flex-col gap-2">
      {/* My location */}
      {onLocateMe && (
        <button
          type="button"
          onClick={onLocateMe}
          disabled={geoLoading}
          className="w-12 h-12 rounded-full bg-white text-gray-600 shadow-lg flex items-center justify-center hover:bg-gray-50 cursor-pointer transition-colors disabled:opacity-50"
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
        className={`w-12 h-12 rounded-full shadow-lg flex items-center justify-center cursor-pointer transition-colors ${
          tracking
            ? "bg-blue-500 text-white"
            : "bg-white text-gray-600 hover:bg-gray-50"
        }`}
        title={tracking ? "Stop tracking" : "Start live tracking"}
      >
        {tracking ? <Navigation size={20} className="animate-pulse" /> : <Locate size={20} />}
      </button>

      {/* Smart reroute */}
      <button
        type="button"
        onClick={onReroute}
        disabled={loading}
        className="w-12 h-12 rounded-full bg-white text-gray-600 shadow-lg flex items-center justify-center hover:bg-gray-50 cursor-pointer transition-colors disabled:opacity-50"
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
