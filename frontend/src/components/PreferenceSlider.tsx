import type { TelecomMode } from "@/src/types/route";

type PreferenceSliderProps = {
  preference: number;
  telecom: TelecomMode;
  emergencyMode: boolean;
  onPreferenceChange: (value: number) => void;
  onTelecomChange: (value: TelecomMode) => void;
  onEmergencyModeChange: (value: boolean) => void;
};

export function PreferenceSlider({
  preference,
  telecom,
  emergencyMode,
  onPreferenceChange,
  onTelecomChange,
  onEmergencyModeChange,
}: PreferenceSliderProps) {
  return (
    <section className="rounded-2xl border border-white/10 bg-[#0f1b2d] p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-white">
          ETA vs Connectivity Preference
        </h2>
        <p className="rounded-full bg-cyan-300/20 px-3 py-1 text-xs text-cyan-100">
          {preference}% toward connectivity
        </p>
      </div>

      <input
        type="range"
        min={0}
        max={100}
        value={preference}
        onChange={(event) => onPreferenceChange(Number(event.target.value))}
        className="mt-4 w-full accent-cyan-300"
      />

      <div className="mt-2 flex justify-between text-xs text-slate-400">
        <span>0 = fastest route</span>
        <span>100 = strongest signal</span>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <label className="space-y-1">
          <span className="text-xs text-slate-300">Telecom Mode</span>
          <select
            value={telecom}
            onChange={(event) =>
              onTelecomChange(event.target.value as TelecomMode)
            }
            className="w-full rounded-xl border border-white/10 bg-[#101e31] px-3 py-2 text-sm text-white outline-none ring-cyan-300/60 transition focus:ring"
          >
            <option value="all">All Networks</option>
            <option value="jio">Jio</option>
            <option value="airtel">Airtel</option>
            <option value="vi">Vi</option>
          </select>
        </label>

        <label className="flex items-center justify-between rounded-xl border border-white/10 bg-[#101e31] px-3 py-2 text-sm text-white">
          <span>Emergency Route Mode</span>
          <input
            type="checkbox"
            checked={emergencyMode}
            onChange={(event) => onEmergencyModeChange(event.target.checked)}
            className="h-4 w-4 accent-cyan-300"
          />
        </label>
      </div>
    </section>
  );
}
