"use client";

import { RadioTower } from "lucide-react";

type NavbarProps = {
  source: string;
  destination: string;
  onSourceChange: (value: string) => void;
  onDestinationChange: (value: string) => void;
};

export function Navbar({
  source,
  destination,
  onSourceChange,
  onDestinationChange,
}: NavbarProps) {
  return (
    <header className="rounded-2xl border border-white/15 bg-[#0d1624]/85 p-4 shadow-[0_10px_40px_rgba(0,0,0,0.35)] backdrop-blur-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-cyan-400/15 p-2 text-cyan-300">
            <RadioTower className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-cyan-300/90">
              SignalRoute AI
            </p>
            <h1 className="text-xl font-semibold text-white">
              Smart Navigation Intelligence
            </h1>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:min-w-[440px]">
          <label className="space-y-1">
            <span className="text-xs text-slate-300">Source</span>
            <input
              value={source}
              onChange={(event) => onSourceChange(event.target.value)}
              className="w-full rounded-xl border border-white/10 bg-[#101e31] px-3 py-2 text-sm text-white outline-none ring-cyan-300/60 transition focus:ring"
              placeholder="MIT"
            />
          </label>
          <label className="space-y-1">
            <span className="text-xs text-slate-300">Destination</span>
            <input
              value={destination}
              onChange={(event) => onDestinationChange(event.target.value)}
              className="w-full rounded-xl border border-white/10 bg-[#101e31] px-3 py-2 text-sm text-white outline-none ring-cyan-300/60 transition focus:ring"
              placeholder="Airport"
            />
          </label>
        </div>
      </div>
    </header>
  );
}
