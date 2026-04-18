"use client";

import type { WeatherInfo } from "@/src/types/route";

type Props = {
  weather: WeatherInfo;
};

export function WeatherBadge({ weather }: Props) {
  const impactColor =
    weather.weather_factor >= 0.90
      ? "text-green-600"
      : weather.weather_factor >= 0.70
        ? "text-yellow-600"
        : weather.weather_factor >= 0.50
          ? "text-orange-500"
          : "text-red-600";

  return (
    <div className="flex items-center gap-2 rounded-xl bg-white/92 px-3 py-2 shadow-md ring-1 ring-black/5 backdrop-blur-sm text-sm">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={`https://openweathermap.org/img/wn/${weather.icon}.png`}
        alt={weather.condition}
        width={36}
        height={36}
        className="shrink-0"
      />
      <div className="min-w-0">
        <p className="font-medium text-gray-800 leading-tight truncate">
          {weather.description}
        </p>
        <p className={`text-xs leading-tight ${impactColor}`}>
          {weather.signal_impact}
        </p>
      </div>
      <div className="text-right shrink-0 pl-1">
        <p className="font-semibold text-gray-700 leading-tight">
          {weather.temperature_c}°C
        </p>
        <p className="text-xs text-gray-500 leading-tight">
          {weather.humidity_pct}% hum
        </p>
      </div>
    </div>
  );
}
