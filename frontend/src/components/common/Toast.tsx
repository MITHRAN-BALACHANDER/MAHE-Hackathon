"use client";

import { AlertTriangle, Info, X } from "lucide-react";
import { useState } from "react";

type Props = {
  message: string | null;
  type?: "info" | "warning" | "reroute";
};

export function Toast({ message, type = "info" }: Props) {
  const [dismissed, setDismissed] = useState(false);

  if (!message || dismissed) return null;

  const Icon = type === "warning" || type === "reroute" ? AlertTriangle : Info;
  const bg =
    type === "warning"
      ? "bg-yellow-50 border-yellow-200 text-yellow-800"
      : type === "reroute"
        ? "bg-blue-50 border-blue-200 text-blue-800"
        : "bg-white border-gray-200 text-gray-700";

  return (
    <div
      className={`absolute bottom-6 left-4 z-[1000] max-w-sm rounded-xl border shadow-lg px-4 py-3 flex items-start gap-3 ${bg}`}
    >
      <Icon size={18} className="shrink-0 mt-0.5" />
      <p className="text-sm flex-1">{message}</p>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        className="shrink-0 opacity-60 hover:opacity-100 cursor-pointer"
      >
        <X size={16} />
      </button>
    </div>
  );
}
