import { Clock3, MapPinned, Signal } from "lucide-react";

import type { RouteOption } from "@/src/types/route";

type RouteCardProps = {
  route: RouteOption;
  isRecommended: boolean;
};

export function RouteCard({ route, isRecommended }: RouteCardProps) {
  return (
    <article
      className={`rounded-2xl border p-4 transition ${
        isRecommended
          ? "border-emerald-400/70 bg-emerald-400/10"
          : "border-white/10 bg-[#0f1b2d] hover:border-cyan-300/45"
      }`}
    >
      <div className="mb-3 flex items-start justify-between">
        <h3 className="text-lg font-semibold text-white">{route.name}</h3>
        {isRecommended ? (
          <span className="rounded-full bg-emerald-300/20 px-3 py-1 text-xs text-emerald-200">
            Recommended
          </span>
        ) : null}
      </div>

      <dl className="grid grid-cols-3 gap-3 text-xs text-slate-300">
        <div className="rounded-xl bg-[#0b1526] p-2">
          <dt className="mb-1 flex items-center gap-1">
            <Clock3 className="h-3.5 w-3.5" /> ETA
          </dt>
          <dd className="text-sm font-medium text-white">{route.eta} min</dd>
        </div>
        <div className="rounded-xl bg-[#0b1526] p-2">
          <dt className="mb-1 flex items-center gap-1">
            <MapPinned className="h-3.5 w-3.5" /> Distance
          </dt>
          <dd className="text-sm font-medium text-white">
            {route.distance} km
          </dd>
        </div>
        <div className="rounded-xl bg-[#0b1526] p-2">
          <dt className="mb-1 flex items-center gap-1">
            <Signal className="h-3.5 w-3.5" /> Signal
          </dt>
          <dd className="text-sm font-medium text-white">
            {route.signal_score}
          </dd>
        </div>
      </dl>

      <p className="mt-3 text-xs text-slate-400">
        Route zones: {route.zones.join(" -> ")}
      </p>
    </article>
  );
}
