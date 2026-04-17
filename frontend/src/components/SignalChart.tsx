"use client";

import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from "chart.js";
import { Bar } from "react-chartjs-2";

import type { RouteOption } from "@/src/types/route";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Tooltip,
  Legend,
  Filler,
);

type SignalChartProps = {
  routes: RouteOption[];
};

export function SignalChart({ routes }: SignalChartProps) {
  return (
    <section className="rounded-2xl border border-white/10 bg-[#0f1b2d] p-4">
      <h2 className="mb-3 text-sm font-semibold text-white">
        Signal Quality by Route
      </h2>
      <div className="h-[260px]">
        <Bar
          data={{
            labels: routes.map((route) => route.name),
            datasets: [
              {
                label: "Signal Score",
                data: routes.map((route) => route.signal_score),
                borderRadius: 8,
                backgroundColor: [
                  "rgba(34, 211, 238, 0.6)",
                  "rgba(250, 204, 21, 0.6)",
                  "rgba(52, 211, 153, 0.6)",
                ],
                borderColor: ["#22d3ee", "#facc15", "#34d399"],
                borderWidth: 1,
              },
            ],
          }}
          options={{
            maintainAspectRatio: false,
            plugins: {
              legend: {
                labels: {
                  color: "#e2e8f0",
                },
              },
            },
            scales: {
              y: {
                beginAtZero: true,
                max: 100,
                ticks: {
                  color: "#cbd5e1",
                },
                grid: {
                  color: "rgba(148, 163, 184, 0.2)",
                },
              },
              x: {
                ticks: {
                  color: "#cbd5e1",
                },
                grid: {
                  display: false,
                },
              },
            },
          }}
        />
      </div>
    </section>
  );
}
