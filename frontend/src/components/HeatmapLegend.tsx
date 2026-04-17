export function HeatmapLegend() {
  return (
    <section className="rounded-2xl border border-white/10 bg-[#0f1b2d] p-4">
      <h2 className="mb-3 text-sm font-semibold text-white">
        Connectivity Heatmap Legend
      </h2>
      <div className="grid gap-2 text-xs text-slate-300">
        <div className="flex items-center gap-2">
          <span className="h-3 w-3 rounded-full bg-emerald-400" />
          <span>Strong signal</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-3 w-3 rounded-full bg-yellow-400" />
          <span>Medium signal</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-3 w-3 rounded-full bg-red-400" />
          <span>Weak signal</span>
        </div>
      </div>
    </section>
  );
}
