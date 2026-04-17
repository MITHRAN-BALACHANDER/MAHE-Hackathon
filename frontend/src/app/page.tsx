"use client";

import { useMemo, useState } from "react";

import { AlertBanner } from "@/src/components/AlertBanner";
import { HeatmapLegend } from "@/src/components/HeatmapLegend";
import { Navbar } from "@/src/components/Navbar";
import { PreferenceSlider } from "@/src/components/PreferenceSlider";
import { RouteComparisonCards } from "@/src/components/RouteComparisonCards";
import { RouteMap } from "@/src/components/RouteMap";
import { SignalChart } from "@/src/components/SignalChart";
import { useRoutes } from "@/src/hooks/useRoutes";
import type { TelecomMode } from "@/src/types/route";

export default function Home() {
  const [source, setSource] = useState("MIT");
  const [destination, setDestination] = useState("Airport");
  const [preference, setPreference] = useState(50);
  const [telecom, setTelecom] = useState<TelecomMode>("all");
  const [emergencyMode, setEmergencyMode] = useState(false);

  const {
    routes,
    recommendedRoute,
    heatmapZones,
    prediction,
    rerouteData,
    loading,
    error,
    requestReroute,
  } = useRoutes({
    source,
    destination,
    preference,
    telecom,
  });

  const activeAlert = useMemo(() => {
    if (rerouteData?.advisory) {
      return rerouteData.advisory;
    }
    if (prediction?.message) {
      return prediction.message;
    }
    if (emergencyMode) {
      return "Emergency mode enabled: prioritizing the most reliable network corridor.";
    }
    return "Download offline maps before entering weak zones for seamless navigation.";
  }, [emergencyMode, prediction?.message, rerouteData?.advisory]);

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_20%_10%,rgba(56,189,248,0.16),transparent_40%),radial-gradient(circle_at_80%_0%,rgba(16,185,129,0.14),transparent_35%),linear-gradient(180deg,#050b16_0%,#091225_55%,#0b1322_100%)] text-slate-100">
      <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 md:px-6 lg:px-8">
        <Navbar
          source={source}
          destination={destination}
          onSourceChange={setSource}
          onDestinationChange={setDestination}
        />

        <AlertBanner message={prediction?.message} fallback={activeAlert} />

        <PreferenceSlider
          preference={preference}
          telecom={telecom}
          emergencyMode={emergencyMode}
          onPreferenceChange={setPreference}
          onTelecomChange={setTelecom}
          onEmergencyModeChange={setEmergencyMode}
        />

        <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
          <RouteMap routes={routes} heatmapZones={heatmapZones} />
          <div className="flex flex-col gap-4">
            <HeatmapLegend />
            <button
              type="button"
              onClick={() => {
                void requestReroute();
              }}
              className="rounded-2xl border border-cyan-300/40 bg-cyan-300/15 px-4 py-3 text-sm font-medium text-cyan-100 transition hover:bg-cyan-300/25"
            >
              Trigger Smart Reroute
            </button>
            <div className="rounded-2xl border border-white/10 bg-[#0f1b2d] p-4 text-xs text-slate-300">
              <p className="mb-1 text-slate-100">Route Status</p>
              <p>
                {loading
                  ? "Loading route intelligence..."
                  : `Comparing ${routes.length} route options`}
              </p>
              {error ? <p className="mt-1 text-red-300">{error}</p> : null}
            </div>
          </div>
        </div>

        <RouteComparisonCards
          routes={routes}
          recommendedRoute={recommendedRoute}
        />
        <SignalChart routes={routes} />
      </main>
    </div>
  );
}
