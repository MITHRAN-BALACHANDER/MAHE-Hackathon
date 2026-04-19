"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import type { WeatherInfo } from "@/src/types/route";

type Props = {
  weather: WeatherInfo;
};

function getImpactDescription(weather: WeatherInfo): string {
  const cond = weather.condition?.toLowerCase() ?? "";
  if (cond.includes("thunder") || cond.includes("storm"))
    return "Thunderstorms severely disrupt wireless signals. Expect frequent call drops and very slow data across all networks.";
  if (cond.includes("rain") || cond.includes("drizzle"))
    return "Rain attenuates high-frequency 4G/5G bands. Expect 15-30% slower speeds and occasional drops in open areas.";
  if (cond.includes("fog") || cond.includes("mist") || cond.includes("haze"))
    return "Fog and haze scatter radio waves slightly. Indoor coverage may feel weaker than usual.";
  if (cond.includes("snow") || cond.includes("sleet"))
    return "Snow absorbs radio frequency energy. Data speeds can drop 20-40% in heavy snowfall.";
  if (weather.weather_factor >= 0.90)
    return "Clear conditions — signal should be optimal across all networks.";
  if (weather.weather_factor >= 0.70)
    return "Mild weather effects — minor signal variations possible in exposed or elevated areas.";
  if (weather.weather_factor >= 0.50)
    return "Moderate weather — expect 10-20% signal degradation, especially on 5G mmWave bands.";
  return "Severe weather — significant signal loss likely. 4G/5G reliability reduced across most carriers.";
}

export function WeatherBadge({ weather }: Props) {
  const [open, setOpen] = useState(false);

  const impactColor =
    weather.weather_factor >= 0.90
      ? "text-emerald-400"
      : weather.weather_factor >= 0.70
        ? "text-amber-400"
        : weather.weather_factor >= 0.50
          ? "text-orange-400"
          : "text-red-400";

  const impactBg =
    weather.weather_factor >= 0.90
      ? "bg-emerald-500/10 border-emerald-500/20"
      : weather.weather_factor >= 0.70
        ? "bg-amber-500/10 border-amber-500/20"
        : weather.weather_factor >= 0.50
          ? "bg-orange-500/10 border-orange-500/20"
          : "bg-red-500/10 border-red-500/20";

  return (
    <div className="relative flex items-end flex-col">
      {/* Collapsed icon button */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        title={`${weather.description} · ${weather.temperature_c}°C — click for details`}
        className="w-full flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] cursor-pointer transition-all"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={`https://openweathermap.org/img/wn/${weather.icon}.png`}
          alt={weather.condition}
          width={22}
          height={22}
          className="shrink-0"
        />
        <span className="text-[11px] font-semibold text-white/80 flex-1 text-left truncate capitalize">
          {weather.description}
        </span>
        <span className="text-[11px] font-bold text-white/90 shrink-0">
          {weather.temperature_c}°C
        </span>
      </button>

      {/* Expanded panel -- absolute so it overlays without pushing content */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.96 }}
            transition={{ duration: 0.18 }}
            className="absolute right-0 top-full mt-2 z-[1200] glass-card rounded-2xl p-4 w-64 text-sm shadow-xl"
          >
            {/* Header row */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`https://openweathermap.org/img/wn/${weather.icon}@2x.png`}
                  alt={weather.condition}
                  width={40}
                  height={40}
                  className="shrink-0"
                />
                <div>
                  <p className="font-semibold text-white/90 leading-tight capitalize">
                    {weather.description}
                  </p>
                  <p className="text-xs text-white/40 leading-tight">
                    {weather.temperature_c}°C · {weather.humidity_pct}% humidity
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="p-1 rounded-full hover:bg-white/10 cursor-pointer transition-colors text-white/40 hover:text-white/80"
              >
                <X size={14} />
              </button>
            </div>

            {/* Signal impact label */}
            <p className={`text-xs font-medium mb-2 ${impactColor}`}>
              {weather.signal_impact}
            </p>

            {/* Impact description */}
            <div className={`rounded-lg border px-3 py-2 ${impactBg}`}>
              <p className="text-xs text-white/70 leading-relaxed">
                {getImpactDescription(weather)}
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
